"""
TuShare API客户端

封装TuShare API的调用逻辑，提供统一的接口和错误处理、重试机制、频率限制等功能。

主要功能：
- API连接管理
- 请求重试机制
- 频率限制控制
- 错误处理和日志
- 数据获取封装
"""

import time
import requests
import pandas as pd
from typing import Dict, Any, Optional, List, Callable
from collections import deque
from datetime import datetime, timedelta
import threading
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from .config import TuShareConfig
from .exceptions import TuShareAPIError, TuShareConfigError
from .field_mapping import TuShareFieldMapping


class TuShareRateLimiter:
    """
    TuShare API频率限制器

    控制API调用频率，避免触发服务端限制。
    """

    def __init__(self, max_requests: int, time_window: int):
        """
        初始化频率限制器

        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口长度（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = threading.Lock()

    def acquire(self) -> float:
        """
        获取请求许可

        如果超过频率限制，会等待直到可以发送请求。

        Returns:
            等待时间（秒）
        """
        with self.lock:
            now = time.time()

            # 清理过期的请求记录
            while self.requests and self.requests[0] <= now - self.time_window:
                self.requests.popleft()

            # 检查是否超过限制
            if len(self.requests) >= self.max_requests:
                # 计算需要等待的时间
                wait_time = self.requests[0] + self.time_window - now
                if wait_time > 0:
                    time.sleep(wait_time)
                    now = time.time()
                    # 重新清理过期记录
                    while self.requests and self.requests[0] <= now - self.time_window:
                        self.requests.popleft()

            # 记录当前请求
            self.requests.append(now)
            return 0.0


class TuShareAPIClient:
    """
    TuShare API客户端

    提供TuShare API的调用接口，包含重试机制、频率限制、错误处理等功能。
    """

    def __init__(self, config: TuShareConfig):
        """
        初始化API客户端

        Args:
            config: TuShare配置对象
        """
        self.config = config
        self.session = self._create_session()
        self.rate_limiter = TuShareRateLimiter(
            config.rate_limit, config.rate_limit_window
        )
        self._last_request_time = 0

        # 验证配置
        self._validate_config()

    def _validate_config(self) -> None:
        """
        验证配置参数

        Raises:
            TuShareConfigError: 当配置无效时
        """
        if not self.config.token:
            raise TuShareConfigError(
                "TuShare Token未配置，请设置TUSHARE_TOKEN环境变量或在配置中指定token",
                config_key="token"
            )

    def _create_session(self) -> requests.Session:
        """
        创建HTTP会话

        Returns:
            配置好的requests.Session对象
        """
        session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # 设置默认超时
        session.timeout = self.config.timeout

        return session

    def _prepare_request_params(self, api_name: str, params: Dict[str, Any], fields: str = None) -> Dict[str, Any]:
        """
        准备请求参数（TuShare HTTP API格式）

        TuShare HTTP API请求格式：
        {
            "api_name": "接口名称",
            "token": "用户Token",
            "params": {"参数名": "参数值"},
            "fields": "字段列表（可选）"
        }

        Args:
            api_name: API接口名称
            params: 接口参数（将放入params字段）
            fields: 字段列表（可选）

        Returns:
            处理后的TuShare HTTP API请求体
        """
        # 构建TuShare标准请求格式
        request_body = {
            "api_name": api_name,
            "token": self.config.token,
            "params": params
        }

        # 添加fields参数（如果提供）
        if fields:
            request_body["fields"] = fields

        # 移除params中的None值
        request_body["params"] = {k: v for k, v in params.items() if v is not None}

        return request_body

    def _make_request(self, api_name: str, params: Dict[str, Any], fields: str = None) -> Dict[str, Any]:
        """
        发送API请求（TuShare HTTP API格式）

        Args:
            api_name: API接口名称（如'stock_basic', 'daily'等）
            params: 接口参数（将放入params字段）
            fields: 字段列表（可选，将作为顶级字段）

        Returns:
            API响应数据

        Raises:
            TuShareAPIError: 当API调用失败时
        """
        # 频率限制
        wait_time = self.rate_limiter.acquire()
        if wait_time > 0 and self.config.enable_api_logging:
            print(f"[TuShare] 频率限制等待 {wait_time:.2f} 秒")

        # 准备TuShare标准请求格式
        request_body = self._prepare_request_params(api_name, params, fields)

        # 使用基础URL（不包含接口名路径）
        url = self.config.api_url

        try:
            if self.config.enable_api_logging:
                print(f"[TuShare] 请求: {api_name}, URL: {url}, 参数: {request_body}")

            # 发送POST请求到基础URL
            response = self.session.post(url, json=request_body)
            response.raise_for_status()

            # 解析响应
            data = response.json()

            # 检查API响应状态
            if data.get("code") != 0:
                raise TuShareAPIError(
                    f"API返回错误: {data.get('msg', '未知错误')}",
                    status_code=response.status_code,
                    api_method=api_name,
                    request_params=request_body,
                    details={"response_code": data.get("code")}
                )

            result_data = data.get("data", {})

            if self.config.enable_api_logging:
                print(f"[TuShare] 响应: {api_name}, 数据量: {len(result_data) if isinstance(result_data, dict) else 0}")

            self._last_request_time = time.time()
            return result_data

        except requests.exceptions.RequestException as e:
            raise TuShareAPIError(
                f"网络请求失败: {str(e)}",
                api_method=api_name,
                request_params=request_body,
                cause=e
            )
        except Exception as e:
            raise TuShareAPIError(
                f"API调用失败: {str(e)}",
                api_method=api_name,
                request_params=request_body,
                cause=e
            )

    def get_daily_data(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        adj: str = None
    ) -> pd.DataFrame:
        """
        获取股票日线数据

        Args:
            ts_code: 股票代码（格式：000001.SZ）
            start_date: 开始日期（格式：20240101）
            end_date: 结束日期（格式：20241231）
            adj: 复权类型 ('qfq': 前复权, 'hfq': 后复权, None: 不复权)

        Returns:
            日线数据DataFrame

        Raises:
            TuShareAPIError: 当API调用失败时
        """
        params = {
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date,
        }

        if adj:
            params["adj"] = adj

        data = self._make_request("daily", params)

        if data:
            # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
            if isinstance(data, dict) and 'fields' in data and 'items' in data:
                # 使用fields作为列名，items作为数据行
                df = pd.DataFrame(data['items'], columns=data['fields'])
            else:
                # 兼容其他可能的格式
                df = pd.DataFrame(data)

            # 字段映射和类型转换
            df = TuShareFieldMapping.map_dataframe_columns(df)
            df = TuShareFieldMapping.convert_data_types(df)

            # 确保数据按日期排序
            if "date" in df.columns:
                df = df.sort_values("date").reset_index(drop=True)

            return df
        else:
            return pd.DataFrame()

    def get_trade_cal(
        self,
        exchange: str = "SSE",
        start_date: str = None,
        end_date: str = None,
        is_open: str = None
    ) -> pd.DataFrame:
        """
        获取交易日历

        Args:
            exchange: 交易所代码 (SSE上交所, SZSE深交所)
            start_date: 开始日期
            end_date: 结束日期
            is_open: 是否开放 ('1': 是, '0': 否)

        Returns:
            交易日历DataFrame
        """
        params = {
            "exchange": exchange,
        }

        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if is_open:
            params["is_open"] = is_open

        data = self._make_request("trade_cal", params)

        if data:
            # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
            if isinstance(data, dict) and 'fields' in data and 'items' in data:
                # 使用fields作为列名，items作为数据行
                df = pd.DataFrame(data['items'], columns=data['fields'])
            else:
                # 兼容其他可能的格式
                df = pd.DataFrame(data)

            # 字段映射和类型转换
            df = TuShareFieldMapping.convert_data_types(df)

            # 确保数据按日期排序
            if "date" in df.columns:
                df = df.sort_values("date").reset_index(drop=True)

            return df
        else:
            return pd.DataFrame()

    def get_stock_basic(
        self,
        exchange: str = None,
        list_status: str = "L",
        fields: str = None
    ) -> pd.DataFrame:
        """
        获取股票基本信息

        Args:
            exchange: 交易所代码
            list_status: 上市状态 (L: 上市, D: 退市, P: 暂停)
            fields: 字段列表

        Returns:
            股票基本信息DataFrame
        """
        # params参数（将放入请求体的params字段）
        params = {
            "list_status": list_status,
        }

        if exchange:
            params["exchange"] = exchange

        # fields作为顶级参数传递
        data = self._make_request("stock_basic", params, fields=fields)

        if data:
            try:
                # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
                if isinstance(data, dict) and 'fields' in data and 'items' in data:
                    # 使用fields作为列名，items作为数据行
                    df = pd.DataFrame(data['items'], columns=data['fields'])
                else:
                    # 兼容其他可能的格式
                    df = pd.DataFrame(data)

                # 字段映射和类型转换
                df = TuShareFieldMapping.map_dataframe_columns(df)
                df = TuShareFieldMapping.convert_data_types(df)

                return df
            except Exception as e:
                # 输出详细的调试信息
                print(f"⚠️ 处理stock_basic数据时出错: {e}")
                print(f"   原始数据类型: {type(data)}")
                if isinstance(data, dict):
                    print(f"   数据键: {list(data.keys())}")
                    if 'fields' in data:
                        print(f"   字段: {data['fields']}")
                    if 'items' in data:
                        print(f"   数据项数量: {len(data['items'])}")
                        if data['items']:
                            print(f"   第一行: {data['items'][0]}")
                raise
        else:
            return pd.DataFrame()

    def get_daily_basic(
        self,
        ts_code: str = None,
        trade_date: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> pd.DataFrame:
        """
        获取股票每日基本面数据

        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            每日基本面数据DataFrame
        """
        params = {}

        if ts_code:
            params["ts_code"] = ts_code
        if trade_date:
            params["trade_date"] = trade_date
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data = self._make_request("daily_basic", params)

        if data:
            # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
            if isinstance(data, dict) and 'fields' in data and 'items' in data:
                # 使用fields作为列名，items作为数据行
                df = pd.DataFrame(data['items'], columns=data['fields'])
            else:
                # 兼容其他可能的格式
                df = pd.DataFrame(data)

            # 字段映射和类型转换
            df = TuShareFieldMapping.map_dataframe_columns(df)
            df = TuShareFieldMapping.convert_data_types(df)

            return df
        else:
            return pd.DataFrame()

    def get_index_daily(
        self,
        ts_code: str = None,
        trade_date: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> pd.DataFrame:
        """
        获取指数日线数据

        Args:
            ts_code: 指数代码
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            指数日线数据DataFrame
        """
        params = {}

        if ts_code:
            params["ts_code"] = ts_code
        if trade_date:
            params["trade_date"] = trade_date
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data = self._make_request("index_daily", params)

        if data:
            # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
            if isinstance(data, dict) and 'fields' in data and 'items' in data:
                # 使用fields作为列名，items作为数据行
                df = pd.DataFrame(data['items'], columns=data['fields'])
            else:
                # 兼容其他可能的格式
                df = pd.DataFrame(data)

            # 字段映射和类型转换
            df = TuShareFieldMapping.map_dataframe_columns(df)
            df = TuShareFieldMapping.convert_data_types(df)

            return df
        else:
            return pd.DataFrame()

    def get_index_weight(
        self,
        index_code: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> pd.DataFrame:
        """
        获取指数成分股权重

        Args:
            index_code: 指数代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            指数权重数据DataFrame
        """
        params = {}

        if index_code:
            params["index_code"] = index_code
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data = self._make_request("index_weight", params)

        if data:
            # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
            if isinstance(data, dict) and 'fields' in data and 'items' in data:
                # 使用fields作为列名，items作为数据行
                df = pd.DataFrame(data['items'], columns=data['fields'])
            else:
                # 兼容其他可能的格式
                df = pd.DataFrame(data)

            # 字段映射和类型转换
            df = TuShareFieldMapping.map_dataframe_columns(df)
            df = TuShareFieldMapping.convert_data_types(df)

            return df
        else:
            return pd.DataFrame()

    def get_industry(
        self,
        src: str = "SW2021",
        level: str = "L1",
        fields: str = None
    ) -> pd.DataFrame:
        """
        获取行业分类数据

        Args:
            src: 行业分类来源
                  - SW2021: 申万2021行业分类
                  - SW: 申万行业分类（旧版）
                  - ZJH: 证监会行业分类
                  - CITIC: 中信行业分类
            level: 行业级别
                   - L1: 一级行业
                   - L2: 二级行业
                   - L3: 三级行业
            fields: 字段列表（可选）

        Returns:
            行业分类数据DataFrame，包含字段：
            - industry_code: 行业代码
            - industry_name: 行业名称
            - level: 行业级别
            - is_parent: 是否为父类
        """
        params = {
            "src": src,
            "level": level
        }

        data = self._make_request("industry", params, fields=fields)

        if data:
            # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
            if isinstance(data, dict) and 'fields' in data and 'items' in data:
                df = pd.DataFrame(data['items'], columns=data['fields'])
            else:
                df = pd.DataFrame(data)

            # 字段映射和类型转换
            df = TuShareFieldMapping.convert_data_types(df)

            return df
        else:
            return pd.DataFrame()

    def get_concept(
        self,
        id: str = None,
        fields: str = None
    ) -> pd.DataFrame:
        """
        获取概念板块分类数据

        Args:
            id: 概念板块ID（可选）
            fields: 字段列表（可选）

        Returns:
            概念板块数据DataFrame，包含字段：
            - id: 概念ID
            - concept_name: 概念名称
            - concept_type: 概念类型
        """
        params = {}

        if id:
            params["id"] = id

        data = self._make_request("concept", params, fields=fields)

        if data:
            # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
            if isinstance(data, dict) and 'fields' in data and 'items' in data:
                df = pd.DataFrame(data['items'], columns=data['fields'])
            else:
                df = pd.DataFrame(data)

            # 字段映射和类型转换
            df = TuShareFieldMapping.convert_data_types(df)

            return df
        else:
            return pd.DataFrame()

    def get_index_member(
        self,
        index_code: str = None,
        fields: str = None
    ) -> pd.DataFrame:
        """
        获取指数成分股数据

        Args:
            index_code: 指数代码（如 000300.SH 沪深300）
            fields: 字段列表（可选）

        Returns:
            指数成分股数据DataFrame，包含字段：
            - index_code: 指数代码
            - con_code: 成分股代码
            - in_date: 纳入日期
            - out_date: 剔除日期
            - is_new: 是否为新成分股
        """
        params = {}

        if index_code:
            params["index_code"] = index_code

        data = self._make_request("index_member", params, fields=fields)

        if data:
            # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
            if isinstance(data, dict) and 'fields' in data and 'items' in data:
                df = pd.DataFrame(data['items'], columns=data['fields'])
            else:
                df = pd.DataFrame(data)

            # 字段映射和类型转换
            df = TuShareFieldMapping.convert_data_types(df)

            return df
        else:
            return pd.DataFrame()

    def get_index_classify(
        self,
        level: str = "L1",
        src: str = "SW2021",
        fields: str = None
    ) -> pd.DataFrame:
        """
        获取指数行业分类数据

        Args:
            level: 行业级别 (L1: 一级, L2: 二级, L3: 三级)
            src: 行业分类来源 (SW2021, ZJH, CITIC)
            fields: 字段列表（可选）

        Returns:
            指数行业分类DataFrame，包含：
            - index_code: 指数代码
            - industry_code: 行业代码
            - industry_name: 行业名称
        """
        params = {
            "level": level,
            "src": src
        }

        data = self._make_request("index_classify", params, fields=fields)

        if data:
            # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
            if isinstance(data, dict) and 'fields' in data and 'items' in data:
                df = pd.DataFrame(data['items'], columns=data['fields'])
            else:
                df = pd.DataFrame(data)

            # 字段映射和类型转换
            df = TuShareFieldMapping.convert_data_types(df)

            return df
        else:
            return pd.DataFrame()

    def get_industry_detail(
        self,
        industry_code: str = None,
        fields: str = None
    ) -> pd.DataFrame:
        """
        获取行业板块详细信息

        Args:
            industry_code: 行业代码（可选）
            fields: 字段列表（可选）

        Returns:
            行业详细信息DataFrame
        """
        params = {}

        if industry_code:
            params["industry_code"] = industry_code

        data = self._make_request("industry_detail", params, fields=fields)

        if data:
            # TuShare API返回格式: {'fields': [...], 'items': [[...], [...]]}
            if isinstance(data, dict) and 'fields' in data and 'items' in data:
                df = pd.DataFrame(data['items'], columns=data['fields'])
            else:
                df = pd.DataFrame(data)

            # 字段映射和类型转换
            df = TuShareFieldMapping.convert_data_types(df)

            return df
        else:
            return pd.DataFrame()

    def close(self) -> None:
        """
        关闭API客户端

        清理资源，关闭HTTP会话。
        """
        if self.session:
            self.session.close()

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()