# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Qlib 数据访问模块 - 核心数据提供者实现

本模块定义了 Qlib 数据访问层的核心组件，包括：
1. 各种数据提供者的抽象基类和具体实现
2. 本地数据访问和客户端数据访问支持
3. 交易日历、股票列表、特征数据、表达式和数据集的统一访问接口
4. 高效的数据缓存和并行处理机制

主要组件：
- CalendarProvider: 交易日历数据提供者
- InstrumentProvider: 股票/工具数据提供者
- FeatureProvider: 特征数据提供者
- ExpressionProvider: 表达式计算提供者
- DatasetProvider: 数据集提供者
- PITProvider: 点对点数据提供者

使用方式：
    from qlib.data import D

    # 获取股票列表
    instruments = D.instruments('csi300')

    # 获取特征数据
    features = D.features(instruments, ['close', 'volume'],
                         start_time='2020-01-01', end_time='2020-12-31')
"""

from __future__ import division
from __future__ import print_function

import abc
import bisect
import copy
import queue
import re
import sys

import numpy as np
import pandas as pd
from typing import List, Union, Optional

# 支持外部代码中的多进程处理，使用 joblib
from joblib import delayed

from .cache import H  # 全局缓存对象
from ..config import C  # 全局配置对象
from .inst_processor import InstProcessor  # 实例处理器

from ..log import get_module_logger  # 日志记录器
from .cache import DiskDatasetCache  # 磁盘数据集缓存
from ..utils import (
    Wrapper,
    init_instance_by_config,
    register_wrapper,
    get_module_by_module_path,
    parse_field,
    hash_args,
    normalize_cache_fields,
    code_to_fname,
    time_to_slc_point,
    read_period_data,
    get_period_list,
)
from ..utils.paral import ParallelExt  # 并行处理扩展
from .ops import Operators  # pylint: disable=W0611  # noqa: F401


class ProviderBackendMixin:
    """
    存储后端提供者混入类

    这个辅助类使得基于存储后端的数据提供者更加便利。
    如果提供者不依赖后端存储，则不需要继承此类。

    主要功能：
    1. 根据类名自动推断默认的后端存储类
    2. 提供统一的后端对象创建接口
    3. 支持后端配置的动态修改

    使用示例：
        class LocalCalendarProvider(CalendarProvider, ProviderBackendMixin):
            # 自动使用 FileCalendarStorage 作为后端
            pass
    """

    def get_default_backend(self):
        """
        获取默认的后端存储配置

        根据当前类名自动推断后端存储类：
        - LocalCalendarProvider -> FileCalendarStorage
        - LocalInstrumentProvider -> FileInstrumentStorage
        - LocalFeatureProvider -> FileFeatureStorage

        Returns:
            dict: 后端存储配置字典
        """
        backend = {}
        # 从类名中提取提供者名称（如 LocalCalendarProvider 中的 Calendar）
        provider_name: str = re.findall("[A-Z][^A-Z]*", self.__class__.__name__)[-2]
        # 设置默认存储类名
        backend.setdefault("class", f"File{provider_name}Storage")
        # 设置默认存储模块路径
        backend.setdefault("module_path", "qlib.data.storage.file_storage")
        return backend

    def backend_obj(self, **kwargs):
        """
        创建后端存储对象

        根据配置创建后端存储实例，支持动态参数覆盖。

        Args:
            **kwargs: 要覆盖或添加的后端参数

        Returns:
            object: 初始化的后端存储对象实例
        """
        # 使用已配置的后端或获取默认后端
        backend = self.backend if self.backend else self.get_default_backend()
        # 深拷贝后端配置以避免修改原始配置
        backend = copy.deepcopy(backend)
        # 更新后端参数
        backend.setdefault("kwargs", {}).update(**kwargs)
        # 根据配置初始化后端对象
        return init_instance_by_config(backend)


class CalendarProvider(abc.ABC):
    """
    交易日历提供者基类

    提供交易日历数据访问的抽象接口，负责：
    1. 加载和缓存交易日历数据
    2. 根据时间范围和频率过滤交易日
    3. 支持历史和未来交易日的查询
    4. 提供高效的日历索引定位功能

    子类需要实现的方法：
    - load_calendar(): 从数据源加载原始日历数据

    使用示例：
        calendar_provider = LocalCalendarProvider()
        # 获取2020年的交易日历
        trading_days = calendar_provider.calendar(
            start_time="2020-01-01",
            end_time="2020-12-31",
            freq="day"
        )
    """

    def calendar(self, start_time=None, end_time=None, freq="day", future=False):
        """
        获取指定时间范围内的交易日历

        根据开始时间、结束时间、频率等参数返回符合条件的交易日列表。
        支持灵活的时间范围查询和未来交易日查询。

        Args:
            start_time (str, optional): 时间范围开始时间。格式：YYYY-MM-DD
            end_time (str, optional): 时间范围结束时间。格式：YYYY-MM-DD
            freq (str): 时间频率。可选值：year/quarter/month/week/day，默认为"day"
            future (bool): 是否包含未来交易日。默认为False

        Returns:
            np.ndarray: 交易日历数组，包含所有符合条件的交易日期

        Note:
            - 如果查询时间范围超出数据范围，返回空数组
            - 如果未指定时间范围，使用全部可用日历数据
            - 支持字符串"None"作为参数值，会被转换为None
        """
        # 从缓存或数据源获取完整日历和索引
        _calendar, _calendar_index = self._get_calendar(freq, future)

        # 处理字符串"None"的情况
        if start_time == "None":
            start_time = None
        if end_time == "None":
            end_time = None

        # 处理开始时间
        if start_time:
            start_time = pd.Timestamp(start_time)
            # 如果开始时间超出日历范围，返回空数组
            if start_time > _calendar[-1]:
                return np.array([])
        else:
            # 如果未指定开始时间，使用日历的最早日期
            start_time = _calendar[0]

        # 处理结束时间
        if end_time:
            end_time = pd.Timestamp(end_time)
            # 如果结束时间早于日历开始，返回空数组
            if end_time < _calendar[0]:
                return np.array([])
        else:
            # 如果未指定结束时间，使用日历的最晚日期
            end_time = _calendar[-1]

        # 定位时间范围在日历中的索引位置
        _, _, si, ei = self.locate_index(start_time, end_time, freq, future)
        # 返回切片后的日历数据
        return _calendar[si : ei + 1]

    def locate_index(
        self,
        start_time: Union[pd.Timestamp, str],
        end_time: Union[pd.Timestamp, str],
        freq: str,
        future: bool = False,
    ):
        """
        在指定频率的日历中定位开始时间和结束时间的索引位置

        这个方法用于将任意时间点映射到交易日历中的具体索引位置，
        自动处理非交易日的情况，返回最接近的有效交易日。

        Args:
            start_time (Union[pd.Timestamp, str]): 时间范围开始时间
            end_time (Union[pd.Timestamp, str]): 时间范围结束时间
            freq (str): 时间频率。可选值：year/quarter/month/week/day
            future (bool): 是否包含未来交易日。默认为False

        Returns:
            tuple: 包含四个元素的元组
                - pd.Timestamp: 实际的开始时间（交易日）
                - pd.Timestamp: 实际的结束时间（交易日）
                - int: 开始时间在日历中的索引
                - int: 结束时间在日历中的索引

        Raises:
            IndexError: 当开始时间是未来日期且future=False时抛出

        Note:
            - 如果开始时间不是交易日，会自动向后找到最近的交易日
            - 如果结束时间不是交易日，会自动向前找到最近的交易日
            - 使用二分查找算法提高定位效率
        """
        # 转换为Timestamp格式
        start_time = pd.Timestamp(start_time)
        end_time = pd.Timestamp(end_time)

        # 获取指定频率和未来标志的日历数据
        calendar, calendar_index = self._get_calendar(freq=freq, future=future)

        # 处理开始时间：如果不是交易日，找到最近的交易日
        if start_time not in calendar_index:
            try:
                # 使用二分查找找到第一个大于等于开始时间的交易日
                start_time = calendar[bisect.bisect_left(calendar, start_time)]
            except IndexError as index_e:
                # 如果开始时间超出日历范围且未启用未来日期查询
                raise IndexError(
                    "`start_time` uses a future date, if you want to get future trading days, you can use: `future=True`"
                ) from index_e

        # 获取开始时间的索引
        start_index = calendar_index[start_time]

        # 处理结束时间：如果不是交易日，找到最近的交易日
        if end_time not in calendar_index:
            # 使用二分查找找到最后一个小于等于结束时间的交易日
            end_time = calendar[bisect.bisect_right(calendar, end_time) - 1]

        # 获取结束时间的索引
        end_index = calendar_index[end_time]

        return start_time, end_time, start_index, end_index

    def _get_calendar(self, freq, future):
        """
        使用内存缓存加载日历数据

        这个方法实现了日历数据的缓存机制，避免重复从数据源加载相同的日历。
        使用全局缓存对象 H 来存储日历数据和索引。

        Args:
            freq (str): 日历频率。可选值：year/quarter/month/week/day
            future (bool): 是否包含未来交易日

        Returns:
            tuple: 包含两个元素的元组
                - np.ndarray: 交易日历时间戳数组
                - dict: 时间戳到索引的映射字典（用于快速查找）

        Note:
            - 缓存键格式："{频率}_future_{是否包含未来}"
            - 索引字典提供O(1)的时间戳查找效率
            - 首次访问时会从数据源加载并缓存，后续访问直接从缓存读取
        """
        # 构建缓存键标识符
        flag = f"{freq}_future_{future}"

        # 检查缓存中是否已存在该日历数据
        if flag not in H["c"]:
            # 缓存未命中，从数据源加载日历
            _calendar = np.array(self.load_calendar(freq, future))
            # 构建时间戳到索引的映射字典，用于快速查找
            _calendar_index = {x: i for i, x in enumerate(_calendar)}
            # 将日历数据和索引存入缓存
            H["c"][flag] = _calendar, _calendar_index

        # 返回缓存中的日历数据
        return H["c"][flag]

    def _uri(self, start_time, end_time, freq, future=False):
        """
        获取日历生成任务的唯一URI

        根据参数生成唯一的资源标识符，用于缓存管理和任务识别。

        Args:
            start_time: 开始时间
            end_time: 结束时间
            freq: 频率
            future (bool): 是否包含未来交易日

        Returns:
            str: 基于参数哈希的唯一URI
        """
        return hash_args(start_time, end_time, freq, future)

    def load_calendar(self, freq, future):
        """
        从文件加载原始日历时间戳

        抽象方法，子类必须实现。负责从具体的数据源（如文件、数据库等）
        加载指定频率和未来标志的日历数据。

        Args:
            freq (str): 日历频率。可选值：year/quarter/month/week/day
            future (bool): 是否包含未来交易日

        Returns:
            list: 时间戳列表

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError(
            "Subclass of CalendarProvider must implement `load_calendar` method"
        )


class InstrumentProvider(abc.ABC):
    """
    股票/工具提供者基类

    提供股票、期货、期权等交易工具的数据访问抽象接口。
    支持市场定义、动态过滤、时间范围查询等功能。

    主要功能：
    1. 获取市场/指数的成分股列表
    2. 支持动态过滤器（如价格、市值、行业等）
    3. 管理工具的有效时间范围
    4. 提供灵活的工具配置接口

    子类需要实现的方法：
    - list_instruments(): 列出符合条件的工具

    使用示例：
        # 获取沪深300成分股
        config = InstrumentProvider.instruments("csi300")
        instruments = provider.list_instruments(config,
                                               start_time="2020-01-01",
                                               end_time="2020-12-31")
    """

    @staticmethod
    def instruments(
        market: Union[List, str] = "all", filter_pipe: Union[List, None] = None
    ):
        """
        获取基础市场添加动态过滤器的通用配置字典

        构建股票池配置，支持市场选择和多层过滤器的组合使用。

        Args:
            market (Union[List, str]): 市场标识或股票列表
                str: 市场/行业/指数简称，如 all/sse/szse/sse50/csi300/csi500
                list: 股票代码列表，如 ["000001.SZ", "000002.SZ"]
            filter_pipe (list, optional): 动态过滤器列表

        Returns:
            Union[dict, list]:
                dict: 当 market 为字符串时，返回股票池配置字典
                    格式: {"market": 市场名称, "filter_pipe": 过滤器列表}
                list: 当 market 为列表时，直接返回原股票列表

        Example:
            >>> config = {
            ...     'market': 'csi500',
            ...     'filter_pipe': [
            ...         {
            ...             'filter_type': 'ExpressionDFilter',
            ...             'rule_expression': '$open<40',
            ...             'filter_start_time': None,
            ...             'filter_end_time': None,
            ...             'keep': False
            ...         },
            ...         {
            ...             'filter_type': 'NameDFilter',
            ...             'name_rule_re': 'SH[0-9]{4}55',
            ...             'filter_start_time': None,
            ...             'filter_end_time': None
            ...         }
            ...     ]
            ... }

        Note:
            - 过滤器的顺序会影响最终结果，系统会按顺序应用所有过滤器
            - 支持直接传入股票列表，提高使用的便利性
        """
        # 如果传入的是股票列表，直接返回
        if isinstance(market, list):
            return market

        # 延迟导入避免循环依赖
        from .filter import SeriesDFilter  # pylint: disable=C0415

        # 初始化过滤器管道
        if filter_pipe is None:
            filter_pipe = []

        # 构建基础配置
        config = {"market": market, "filter_pipe": []}

        # 处理过滤器：保持过滤器顺序，因为顺序会影响结果
        for filter_t in filter_pipe:
            if isinstance(filter_t, dict):
                # 字典格式的过滤器配置
                _config = filter_t
            elif isinstance(filter_t, SeriesDFilter):
                # SeriesDFilter 对象转换为配置字典
                _config = filter_t.to_config()
            else:
                # 不支持的过滤器类型
                raise TypeError(
                    f"Unsupported filter types: {type(filter_t)}! Filter only supports dict or isinstance(filter, SeriesDFilter)"
                )
            config["filter_pipe"].append(_config)

        return config

    @abc.abstractmethod
    def list_instruments(
        self, instruments, start_time=None, end_time=None, freq="day", as_list=False
    ):
        """
        根据股票池配置列出符合条件的工具

        抽象方法，子类必须实现。根据配置参数获取在指定时间范围内
        有效的交易工具列表，支持多种返回格式。

        Args:
            instruments (dict): 股票池配置字典
            start_time (str, optional): 时间范围开始时间
            end_time (str, optional): 时间范围结束时间
            freq (str): 时间频率。默认为"day"
            as_list (bool): 是否以列表形式返回。默认为False（返回字典）

        Returns:
            Union[dict, list]:
                dict: 工具字典，包含每个工具的时间跨度信息
                    格式: {工具代码: [(开始时间, 结束时间), ...]}
                list: 工具代码列表（当 as_list=True 时）

        Raises:
            NotImplementedError: 子类必须实现此方法

        Note:
            - 返回的工具都是在指定时间范围内有效的
            - 字典格式包含详细的时间跨度信息
            - 列表格式仅包含工具代码，更简洁
        """
        raise NotImplementedError(
            "Subclass of InstrumentProvider must implement `list_instruments` method"
        )

    def _uri(
        self, instruments, start_time=None, end_time=None, freq="day", as_list=False
    ):
        """
        生成工具列表任务的唯一URI

        根据所有参数生成哈希值，用于缓存管理和任务识别。

        Args:
            instruments: 工具配置
            start_time: 开始时间
            end_time: 结束时间
            freq: 频率
            as_list (bool): 是否返回列表格式

        Returns:
            str: 基于参数哈希的唯一URI
        """
        return hash_args(instruments, start_time, end_time, freq, as_list)

    # 工具类型常量定义
    LIST = "LIST"    # 列表类型：直接的股票代码列表
    DICT = "DICT"    # 字典类型：包含时间跨度的股票字典
    CONF = "CONF"    # 配置类型：市场配置字典

    @classmethod
    def get_inst_type(cls, inst):
        """
        识别工具输入的类型

        根据输入数据的结构和内容判断其类型，用于后续的
        相应处理逻辑。

        Args:
            inst: 工具配置数据

        Returns:
            str: 工具类型（LIST、DICT 或 CONF）

        Raises:
            ValueError: 无法识别的工具类型

        Note:
            - CONF: 包含"market"键的配置字典
            - DICT: 不包含"market"键的普通字典
            - LIST: 列表、元组、pandas.Index 或 numpy.ndarray
        """
        if "market" in inst:
            return cls.CONF  # 市场配置类型
        if isinstance(inst, dict):
            return cls.DICT  # 字典类型
        if isinstance(inst, (list, tuple, pd.Index, np.ndarray)):
            return cls.LIST  # 列表类型
        raise ValueError(f"Unknown instrument type {inst}")


class FeatureProvider(abc.ABC):
    """
    特征数据提供者基类

    提供原始特征数据的访问接口，包括价格、成交量、技术指标等。
    这是数据访问层的基础组件，为上层的表达式计算和数据集提供数据。

    主要功能：
    1. 提供单个工具的单个特征数据访问
    2. 支持不同的时间频率和数据范围
    3. 为表达式系统提供基础数据支持
    4. 支持高效的数据索引和切片

    子类需要实现的方法：
    - feature(): 获取指定工具的特征数据

    使用示例：
        provider = LocalFeatureProvider()
        # 获取股票000001.SZ的收盘价数据
        close_prices = provider.feature("000001.SZ", "$close",
                                       start_index=0, end_index=100, freq="day")
    """

    @abc.abstractmethod
    def feature(self, instrument, field, start_index, end_index, freq):
        """
        获取指定工具的特征数据

        抽象方法，子类必须实现。返回单个工具在指定时间范围内
        的某个特征数据序列。

        Args:
            instrument (str): 工具代码，如 "000001.SZ"
            field (str): 特征字段名，如 "$close"、"$volume" 等
            start_index (int): 开始索引位置
            end_index (int): 结束索引位置
            freq (str): 数据频率。可选值：year/quarter/month/week/day

        Returns:
            pd.Series: 特征数据序列，索引为时间或整数

        Raises:
            NotImplementedError: 子类必须实现此方法

        Note:
            - field 通常以 "$" 开头表示基础特征
            - 返回的数据类型根据具体实现可能是时间索引或整数索引
            - start_index 和 end_index 是相对于数据源的索引，不是时间戳
        """
        raise NotImplementedError(
            "Subclass of FeatureProvider must implement `feature` method"
        )


class PITProvider(abc.ABC):
    @abc.abstractmethod
    def period_feature(
        self,
        instrument,
        field,
        start_index: int,
        end_index: int,
        cur_time: pd.Timestamp,
        period: Optional[int] = None,
    ) -> pd.Series:
        """
        get the historical periods data series between `start_index` and `end_index`

        Parameters
        ----------
        start_index: int
            start_index is a relative index to the latest period to cur_time

        end_index: int
            end_index is a relative index to the latest period to cur_time
            in most cases, the start_index and end_index will be a non-positive values
            For example, start_index == -3 end_index == 0 and current period index is cur_idx,
            then the data between [start_index + cur_idx, end_index + cur_idx] will be retrieved.

        period: int
            This is used for query specific period.
            The period is represented with int in Qlib. (e.g. 202001 may represent the first quarter in 2020)
            NOTE: `period`  will override `start_index` and `end_index`

        Returns
        -------
        pd.Series
            The index will be integers to indicate the periods of the data
            An typical examples will be
            TODO

        Raises
        ------
        FileNotFoundError
            This exception will be raised if the queried data do not exist.
        """
        raise NotImplementedError("Please implement the `period_feature` method")


class ExpressionProvider(abc.ABC):
    """Expression provider class

    Provide Expression data.
    """

    def __init__(self):
        self.expression_instance_cache = {}

    def get_expression_instance(self, field):
        try:
            if field in self.expression_instance_cache:
                expression = self.expression_instance_cache[field]
            else:
                expression = eval(parse_field(field))
                self.expression_instance_cache[field] = expression
        except NameError as e:
            get_module_logger("data").exception(
                "ERROR: field [%s] contains invalid operator/variable [%s]"
                % (str(field), str(e).split()[1])
            )
            raise
        except SyntaxError:
            get_module_logger("data").exception(
                "ERROR: field [%s] contains invalid syntax" % str(field)
            )
            raise
        return expression

    @abc.abstractmethod
    def expression(
        self, instrument, field, start_time=None, end_time=None, freq="day"
    ) -> pd.Series:
        """Get Expression data.

        The responsibility of `expression`
        - parse the `field` and `load` the according data.
        - When loading the data, it should handle the time dependency of the data. `get_expression_instance` is commonly used in this method

        Parameters
        ----------
        instrument : str
            a certain instrument.
        field : str
            a certain field of feature.
        start_time : str
            start of the time range.
        end_time : str
            end of the time range.
        freq : str
            time frequency, available: year/quarter/month/week/day.

        Returns
        -------
        pd.Series
            data of a certain expression

            The data has two types of format

            1) expression with datetime index

            2) expression with integer index

                - because the datetime is not as good as
        """
        raise NotImplementedError(
            "Subclass of ExpressionProvider must implement `Expression` method"
        )


class DatasetProvider(abc.ABC):
    """Dataset provider class

    Provide Dataset data.
    """

    @abc.abstractmethod
    def dataset(
        self,
        instruments,
        fields,
        start_time=None,
        end_time=None,
        freq="day",
        inst_processors=[],
    ):
        """Get dataset data.

        Parameters
        ----------
        instruments : list or dict
            list/dict of instruments or dict of stockpool config.
        fields : list
            list of feature instances.
        start_time : str
            start of the time range.
        end_time : str
            end of the time range.
        freq : str
            time frequency.
        inst_processors:  Iterable[Union[dict, InstProcessor]]
            the operations performed on each instrument

        Returns
        ----------
        pd.DataFrame
            a pandas dataframe with <instrument, datetime> index.
        """
        raise NotImplementedError(
            "Subclass of DatasetProvider must implement `Dataset` method"
        )

    def _uri(
        self,
        instruments,
        fields,
        start_time=None,
        end_time=None,
        freq="day",
        disk_cache=1,
        inst_processors=[],
        **kwargs,
    ):
        """Get task uri, used when generating rabbitmq task in qlib_server

        Parameters
        ----------
        instruments : list or dict
            list/dict of instruments or dict of stockpool config.
        fields : list
            list of feature instances.
        start_time : str
            start of the time range.
        end_time : str
            end of the time range.
        freq : str
            time frequency.
        disk_cache : int
            whether to skip(0)/use(1)/replace(2) disk_cache.

        """
        # TODO: qlib-server support inst_processors
        return DiskDatasetCache._uri(
            instruments, fields, start_time, end_time, freq, disk_cache, inst_processors
        )

    @staticmethod
    def get_instruments_d(instruments, freq):
        """
        Parse different types of input instruments to output instruments_d
        Wrong format of input instruments will lead to exception.

        """
        if isinstance(instruments, dict):
            if "market" in instruments:
                # dict of stockpool config
                instruments_d = Inst.list_instruments(
                    instruments=instruments, freq=freq, as_list=False
                )
            else:
                # dict of instruments and timestamp
                instruments_d = instruments
        elif isinstance(instruments, (list, tuple, pd.Index, np.ndarray)):
            # list or tuple of a group of instruments
            instruments_d = list(instruments)
        else:
            raise ValueError("Unsupported input type for param `instrument`")
        return instruments_d

    @staticmethod
    def get_column_names(fields):
        """
        Get column names from input fields

        """
        if len(fields) == 0:
            raise ValueError("fields cannot be empty")
        column_names = [str(f) for f in fields]
        return column_names

    @staticmethod
    def parse_fields(fields):
        # parse and check the input fields
        return [ExpressionD.get_expression_instance(f) for f in fields]

    @staticmethod
    def dataset_processor(
        instruments_d, column_names, start_time, end_time, freq, inst_processors=[]
    ):
        """
        Load and process the data, return the data set.
        - default using multi-kernel method.

        """
        normalize_column_names = normalize_cache_fields(column_names)
        # One process for one task, so that the memory will be freed quicker.
        workers = max(min(C.get_kernels(freq), len(instruments_d)), 1)

        # create iterator
        if isinstance(instruments_d, dict):
            it = instruments_d.items()
        else:
            it = zip(instruments_d, [None] * len(instruments_d))

        inst_l = []
        task_l = []
        for inst, spans in it:
            inst_l.append(inst)
            task_l.append(
                delayed(DatasetProvider.inst_calculator)(
                    inst,
                    start_time,
                    end_time,
                    freq,
                    normalize_column_names,
                    spans,
                    C,
                    inst_processors,
                )
            )

        data = dict(
            zip(
                inst_l,
                ParallelExt(
                    n_jobs=workers,
                    backend=C.joblib_backend,
                    maxtasksperchild=C.maxtasksperchild,
                )(task_l),
            )
        )

        new_data = dict()
        for inst in sorted(data.keys()):
            if len(data[inst]) > 0:
                # NOTE: Python version >= 3.6; in versions after python3.6, dict will always guarantee the insertion order
                new_data[inst] = data[inst]

        if len(new_data) > 0:
            data = pd.concat(new_data, names=["instrument"], sort=False)
            data = DiskDatasetCache.cache_to_origin_data(data, column_names)
        else:
            data = pd.DataFrame(
                index=pd.MultiIndex.from_arrays(
                    [[], []], names=("instrument", "datetime")
                ),
                columns=column_names,
                dtype=np.float32,
            )

        return data

    @staticmethod
    def inst_calculator(
        inst,
        start_time,
        end_time,
        freq,
        column_names,
        spans=None,
        g_config=None,
        inst_processors=[],
    ):
        """
        Calculate the expressions for **one** instrument, return a df result.
        If the expression has been calculated before, load from cache.

        return value: A data frame with index 'datetime' and other data columns.

        """
        # FIXME: Windows OS or MacOS using spawn: https://docs.python.org/3.8/library/multiprocessing.html?highlight=spawn#contexts-and-start-methods
        # NOTE: This place is compatible with windows, windows multi-process is spawn
        C.register_from_C(g_config)

        obj = dict()
        for field in column_names:
            #  The client does not have expression provider, the data will be loaded from cache using static method.
            obj[field] = ExpressionD.expression(inst, field, start_time, end_time, freq)

        data = pd.DataFrame(obj)
        if not data.empty and not np.issubdtype(data.index.dtype, np.dtype("M")):
            # If the underlaying provides the data not in datetime format, we'll convert it into datetime format
            _calendar = Cal.calendar(freq=freq)
            data.index = _calendar[data.index.values.astype(int)]
        data.index.names = ["datetime"]

        if not data.empty and spans is not None:
            mask = np.zeros(len(data), dtype=bool)
            for begin, end in spans:
                mask |= (data.index >= begin) & (data.index <= end)
            data = data[mask]

        for _processor in inst_processors:
            if _processor:
                _processor_obj = init_instance_by_config(
                    _processor, accept_types=InstProcessor
                )
                data = _processor_obj(data, instrument=inst)
        return data


class LocalCalendarProvider(CalendarProvider, ProviderBackendMixin):
    """Local calendar data provider class

    Provide calendar data from local data source.
    """

    def __init__(self, remote=False, backend={}):
        super().__init__()
        self.remote = remote
        self.backend = backend

    def load_calendar(self, freq, future):
        """Load original calendar timestamp from file.

        Parameters
        ----------
        freq : str
            frequency of read calendar file.
        future: bool
        Returns
        ----------
        list
            list of timestamps
        """
        try:
            backend_obj = self.backend_obj(freq=freq, future=future).data
        except ValueError:
            if future:
                get_module_logger("data").warning(
                    f"load calendar error: freq={freq}, future={future}; return current calendar!"
                )
                get_module_logger("data").warning(
                    "You can get future calendar by referring to the following document: https://github.com/microsoft/qlib/blob/main/scripts/data_collector/contrib/README.md"
                )
                backend_obj = self.backend_obj(freq=freq, future=False).data
            else:
                raise

        return [pd.Timestamp(x) for x in backend_obj]


class LocalInstrumentProvider(InstrumentProvider, ProviderBackendMixin):
    """Local instrument data provider class

    Provide instrument data from local data source.
    """

    def __init__(self, backend={}) -> None:
        super().__init__()
        self.backend = backend

    def _load_instruments(self, market, freq):
        return self.backend_obj(market=market, freq=freq).data

    def list_instruments(
        self, instruments, start_time=None, end_time=None, freq="day", as_list=False
    ):
        market = instruments["market"]
        if market in H["i"]:
            _instruments = H["i"][market]
        else:
            _instruments = self._load_instruments(market, freq=freq)
            H["i"][market] = _instruments
        # strip
        # use calendar boundary
        cal = Cal.calendar(freq=freq)
        start_time = pd.Timestamp(start_time or cal[0])
        end_time = pd.Timestamp(end_time or cal[-1])
        _instruments_filtered = {
            inst: list(
                filter(
                    lambda x: x[0] <= x[1],
                    [
                        (
                            max(start_time, pd.Timestamp(x[0])),
                            min(end_time, pd.Timestamp(x[1])),
                        )
                        for x in spans
                    ],
                )
            )
            for inst, spans in _instruments.items()
        }
        _instruments_filtered = {
            key: value for key, value in _instruments_filtered.items() if value
        }
        # filter
        filter_pipe = instruments["filter_pipe"]
        for filter_config in filter_pipe:
            from . import filter as F  # pylint: disable=C0415

            filter_t = getattr(F, filter_config["filter_type"]).from_config(
                filter_config
            )
            _instruments_filtered = filter_t(
                _instruments_filtered, start_time, end_time, freq
            )
        # as list
        if as_list:
            return list(_instruments_filtered)
        return _instruments_filtered


class LocalFeatureProvider(FeatureProvider, ProviderBackendMixin):
    """Local feature data provider class

    Provide feature data from local data source.
    """

    def __init__(self, remote=False, backend={}):
        super().__init__()
        self.remote = remote
        self.backend = backend

    def feature(self, instrument, field, start_index, end_index, freq):
        # validate
        field = str(field)[1:]
        instrument = code_to_fname(instrument)
        return self.backend_obj(instrument=instrument, field=field, freq=freq)[
            start_index : end_index + 1
        ]


class LocalPITProvider(PITProvider):
    # TODO: Add PIT backend file storage
    # NOTE: This class is not multi-threading-safe!!!!

    def period_feature(
        self, instrument, field, start_index, end_index, cur_time, period=None
    ):
        if not isinstance(cur_time, pd.Timestamp):
            raise ValueError(
                f"Expected pd.Timestamp for `cur_time`, got '{cur_time}'. Advices: you can't query PIT data directly(e.g. '$$roewa_q'), you must use `P` operator to convert data to each day (e.g. 'P($$roewa_q)')"
            )

        assert end_index <= 0  # PIT don't support querying future data

        DATA_RECORDS = [
            ("date", C.pit_record_type["date"]),
            ("period", C.pit_record_type["period"]),
            ("value", C.pit_record_type["value"]),
            ("_next", C.pit_record_type["index"]),
        ]
        VALUE_DTYPE = C.pit_record_type["value"]

        field = str(field).lower()[2:]
        instrument = code_to_fname(instrument)

        # {For acceleration
        # start_index, end_index, cur_index = kwargs["info"]
        # if cur_index == start_index:
        #     if not hasattr(self, "all_fields"):
        #         self.all_fields = []
        #     self.all_fields.append(field)
        #     if not hasattr(self, "period_index"):
        #         self.period_index = {}
        #     if field not in self.period_index:
        #         self.period_index[field] = {}
        # For acceleration}

        if not field.endswith("_q") and not field.endswith("_a"):
            raise ValueError("period field must ends with '_q' or '_a'")
        quarterly = field.endswith("_q")
        index_path = (
            C.dpm.get_data_uri() / "financial" / instrument.lower() / f"{field}.index"
        )
        data_path = (
            C.dpm.get_data_uri() / "financial" / instrument.lower() / f"{field}.data"
        )
        if not (index_path.exists() and data_path.exists()):
            raise FileNotFoundError("No file is found.")
        # NOTE: The most significant performance loss is here.
        # Does the acceleration that makes the program complicated really matters?
        # - It makes parameters of the interface complicate
        # - It does not performance in the optimal way (places all the pieces together, we may achieve higher performance)
        #    - If we design it carefully, we can go through for only once to get the historical evolution of the data.
        # So I decide to deprecated previous implementation and keep the logic of the program simple
        # Instead, I'll add a cache for the index file.
        data = np.fromfile(data_path, dtype=DATA_RECORDS)

        # find all revision periods before `cur_time`
        cur_time_int = (
            int(cur_time.year) * 10000 + int(cur_time.month) * 100 + int(cur_time.day)
        )
        loc = np.searchsorted(data["date"], cur_time_int, side="right")
        if loc <= 0:
            return pd.Series(dtype=C.pit_record_type["value"])
        last_period = data["period"][:loc].max()  # return the latest quarter
        first_period = data["period"][:loc].min()
        period_list = get_period_list(first_period, last_period, quarterly)
        if period is not None:
            # NOTE: `period` has higher priority than `start_index` & `end_index`
            if period not in period_list:
                return pd.Series(dtype=C.pit_record_type["value"])
            else:
                period_list = [period]
        else:
            period_list = period_list[
                max(0, len(period_list) + start_index - 1) : len(period_list)
                + end_index
            ]
        value = np.full((len(period_list),), np.nan, dtype=VALUE_DTYPE)
        for i, p in enumerate(period_list):
            # last_period_index = self.period_index[field].get(period)  # For acceleration
            value[i], now_period_index = read_period_data(
                index_path,
                data_path,
                p,
                cur_time_int,
                quarterly,  # , last_period_index  # For acceleration
            )
            # self.period_index[field].update({period: now_period_index})  # For acceleration
        # NOTE: the index is period_list; So it may result in unexpected values(e.g. nan)
        # when calculation between different features and only part of its financial indicator is published
        series = pd.Series(value, index=period_list, dtype=VALUE_DTYPE)

        # {For acceleration
        # if cur_index == end_index:
        #     self.all_fields.remove(field)
        #     if not len(self.all_fields):
        #         del self.all_fields
        #         del self.period_index
        # For acceleration}

        return series


class LocalExpressionProvider(ExpressionProvider):
    """Local expression data provider class

    Provide expression data from local data source.
    """

    def __init__(self, time2idx=True):
        super().__init__()
        self.time2idx = time2idx

    def expression(self, instrument, field, start_time=None, end_time=None, freq="day"):
        expression = self.get_expression_instance(field)
        start_time = time_to_slc_point(start_time)
        end_time = time_to_slc_point(end_time)

        # Two kinds of queries are supported
        # - Index-based expression: this may save a lot of memory because the datetime index is not saved on the disk
        # - Data with datetime index expression: this will make it more convenient to integrating with some existing databases
        if self.time2idx:
            _, _, start_index, end_index = Cal.locate_index(
                start_time, end_time, freq=freq, future=False
            )
            lft_etd, rght_etd = expression.get_extended_window_size()
            query_start, query_end = max(0, start_index - lft_etd), end_index + rght_etd
        else:
            start_index, end_index = query_start, query_end = start_time, end_time

        try:
            series = expression.load(instrument, query_start, query_end, freq)
        except Exception as e:
            get_module_logger("data").debug(
                "Loading expression error: "
                f"instrument={instrument}, field=({field}), start_time={start_time}, end_time={end_time}, freq={freq}. "
                f"error info: {str(e)}"
            )
            raise
        # Ensure that each column type is consistent
        # FIXME:
        # 1) The stock data is currently float. If there is other types of data, this part needs to be re-implemented.
        # 2) The precision should be configurable
        try:
            series = series.astype(np.float32)
        except ValueError:
            pass
        except TypeError:
            pass
        if not series.empty:
            series = series.loc[start_index:end_index]
        return series


class LocalDatasetProvider(DatasetProvider):
    """
    本地数据集提供者类

    从本地数据源提供完整的数据集访问功能。这是 Qlib 最核心的
    数据访问组件，负责将多个工具的多个特征组合成统一的数据集。

    主要功能：
    1. 支持多工具、多特征的数据集查询
    2. 提供时间对齐和数据缓存机制
    3. 支持并行处理提高数据加载效率
    4. 支持实例级别的数据后处理
    5. 提供表达式缓存预热的批量操作

    核心特性：
    - 时间对齐：将数据对齐到标准交易日历
    - 并行处理：使用多进程并行加载不同工具的数据
    - 缓存优化：多级缓存机制提高访问效率
    - 灵活配置：支持不同的数据处理器和过滤条件

    Args:
        align_time (bool): 是否将时间对齐到日历。默认为True

    Note:
        - 对于固定频率的数据，时间对齐可以提高缓存效率
        - 对于灵活频率的数据，应关闭时间对齐功能
        - 对齐后的查询可以使用相同的缓存，提高性能
    """

    def __init__(self, align_time: bool = True):
        """
        初始化本地数据集提供者

        Args:
            align_time (bool): 是否将时间对齐到标准日历
                True: 将数据对齐到固定频率的日历点，有利于缓存共享
                False: 保持原始数据的时间点，适用于灵活频率的数据

        Note:
            时间对齐的好处：
            - 统一查询参数，便于缓存共享
            - 确保不同工具的数据在时间维度上对齐
            - 提高后续数据处理的效率
        """
        super().__init__()
        self.align_time = align_time

    def dataset(
        self,
        instruments,
        fields,
        start_time=None,
        end_time=None,
        freq="day",
        inst_processors=[],
    ):
        instruments_d = self.get_instruments_d(instruments, freq)
        column_names = self.get_column_names(fields)
        if self.align_time:
            # NOTE: if the frequency is a fixed value.
            # align the data to fixed calendar point
            cal = Cal.calendar(start_time, end_time, freq)
            if len(cal) == 0:
                return pd.DataFrame(
                    index=pd.MultiIndex.from_arrays(
                        [[], []], names=("instrument", "datetime")
                    ),
                    columns=column_names,
                )
            start_time = cal[0]
            end_time = cal[-1]
        data = self.dataset_processor(
            instruments_d,
            column_names,
            start_time,
            end_time,
            freq,
            inst_processors=inst_processors,
        )

        return data

    @staticmethod
    def multi_cache_walker(
        instruments, fields, start_time=None, end_time=None, freq="day"
    ):
        """
        This method is used to prepare the expression cache for the client.
        Then the client will load the data from expression cache by itself.

        """
        instruments_d = DatasetProvider.get_instruments_d(instruments, freq)
        column_names = DatasetProvider.get_column_names(fields)
        cal = Cal.calendar(start_time, end_time, freq)
        if len(cal) == 0:
            return
        start_time = cal[0]
        end_time = cal[-1]
        workers = max(min(C.kernels, len(instruments_d)), 1)

        ParallelExt(
            n_jobs=workers,
            backend=C.joblib_backend,
            maxtasksperchild=C.maxtasksperchild,
        )(
            delayed(LocalDatasetProvider.cache_walker)(
                inst, start_time, end_time, freq, column_names
            )
            for inst in instruments_d
        )

    @staticmethod
    def cache_walker(inst, start_time, end_time, freq, column_names):
        """
        If the expressions of one instrument haven't been calculated before,
        calculate it and write it into expression cache.

        """
        for field in column_names:
            ExpressionD.expression(inst, field, start_time, end_time, freq)


class ClientCalendarProvider(CalendarProvider):
    """Client calendar data provider class

    Provide calendar data by requesting data from server as a client.
    """

    def __init__(self):
        self.conn = None
        self.queue = queue.Queue()

    def set_conn(self, conn):
        self.conn = conn

    def calendar(self, start_time=None, end_time=None, freq="day", future=False):
        self.conn.send_request(
            request_type="calendar",
            request_content={
                "start_time": str(start_time),
                "end_time": str(end_time),
                "freq": freq,
                "future": future,
            },
            msg_queue=self.queue,
            msg_proc_func=lambda response_content: [
                pd.Timestamp(c) for c in response_content
            ],
        )
        result = self.queue.get(timeout=C["timeout"])
        return result


class ClientInstrumentProvider(InstrumentProvider):
    """Client instrument data provider class

    Provide instrument data by requesting data from server as a client.
    """

    def __init__(self):
        self.conn = None
        self.queue = queue.Queue()

    def set_conn(self, conn):
        self.conn = conn

    def list_instruments(
        self, instruments, start_time=None, end_time=None, freq="day", as_list=False
    ):
        def inst_msg_proc_func(response_content):
            if isinstance(response_content, dict):
                instrument = {
                    i: [(pd.Timestamp(s), pd.Timestamp(e)) for s, e in t]
                    for i, t in response_content.items()
                }
            else:
                instrument = response_content
            return instrument

        self.conn.send_request(
            request_type="instrument",
            request_content={
                "instruments": instruments,
                "start_time": str(start_time),
                "end_time": str(end_time),
                "freq": freq,
                "as_list": as_list,
            },
            msg_queue=self.queue,
            msg_proc_func=inst_msg_proc_func,
        )
        result = self.queue.get(timeout=C["timeout"])
        if isinstance(result, Exception):
            raise result
        get_module_logger("data").debug("get result")
        return result


class ClientDatasetProvider(DatasetProvider):
    """Client dataset data provider class

    Provide dataset data by requesting data from server as a client.
    """

    def __init__(self):
        self.conn = None

    def set_conn(self, conn):
        self.conn = conn
        self.queue = queue.Queue()

    def dataset(
        self,
        instruments,
        fields,
        start_time=None,
        end_time=None,
        freq="day",
        disk_cache=0,
        return_uri=False,
        inst_processors=[],
    ):
        if Inst.get_inst_type(instruments) == Inst.DICT:
            get_module_logger("data").warning(
                "Getting features from a dict of instruments is not recommended because the features will not be "
                "cached! "
                "The dict of instruments will be cleaned every day."
            )

        if disk_cache == 0:
            """
            Call the server to generate the expression cache.
            Then load the data from the expression cache directly.
            - default using multi-kernel method.

            """
            self.conn.send_request(
                request_type="feature",
                request_content={
                    "instruments": instruments,
                    "fields": fields,
                    "start_time": start_time,
                    "end_time": end_time,
                    "freq": freq,
                    "disk_cache": 0,
                },
                msg_queue=self.queue,
            )
            feature_uri = self.queue.get(timeout=C["timeout"])
            if isinstance(feature_uri, Exception):
                raise feature_uri
            else:
                instruments_d = self.get_instruments_d(instruments, freq)
                column_names = self.get_column_names(fields)
                cal = Cal.calendar(start_time, end_time, freq)
                if len(cal) == 0:
                    return pd.DataFrame(
                        index=pd.MultiIndex.from_arrays(
                            [[], []], names=("instrument", "datetime")
                        ),
                        columns=column_names,
                    )
                start_time = cal[0]
                end_time = cal[-1]

                data = self.dataset_processor(
                    instruments_d,
                    column_names,
                    start_time,
                    end_time,
                    freq,
                    inst_processors,
                )
                if return_uri:
                    return data, feature_uri
                else:
                    return data
        else:
            """
            Call the server to generate the data-set cache, get the uri of the cache file.
            Then load the data from the file on NFS directly.
            - using single-process implementation.

            """
            # TODO: support inst_processors, need to change the code of qlib-server at the same time
            # FIXME: The cache after resample, when read again and intercepted with end_time, results in incomplete data date
            if inst_processors:
                raise ValueError(
                    f"{self.__class__.__name__} does not support inst_processor. "
                    "Please use `D.features(disk_cache=0)` or `qlib.init(dataset_cache=None)`"
                )
            self.conn.send_request(
                request_type="feature",
                request_content={
                    "instruments": instruments,
                    "fields": fields,
                    "start_time": start_time,
                    "end_time": end_time,
                    "freq": freq,
                    "disk_cache": 1,
                },
                msg_queue=self.queue,
            )
            # - Done in callback
            feature_uri = self.queue.get(timeout=C["timeout"])
            if isinstance(feature_uri, Exception):
                raise feature_uri
            get_module_logger("data").debug("get result")
            try:
                # pre-mound nfs, used for demo
                mnt_feature_uri = C.dpm.get_data_uri(freq).joinpath(
                    C.dataset_cache_dir_name, feature_uri
                )
                df = DiskDatasetCache.read_data_from_cache(
                    mnt_feature_uri, start_time, end_time, fields
                )
                get_module_logger("data").debug("finish slicing data")
                if return_uri:
                    return df, feature_uri
                return df
            except AttributeError as attribute_e:
                raise IOError(
                    "Unable to fetch instruments from remote server!"
                ) from attribute_e


class BaseProvider:
    """Local provider class
    It is a set of interface that allow users to access data.
    Because PITD is not exposed publicly to users, so it is not included in the interface.

    To keep compatible with old qlib provider.
    """

    def calendar(self, start_time=None, end_time=None, freq="day", future=False):
        return Cal.calendar(start_time, end_time, freq, future=future)

    def instruments(
        self, market="all", filter_pipe=None, start_time=None, end_time=None
    ):
        if start_time is not None or end_time is not None:
            get_module_logger("Provider").warning(
                "The instruments corresponds to a stock pool. "
                "Parameters `start_time` and `end_time` does not take effect now."
            )
        return InstrumentProvider.instruments(market, filter_pipe)

    def list_instruments(
        self, instruments, start_time=None, end_time=None, freq="day", as_list=False
    ):
        return Inst.list_instruments(instruments, start_time, end_time, freq, as_list)

    def features(
        self,
        instruments,
        fields,
        start_time=None,
        end_time=None,
        freq="day",
        disk_cache=None,
        inst_processors=[],
    ):
        """
        Parameters
        ----------
        disk_cache : int
            whether to skip(0)/use(1)/replace(2) disk_cache


        This function will try to use cache method which has a keyword `disk_cache`,
        and will use provider method if a type error is raised because the DatasetD instance
        is a provider class.
        """
        disk_cache = C.default_disk_cache if disk_cache is None else disk_cache
        fields = list(fields)  # In case of tuple.
        try:
            return DatasetD.dataset(
                instruments,
                fields,
                start_time,
                end_time,
                freq,
                disk_cache,
                inst_processors=inst_processors,
            )
        except TypeError:
            return DatasetD.dataset(
                instruments,
                fields,
                start_time,
                end_time,
                freq,
                inst_processors=inst_processors,
            )


class LocalProvider(BaseProvider):
    def _uri(self, type, **kwargs):
        """_uri
        The server hope to get the uri of the request. The uri will be decided
        by the dataprovider. For ex, different cache layer has different uri.

        :param type: The type of resource for the uri
        :param **kwargs:
        """
        if type == "calendar":
            return Cal._uri(**kwargs)
        elif type == "instrument":
            return Inst._uri(**kwargs)
        elif type == "feature":
            return DatasetD._uri(**kwargs)

    def features_uri(
        self, instruments, fields, start_time, end_time, freq, disk_cache=1
    ):
        """features_uri

        Return the uri of the generated cache of features/dataset

        :param disk_cache:
        :param instruments:
        :param fields:
        :param start_time:
        :param end_time:
        :param freq:
        """
        return DatasetD._dataset_uri(
            instruments, fields, start_time, end_time, freq, disk_cache
        )


class ClientProvider(BaseProvider):
    """Client Provider

    Requesting data from server as a client. Can propose requests:

        - Calendar : Directly respond a list of calendars
        - Instruments (without filter): Directly respond a list/dict of instruments
        - Instruments (with filters):  Respond a list/dict of instruments
        - Features : Respond a cache uri

    The general workflow is described as follows:
    When the user use client provider to propose a request, the client provider will connect the server and send the request. The client will start to wait for the response. The response will be made instantly indicating whether the cache is available. The waiting procedure will terminate only when the client get the response saying `feature_available` is true.
    `BUG` : Everytime we make request for certain data we need to connect to the server, wait for the response and disconnect from it. We can't make a sequence of requests within one connection. You can refer to https://python-socketio.readthedocs.io/en/latest/client.html for documentation of python-socketIO client.
    """

    def __init__(self):
        def is_instance_of_provider(instance: object, cls: type):
            if isinstance(instance, Wrapper):
                p = getattr(instance, "_provider", None)

                return False if p is None else isinstance(p, cls)

            return isinstance(instance, cls)

        from .client import Client  # pylint: disable=C0415

        self.client = Client(C.flask_server, C.flask_port)
        self.logger = get_module_logger(self.__class__.__name__)
        if is_instance_of_provider(Cal, ClientCalendarProvider):
            Cal.set_conn(self.client)
        if is_instance_of_provider(Inst, ClientInstrumentProvider):
            Inst.set_conn(self.client)
        if hasattr(DatasetD, "provider"):
            DatasetD.provider.set_conn(self.client)
        else:
            DatasetD.set_conn(self.client)


if sys.version_info >= (3, 9):
    from typing import Annotated

    CalendarProviderWrapper = Annotated[CalendarProvider, Wrapper]
    InstrumentProviderWrapper = Annotated[InstrumentProvider, Wrapper]
    FeatureProviderWrapper = Annotated[FeatureProvider, Wrapper]
    PITProviderWrapper = Annotated[PITProvider, Wrapper]
    ExpressionProviderWrapper = Annotated[ExpressionProvider, Wrapper]
    DatasetProviderWrapper = Annotated[DatasetProvider, Wrapper]
    BaseProviderWrapper = Annotated[BaseProvider, Wrapper]
else:
    CalendarProviderWrapper = CalendarProvider
    InstrumentProviderWrapper = InstrumentProvider
    FeatureProviderWrapper = FeatureProvider
    PITProviderWrapper = PITProvider
    ExpressionProviderWrapper = ExpressionProvider
    DatasetProviderWrapper = DatasetProvider
    BaseProviderWrapper = BaseProvider

Cal: CalendarProviderWrapper = Wrapper()
Inst: InstrumentProviderWrapper = Wrapper()
FeatureD: FeatureProviderWrapper = Wrapper()
PITD: PITProviderWrapper = Wrapper()
ExpressionD: ExpressionProviderWrapper = Wrapper()
DatasetD: DatasetProviderWrapper = Wrapper()
D: BaseProviderWrapper = Wrapper()


def register_all_wrappers(C):
    """register_all_wrappers"""
    logger = get_module_logger("data")
    module = get_module_by_module_path("qlib.data")

    _calendar_provider = init_instance_by_config(C.calendar_provider, module)
    if getattr(C, "calendar_cache", None) is not None:
        _calendar_provider = init_instance_by_config(
            C.calendar_cache, module, provide=_calendar_provider
        )
    register_wrapper(Cal, _calendar_provider, "qlib.data")
    logger.debug(f"registering Cal {C.calendar_provider}-{C.calendar_cache}")

    _instrument_provider = init_instance_by_config(C.instrument_provider, module)
    register_wrapper(Inst, _instrument_provider, "qlib.data")
    logger.debug(f"registering Inst {C.instrument_provider}")

    if getattr(C, "feature_provider", None) is not None:
        feature_provider = init_instance_by_config(C.feature_provider, module)
        register_wrapper(FeatureD, feature_provider, "qlib.data")
        logger.debug(f"registering FeatureD {C.feature_provider}")

    if getattr(C, "pit_provider", None) is not None:
        pit_provider = init_instance_by_config(C.pit_provider, module)
        register_wrapper(PITD, pit_provider, "qlib.data")
        logger.debug(f"registering PITD {C.pit_provider}")

    if getattr(C, "expression_provider", None) is not None:
        # This provider is unnecessary in client provider
        _eprovider = init_instance_by_config(C.expression_provider, module)
        if getattr(C, "expression_cache", None) is not None:
            _eprovider = init_instance_by_config(
                C.expression_cache, module, provider=_eprovider
            )
        register_wrapper(ExpressionD, _eprovider, "qlib.data")
        logger.debug(
            f"registering ExpressionD {C.expression_provider}-{C.expression_cache}"
        )

    _dprovider = init_instance_by_config(C.dataset_provider, module)
    if getattr(C, "dataset_cache", None) is not None:
        _dprovider = init_instance_by_config(
            C.dataset_cache, module, provider=_dprovider
        )
    register_wrapper(DatasetD, _dprovider, "qlib.data")
    logger.debug(f"registering DatasetD {C.dataset_provider}-{C.dataset_cache}")

    register_wrapper(D, C.provider, "qlib.data")
    logger.debug(f"registering D {C.provider}")
