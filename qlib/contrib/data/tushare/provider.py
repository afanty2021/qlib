"""
TuShare数据源提供者

实现Qlib数据源接口，提供完整的TuShare数据源集成。

主要功能：
- 实现Qlib数据提供者接口
- 提供交易日历数据
- 提供股票列表数据
- 提供特征数据
- 提供表达式数据
"""

import time
import pandas as pd
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path

from qlib.data.data import BaseProvider
from qlib.data.dataset import DatasetH
from qlib.data.cache import H

from .config import TuShareConfig
from .api_client import TuShareAPIClient
from .cache import TuShareCacheManager
from .utils import (
    TuShareDataProcessor,
    TuShareCodeConverter,
    TuShareDateUtils,
    TuShareMarketUtils
)
from .field_mapping import TuShareFieldMapping
from .exceptions import TuShareError, TuShareAPIError, TuShareDataError

try:
    from ..log import get_module_logger
    logger = get_module_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TuShareProvider(BaseProvider):
    """
    TuShare数据提供者

    实现Qlib数据源接口，提供TuShare数据源的数据访问功能。
    """

    def __init__(self, config: TuShareConfig, **kwargs):
        """
        初始化TuShare数据提供者

        Args:
            config: TuShare配置对象
            **kwargs: 其他参数
        """
        super().__init__(**kwargs)
        self.config = config

        # 初始化API客户端
        self.api_client = TuShareAPIClient(config)

        # 初始化缓存管理器
        self.cache_manager = TuShareCacheManager(config)

        # 缓存交易日历
        self._calendar_cache = None
        self._instruments_cache = None

        logger.info("TuShare数据提供者初始化完成")

    def calendar(self, start_time=None, end_time=None, freq="day", future=False) -> List[pd.Timestamp]:
        """
        获取交易日历

        Args:
            start_time: 开始时间
            end_time: 结束时间
            freq: 频率
            future: 是否包含未来日期

        Returns:
            交易日历列表
        """
        try:
            # 转换日期格式
            if start_time:
                start_date = TuShareDateUtils.to_tushare_date(start_time)
            else:
                start_date = "20000101"  # 默认开始日期

            if end_time:
                end_date = TuShareDateUtils.to_tushare_date(end_time)
            else:
                end_date = "20991231"  # 默认结束日期

            # 生成缓存键
            cache_key = self.cache_manager.generate_key(
                "calendar", start_date, end_date, freq, future
            )

            # 尝试从缓存获取
            cached_data = self.cache_manager.get(cache_key)
            if cached_data is not None:
                return cached_data

            # 从API获取交易日历
            trading_cal = self.api_client.get_trade_cal(
                start_date=start_date,
                end_date=end_date,
                is_open="1"  # 只获取开放交易日
            )

            if trading_cal.empty:
                return []

            # 转换为Timestamp列表
            trading_dates = [
                pd.Timestamp(date) for date in trading_cal["date"]
            ]

            # 按时间排序
            trading_dates.sort()

            # 缓存结果
            self.cache_manager.set(cache_key, trading_dates)

            return trading_dates

        except Exception as e:
            logger.error(f"获取交易日历失败: {str(e)}")
            return []

    def instruments(self, market="all", filters=None) -> Dict[str, Any]:
        """
        获取股票列表

        Args:
            market: 市场类型
            filters: 过滤条件

        Returns:
            股票列表字典
        """
        try:
            # 生成缓存键
            cache_key = self.cache_manager.generate_key("instruments", market, filters)

            # 尝试从缓存获取
            cached_data = self.cache_manager.get(cache_key)
            if cached_data is not None:
                return cached_data

            # 获取股票基本信息
            stock_basic = self.api_client.get_stock_basic(
                list_status="L",  # 只获取上市股票
                fields="ts_code,symbol,name,area,industry,market,list_date"
            )

            if stock_basic.empty:
                return {}

            # 转换为Qlib格式
            instruments = {}

            for _, row in stock_basic.iterrows():
                ts_code = row["instrument"]
                qlib_code = TuShareCodeConverter.to_qlib_format(ts_code)

                instruments[qlib_code] = {
                    "code": qlib_code,
                    "name": row["name"],
                    "market": row["market"],
                    "sector": row.get("industry", ""),
                    "industry": row.get("industry", ""),
                    "list_date": row.get("list_date", ""),
                    "type": "stock"
                }

            # 应用过滤条件
            if filters:
                instruments = self._apply_instrument_filters(instruments, filters)

            # 缓存结果
            self.cache_manager.set(cache_key, instruments)

            return instruments

        except Exception as e:
            logger.error(f"获取股票列表失败: {str(e)}")
            return {}

    def _apply_instrument_filters(self, instruments: Dict[str, Any], filters: List[str]) -> Dict[str, Any]:
        """
        应用股票过滤条件

        Args:
            instruments: 股票列表
            filters: 过滤条件列表

        Returns:
            过滤后的股票列表
        """
        if not filters:
            return instruments

        filtered_instruments = {}

        for code, info in instruments.items():
            include = True

            for filter_str in filters:
                # 简单的字符串匹配过滤
                if filter_str.startswith("market="):
                    market = filter_str.split("=", 1)[1]
                    if info["market"] != market:
                        include = False
                        break
                elif filter_str.startswith("sector="):
                    sector = filter_str.split("=", 1)[1]
                    if sector not in info.get("sector", ""):
                        include = False
                        break
                elif filter_str.startswith("industry="):
                    industry = filter_str.split("=", 1)[1]
                    if industry not in info.get("industry", ""):
                        include = False
                        break

            if include:
                filtered_instruments[code] = info

        return filtered_instruments

    def feature(self, instrument, field, start_time=None, end_time=None, freq="day") -> pd.Series:
        """
        获取单个特征数据

        Args:
            instrument: 股票代码
            field: 字段名
            start_time: 开始时间
            end_time: 结束时间
            freq: 频率

        Returns:
            特征数据Series
        """
        try:
            # 转换股票代码格式
            tushare_code = TuShareCodeConverter.to_tushare_format(instrument)

            # 转换日期格式
            if start_time:
                start_date = TuShareDateUtils.to_tushare_date(start_time)
            else:
                start_date = "20200101"  # 默认开始日期

            if end_time:
                end_date = TuShareDateUtils.to_tushare_date(end_time)
            else:
                end_date = "20991231"  # 默认结束日期

            # 转换字段名
            tushare_field = TuShareFieldMapping.get_tushare_field(field)
            if not tushare_field:
                # 如果没有映射关系，使用原始字段名
                tushare_field = field

            # 生成缓存键
            cache_key = self.cache_manager.generate_key(
                "feature", tushare_code, tushare_field, start_date, end_date, freq
            )

            # 尝试从缓存获取
            cached_data = self.cache_manager.get(cache_key)
            if cached_data is not None:
                return cached_data

            # 从API获取数据
            daily_data = self.api_client.get_daily_data(
                ts_code=tushare_code,
                start_date=start_date,
                end_date=end_date,
                adj="qfq" if self.config.adjust_price else None
            )

            if daily_data.empty or tushare_field not in daily_data.columns:
                return pd.Series(dtype=float)

            # 获取特征数据
            feature_data = daily_data.set_index("date")[tushare_field]

            # 重命名索引为日期格式
            feature_data.index = pd.to_datetime(feature_data.index)

            # 数据验证和清洗
            if self.config.validate_data:
                is_valid, errors = TuShareDataProcessor.validate_trading_data(
                    daily_data[[tushare_field]].to_frame()
                )
                if not is_valid:
                    logger.warning(f"数据验证失败: {errors}")

            # 缓存结果
            self.cache_manager.set(cache_key, feature_data)

            return feature_data

        except Exception as e:
            logger.error(f"获取特征数据失败: {instrument}.{field}, 错误: {str(e)}")
            return pd.Series(dtype=float)

    def features(self, instruments, fields, start_time=None, end_time=None, freq="day") -> pd.DataFrame:
        """
        获取多个特征数据

        Args:
            instruments: 股票代码列表
            fields: 字段名列表
            start_time: 开始时间
            end_time: 结束时间
            freq: 频率

        Returns:
            特征数据DataFrame
        """
        try:
            # 转换日期格式
            if start_time:
                start_date = TuShareDateUtils.to_tushare_date(start_time)
            else:
                start_date = "20200101"

            if end_time:
                end_date = TuShareDateUtils.to_tushare_date(end_time)
            else:
                end_date = "20991231"

            # 生成缓存键
            cache_key = self.cache_manager.generate_key(
                "features", tuple(instruments), tuple(fields), start_date, end_date, freq
            )

            # 尝试从缓存获取
            cached_data = self.cache_manager.get(cache_key)
            if cached_data is not None:
                return cached_data

            # 初始化结果DataFrame
            all_data = []

            # 批量获取数据
            for instrument in instruments:
                try:
                    # 转换股票代码
                    tushare_code = TuShareCodeConverter.to_tushare_format(instrument)

                    # 从API获取数据
                    daily_data = self.api_client.get_daily_data(
                        ts_code=tushare_code,
                        start_date=start_date,
                        end_date=end_date,
                        adj="qfq" if self.config.adjust_price else None
                    )

                    if daily_data.empty:
                        continue

                    # 添加股票代码列
                    daily_data["instrument"] = instrument

                    # 转换字段名
                    daily_data = TuShareFieldMapping.map_dataframe_columns(daily_data)

                    all_data.append(daily_data)

                except Exception as e:
                    logger.warning(f"获取股票数据失败: {instrument}, 错误: {str(e)}")
                    continue

            if not all_data:
                return pd.DataFrame()

            # 合并所有数据
            merged_data = pd.concat(all_data, ignore_index=True)

            # 数据验证和清洗
            if self.config.validate_data:
                merged_data = TuShareDataProcessor.clean_trading_data(merged_data)

            # 重构为MultiIndex格式
            if not merged_data.empty:
                # 筛选需要的字段
                available_fields = [field for field in fields if field in merged_data.columns]
                if available_fields:
                    result_data = merged_data[["instrument", "date"] + available_fields]

                    # 设置MultiIndex
                    result_data = result_data.set_index(["instrument", "date"])
                    result_data = result_data.sort_index()

                    # 缓存结果
                    self.cache_manager.set(cache_key, result_data)

                    return result_data

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"批量获取特征数据失败: {str(e)}")
            return pd.DataFrame()

    def expression(self, instrument, expression, start_time=None, end_time=None, freq="day") -> pd.Series:
        """
        获取表达式计算结果

        注意：目前不支持复杂的表达式计算，建议使用Qlib的表达式引擎

        Args:
            instrument: 股票代码
            expression: 表达式字符串
            start_time: 开始时间
            end_time: 结束时间
            freq: 频率

        Returns:
            计算结果Series
        """
        logger.warning("TuShareProvider不支持表达式计算，请使用Qlib表达式引擎")
        return pd.Series(dtype=float)

    def dataset(self, instruments, fields, start_time=None, end_time=None, freq="day",
                inst_processors=None) -> DatasetH:
        """
        获取数据集

        Args:
            instruments: 股票代码列表
            fields: 字段名列表
            start_time: 开始时间
            end_time: 结束时间
            freq: 频率
            inst_processors: 处理器

        Returns:
            数据集对象
        """
        try:
            # 获取特征数据
            features_df = self.features(
                instruments=instruments,
                fields=fields,
                start_time=start_time,
                end_time=end_time,
                freq=freq
            )

            if features_df.empty:
                return DatasetH(pd.DataFrame(), pd.DataFrame())

            # 转换为DatasetH格式
            df = features_df.reset_index()
            df["datetime"] = df["date"]

            # 创建数据集
            dataset = DatasetH(df)

            return dataset

        except Exception as e:
            logger.error(f"获取数据集失败: {str(e)}")
            return DatasetH(pd.DataFrame(), pd.DataFrame())

    def get_industry_classification(
        self,
        src: str = "SW2021",
        level: str = "L1"
    ) -> pd.DataFrame:
        """
        获取行业分类数据

        Args:
            src: 行业分类来源 (SW2021, ZJH, CITIC)
            level: 行业级别 (L1, L2, L3)

        Returns:
            行业分类DataFrame
        """
        try:
            # 生成缓存键
            cache_key = self.cache_manager.generate_key("industry", src, level)

            # 尝试从缓存获取
            cached_data = self.cache_manager.get(cache_key)
            if cached_data is not None:
                return cached_data

            # 从API获取行业分类
            industry_data = self.api_client.get_industry(src=src, level=level)

            if industry_data.empty:
                logger.warning(f"获取行业分类数据为空: src={src}, level={level}")
                return pd.DataFrame()

            # 缓存结果
            self.cache_manager.set(cache_key, industry_data)

            return industry_data

        except Exception as e:
            logger.error(f"获取行业分类失败: {str(e)}")
            return pd.DataFrame()

    def get_concept_classification(self, id: str = None) -> pd.DataFrame:
        """
        获取概念板块分类数据

        Args:
            id: 概念板块ID（可选）

        Returns:
            概念板块分类DataFrame
        """
        try:
            # 生成缓存键
            cache_key = self.cache_manager.generate_key("concept", id)

            # 尝试从缓存获取
            cached_data = self.cache_manager.get(cache_key)
            if cached_data is not None:
                return cached_data

            # 从API获取概念分类
            concept_data = self.api_client.get_concept(id=id)

            if concept_data.empty:
                logger.warning(f"获取概念板块数据为空: id={id}")
                return pd.DataFrame()

            # 缓存结果
            self.cache_manager.set(cache_key, concept_data)

            return concept_data

        except Exception as e:
            logger.error(f"获取概念板块失败: {str(e)}")
            return pd.DataFrame()

    def get_industry_members(
        self,
        index_code: str = None
    ) -> pd.DataFrame:
        """
        获取指数成分股数据

        Args:
            index_code: 指数代码（如 000300.SH 沪深300）

        Returns:
            指数成分股DataFrame
        """
        try:
            # 生成缓存键
            cache_key = self.cache_manager.generate_key("index_member", index_code)

            # 尝试从缓存获取
            cached_data = self.cache_manager.get(cache_key)
            if cached_data is not None:
                return cached_data

            # 从API获取指数成分股
            member_data = self.api_client.get_index_member(index_code=index_code)

            if member_data.empty:
                logger.warning(f"获取指数成分股数据为空: index_code={index_code}")
                return pd.DataFrame()

            # 缓存结果
            self.cache_manager.set(cache_key, member_data)

            return member_data

        except Exception as e:
            logger.error(f"获取指数成分股失败: {str(e)}")
            return pd.DataFrame()

    def get_industry_factors(
        self,
        instruments: List[str],
        factor_type: str = "momentum",
        start_time=None,
        end_time=None,
        **kwargs
    ) -> pd.DataFrame:
        """
        获取行业因子数据

        Args:
            instruments: 股票代码列表
            factor_type: 因子类型
                        - "momentum": 行业动量
                        - "relative_strength": 行业相对强度
                        - "concentration": 行业集中度
                        - "pe_ratio": 行业市盈率
            start_time: 开始时间
            end_time: 结束时间
            **kwargs: 其他因子参数

        Returns:
            行业因子DataFrame
        """
        try:
            from .industry_factors import IndustryFactorCalculator

            # 获取行业分类数据
            industry_data = self.get_industry_classification()

            if industry_data.empty:
                logger.warning("行业分类数据为空，无法计算因子")
                return pd.DataFrame()

            # 获取价格数据
            price_df = self.features(
                instruments=instruments,
                fields=["close", "volume"],
                start_time=start_time,
                end_time=end_time,
                freq="day"
            )

            if price_df.empty:
                logger.warning("价格数据为空，无法计算因子")
                return pd.DataFrame()

            # 转换为因子计算器需要的格式
            price_df_reset = price_df.reset_index()
            price_df_reset.columns = ['instrument', 'date', 'close', 'volume']

            # 初始化因子计算器
            calculator = IndustryFactorCalculator(
                industry_data=industry_data,
                price_data=price_df_reset,
                industry_classification="SW2021"
            )

            # 根据因子类型计算
            if factor_type == "momentum":
                factor_df = calculator.calculate_industry_momentum(
                    window=kwargs.get("window", 20),
                    method=kwargs.get("method", "return")
                )
            elif factor_type == "relative_strength":
                factor_df = calculator.calculate_industry_relative_strength(
                    benchmark=kwargs.get("benchmark", "market"),
                    window=kwargs.get("window", 20)
                )
            elif factor_type == "concentration":
                holdings = kwargs.get("holdings")
                if holdings is None:
                    raise ValueError("计算集中度因子需要提供holdings参数")
                factor_df = calculator.calculate_industry_concentration(holdings=holdings)
            elif factor_type == "pe_ratio":
                fundamental_data = kwargs.get("fundamental_data")
                if fundamental_data is None:
                    raise ValueError("计算PE因子需要提供fundamental_data参数")
                factor_df = calculator.calculate_industry_pe_ratio(
                    fundamental_data=fundamental_data,
                    method=kwargs.get("method", "median")
                )
            else:
                raise ValueError(f"不支持的因子类型: {factor_type}")

            return factor_df

        except Exception as e:
            logger.error(f"获取行业因子失败: {str(e)}")
            return pd.DataFrame()

    def features_with_industry(
        self,
        instruments: List[str],
        fields: List[str],
        start_time=None,
        end_time=None,
        freq: str = "day",
        include_industry: bool = True
    ) -> pd.DataFrame:
        """
        获取包含行业信息的特征数据

        与标准features方法的区别是会自动添加行业分类信息。

        Args:
            instruments: 股票代码列表
            fields: 特征字段列表
            start_time: 开始时间
            end_time: 结束时间
            freq: 频率
            include_industry: 是否包含行业信息

        Returns:
            特征数据DataFrame（包含行业列）
        """
        try:
            # 获取标准特征数据
            features_df = self.features(
                instruments=instruments,
                fields=fields,
                start_time=start_time,
                end_time=end_time,
                freq=freq
            )

            if features_df.empty:
                return features_df

            # 如果不需要行业信息，直接返回
            if not include_industry:
                return features_df

            # 获取行业分类
            industry_data = self.get_industry_classification()

            if industry_data.empty:
                logger.warning("无法获取行业分类数据")
                return features_df

            # 映射股票代码
            industry_map = {}
            for _, row in industry_data.iterrows():
                if 'instrument' in row:
                    qlib_code = row['instrument']
                    if 'industry_name' in row:
                        industry_map[qlib_code] = row['industry_name']

            # 添加行业信息
            features_with_industry = features_df.copy()
            features_with_industry['industry'] = features_with_industry.index.get_level_values(0).map(industry_map)

            return features_with_industry

        except Exception as e:
            logger.error(f"获取行业特征数据失败: {str(e)}")
            return self.features(
                instruments=instruments,
                fields=fields,
                start_time=start_time,
                end_time=end_time,
                freq=freq
            )

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计字典
        """
        return self.cache_manager.get_stats()

    def clear_cache(self, level: str = "all") -> None:
        """
        清空缓存

        Args:
            level: 缓存级别 ("memory", "disk", "all")
        """
        self.cache_manager.clear(level)

    def close(self) -> None:
        """
        关闭数据提供者

        清理资源，关闭连接。
        """
        if self.api_client:
            self.api_client.close()

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()