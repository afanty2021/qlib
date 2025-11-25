"""
TuShare数据处理工具

提供TuShare数据源的数据处理、验证、转换等工具函数。

主要功能：
- 数据格式转换和标准化
- 数据质量检查和清洗
- 交易日历处理
- 股票代码转换
- 日期处理和格式化
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
import re

from .field_mapping import TuShareFieldMapping
from .exceptions import TuShareDataError


class TuShareDataProcessor:
    """
    TuShare数据处理器

    提供数据清洗、验证、转换等处理功能。
    """

    @staticmethod
    def validate_trading_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        验证交易数据的完整性和有效性

        Args:
            df: 交易数据DataFrame

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        # 检查数据是否为空
        if df.empty:
            errors.append("数据为空")
            return False, errors

        # 检查必需字段
        required_fields = ["date", "open", "high", "low", "close", "volume"]
        missing_fields = [field for field in required_fields if field not in df.columns]
        if missing_fields:
            errors.append(f"缺少必需字段: {missing_fields}")

        # 检查数据类型
        numeric_fields = ["open", "high", "low", "close", "volume"]
        for field in numeric_fields:
            if field in df.columns and not pd.api.types.is_numeric_dtype(df[field]):
                errors.append(f"字段 {field} 不是数值类型")

        # 检查价格合理性
        price_fields = ["open", "high", "low", "close"]
        for field in price_fields:
            if field in df.columns:
                invalid_prices = df[df[field] <= 0]
                if len(invalid_prices) > 0:
                    errors.append(f"字段 {field} 存在非正价格: {len(invalid_prices)} 条记录")

        # 检查成交量合理性
        if "volume" in df.columns:
            invalid_volume = df[df["volume"] < 0]
            if len(invalid_volume) > 0:
                errors.append(f"成交量存在负值: {len(invalid_volume)} 条记录")

        # 检查价格逻辑关系
        if all(field in df.columns for field in ["high", "low", "open", "close"]):
            # 最高价应该大于等于最低价
            invalid_high_low = df[df["high"] < df["low"]]
            if len(invalid_high_low) > 0:
                errors.append(f"最高价小于最低价: {len(invalid_high_low)} 条记录")

            # 最高价和最低价应该包含开盘价和收盘价
            invalid_range_open = df[(df["open"] > df["high"]) | (df["open"] < df["low"])]
            invalid_range_close = df[(df["close"] > df["high"]) | (df["close"] < df["low"])]

            if len(invalid_range_open) > 0:
                errors.append(f"开盘价超出最高最低价范围: {len(invalid_range_open)} 条记录")
            if len(invalid_range_close) > 0:
                errors.append(f"收盘价超出最高最低价范围: {len(invalid_range_close)} 条记录")

        # 检查重复日期
        if "date" in df.columns:
            duplicate_dates = df[df["date"].duplicated()]
            if len(duplicate_dates) > 0:
                errors.append(f"存在重复日期: {len(duplicate_dates)} 条记录")

        return len(errors) == 0, errors

    @staticmethod
    def clean_trading_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗交易数据

        Args:
            df: 原始交易数据

        Returns:
            清洗后的数据
        """
        cleaned_df = df.copy()

        # 移除全为NaN的行
        cleaned_df = cleaned_df.dropna(how="all")

        # 按日期排序
        if "date" in cleaned_df.columns:
            cleaned_df = cleaned_df.sort_values("date").reset_index(drop=True)

        # 处理异常价格
        price_fields = ["open", "high", "low", "close"]
        for field in price_fields:
            if field in cleaned_df.columns:
                # 将非正价格替换为NaN
                cleaned_df.loc[cleaned_df[field] <= 0, field] = np.nan

        # 处理异常成交量
        if "volume" in cleaned_df.columns:
            # 将负成交量替换为NaN
            cleaned_df.loc[cleaned_df["volume"] < 0, "volume"] = np.nan

        # 前向填充缺失值
        numeric_columns = cleaned_df.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            cleaned_df[col] = cleaned_df[col].fillna(method="ffill")

        # 移除仍然存在NaN的行
        cleaned_df = cleaned_df.dropna()

        # 重新计算涨跌幅（如果有原始数据的话）
        if all(col in cleaned_df.columns for col in ["close", "pre_close"]):
            cleaned_df["pct_change"] = (cleaned_df["close"] / cleaned_df["pre_close"] - 1) * 100
            cleaned_df["change"] = cleaned_df["close"] - cleaned_df["pre_close"]

        return cleaned_df

    @staticmethod
    def adjust_price(df: pd.DataFrame, method: str = "qfq") -> pd.DataFrame:
        """
        价格复权处理

        Args:
            df: 原始数据，必须包含adj_factor字段
            method: 复权方法 ("qfq"前复权, "hfq"后复权, "none"不复权)

        Returns:
            复权后的数据
        """
        if method == "none" or "adj_factor" not in df.columns:
            return df

        adjusted_df = df.copy()

        if method == "qfq":
            # 前复权：使用最新的复权因子
            latest_factor = df["adj_factor"].iloc[-1]
            price_fields = ["open", "high", "low", "close", "pre_close"]
            for field in price_fields:
                if field in adjusted_df.columns:
                    adjusted_df[f"{field}_adj"] = adjusted_df[field] * (latest_factor / adjusted_df["adj_factor"])

        elif method == "hfq":
            # 后复权：使用初始的复权因子
            initial_factor = df["adj_factor"].iloc[0]
            price_fields = ["open", "high", "low", "close", "pre_close"]
            for field in price_fields:
                if field in adjusted_df.columns:
                    adjusted_df[f"{field}_adj"] = adjusted_df[field] * (initial_factor / adjusted_df["adj_factor"])

        return adjusted_df

    @staticmethod
    def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        计算常用技术指标

        Args:
            df: 基础交易数据

        Returns:
            包含技术指标的数据
        """
        if df.empty or "close" not in df.columns:
            return df

        result_df = df.copy()

        # 计算收益率
        result_df["returns"] = result_df["close"].pct_change()

        # 移动平均线
        for period in [5, 10, 20, 60]:
            result_df[f"ma_{period}"] = result_df["close"].rolling(window=period).mean()

        # 指数移动平均线
        for period in [12, 26]:
            result_df[f"ema_{period}"] = result_df["close"].ewm(span=period).mean()

        # MACD
        ema_12 = result_df["close"].ewm(span=12).mean()
        ema_26 = result_df["close"].ewm(span=26).mean()
        result_df["macd"] = ema_12 - ema_26
        result_df["macd_signal"] = result_df["macd"].ewm(span=9).mean()
        result_df["macd_histogram"] = result_df["macd"] - result_df["macd_signal"]

        # RSI
        delta = result_df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        result_df["rsi"] = 100 - (100 / (1 + rs))

        # 布林带
        ma_20 = result_df["close"].rolling(window=20).mean()
        std_20 = result_df["close"].rolling(window=20).std()
        result_df["bb_upper"] = ma_20 + (std_20 * 2)
        result_df["bb_lower"] = ma_20 - (std_20 * 2)
        result_df["bb_middle"] = ma_20

        # 成交量移动平均
        if "volume" in result_df.columns:
            for period in [5, 20]:
                result_df[f"volume_ma_{period}"] = result_df["volume"].rolling(window=period).mean()

            # 量比
            result_df["volume_ratio"] = result_df["volume"] / result_df["volume_ma_5"]

        return result_df


class TuShareCodeConverter:
    """
    TuShare股票代码转换器

    提供不同格式的股票代码转换功能。
    """

    @staticmethod
    def to_tushare_format(symbol: str) -> str:
        """
        转换为TuShare格式的股票代码

        Args:
            symbol: 股票代码（可以是各种格式）

        Returns:
            TuShare格式代码（如：000001.SZ）
        """
        # 移除所有非数字字符
        code_digits = re.sub(r"[^\d]", "", symbol)

        if not code_digits:
            raise TuShareDataError(f"无效的股票代码: {symbol}")

        # 根据代码首位判断市场
        first_digit = code_digits[0]

        if first_digit in ["0", "2", "3"]:
            return f"{code_digits}.SZ"  # 深交所
        elif first_digit in ["6"]:
            return f"{code_digits}.SH"  # 上交所
        elif first_digit in ["4", "8"]:
            return f"{code_digits}.BJ"  # 北交所
        else:
            # 默认当作上交所处理
            return f"{code_digits}.SH"

    @staticmethod
    def to_qlib_format(symbol: str) -> str:
        """
        转换为Qlib格式的股票代码

        Args:
            symbol: TuShare格式代码（如：000001.SZ）

        Returns:
            Qlib格式代码（如：SZ000001）
        """
        if "." in symbol:
            code, market = symbol.split(".")
            return f"{market}{code}"
        else:
            # 如果没有交易所后缀，尝试判断
            return TuShareCodeConverter._guess_market_and_format(symbol)

    @staticmethod
    def _guess_market_and_format(symbol: str) -> str:
        """
        根据代码猜测市场并格式化

        Args:
            symbol: 纯数字代码

        Returns:
            Qlib格式代码
        """
        code_digits = re.sub(r"[^\d]", "", symbol)
        if not code_digits:
            raise TuShareDataError(f"无效的股票代码: {symbol}")

        first_digit = code_digits[0]

        if first_digit in ["0", "2", "3"]:
            return f"SZ{code_digits}"
        elif first_digit in ["6"]:
            return f"SH{code_digits}"
        elif first_digit in ["4", "8"]:
            return f"BJ{code_digits}"
        else:
            return f"SH{code_digits}"  # 默认

    @staticmethod
    def normalize_code(symbol: str, target_format: str = "tushare") -> str:
        """
        标准化股票代码格式

        Args:
            symbol: 股票代码（任意格式）
            target_format: 目标格式 ("tushare", "qlib", "raw")

        Returns:
            标准化后的代码
        """
        if target_format == "tushare":
            return TuShareCodeConverter.to_tushare_format(symbol)
        elif target_format == "qlib":
            return TuShareCodeConverter.to_qlib_format(symbol)
        elif target_format == "raw":
            return re.sub(r"[^\d]", "", symbol)
        else:
            raise ValueError(f"不支持的目标格式: {target_format}")


class TuShareDateUtils:
    """
    TuShare日期处理工具

    提供日期格式转换、交易日计算等功能。
    """

    @staticmethod
    def to_tushare_date(date: Union[str, datetime, pd.Timestamp]) -> str:
        """
        转换为TuShare日期格式

        Args:
            date: 日期对象或字符串

        Returns:
            TuShare格式日期字符串 (YYYYMMDD)
        """
        if isinstance(date, str):
            # 尝试解析不同格式的日期字符串
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
                try:
                    dt = datetime.strptime(date, fmt)
                    return dt.strftime("%Y%m%d")
                except ValueError:
                    continue

            # 如果所有格式都失败，尝试使用pandas解析
            try:
                dt = pd.to_datetime(date)
                return dt.strftime("%Y%m%d")
            except:
                raise TuShareDataError(f"无法解析日期字符串: {date}")

        elif isinstance(date, (datetime, pd.Timestamp)):
            return date.strftime("%Y%m%d")
        else:
            raise TuShareDataError(f"不支持的日期类型: {type(date)}")

    @staticmethod
    def from_tushare_date(date_str: str) -> datetime:
        """
        从TuShare日期格式转换为datetime对象

        Args:
            date_str: TuShare格式日期字符串 (YYYYMMDD)

        Returns:
            datetime对象
        """
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            raise TuShareDataError(f"无效的TuShare日期格式: {date_str}")

    @staticmethod
    def get_date_range(start_date: str, end_date: str) -> List[str]:
        """
        获取日期范围内的所有日期

        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            日期列表
        """
        start_dt = TuShareDateUtils.from_tushare_date(start_date)
        end_dt = TuShareDateUtils.from_tushare_date(end_date)

        date_list = []
        current_dt = start_dt
        while current_dt <= end_dt:
            date_list.append(current_dt.strftime("%Y%m%d"))
            current_dt += timedelta(days=1)

        return date_list

    @staticmethod
    def is_trading_day(date: str, trading_calendar: pd.DataFrame) -> bool:
        """
        检查是否为交易日

        Args:
            date: 日期字符串 (YYYYMMDD)
            trading_calendar: 交易日历DataFrame

        Returns:
            是否为交易日
        """
        if trading_calendar.empty:
            return True  # 如果没有交易日历，默认都是交易日

        date_formatted = TuShareDateUtils.from_tushare_date(date)
        date_str = date_formatted.strftime("%Y-%m-%d")

        return date_str in trading_calendar["date"].astype(str).values


class TuShareMarketUtils:
    """
    TuShare市场工具

    提供市场相关的工具函数。
    """

    @staticmethod
    def get_market_code(symbol: str) -> str:
        """
        获取股票所属市场代码

        Args:
            symbol: 股票代码

        Returns:
            市场代码 (SH/SZ/BJ)
        """
        tushare_code = TuShareCodeConverter.to_tushare_format(symbol)
        return tushare_code.split(".")[-1]

    @staticmethod
    def is_index_code(symbol: str) -> bool:
        """
        判断是否为指数代码

        Args:
            symbol: 代码

        Returns:
            是否为指数
        """
        # 指数代码通常以数字开头且包含特定模式
        return bool(re.match(r"^\d{6}\.(SH|SZ)$", symbol)) and any(
            pattern in symbol for pattern in ["000001", "399001", "399005", "399006", "000300"]
        )

    @staticmethod
    def get_stock_name_suffix(symbol: str) -> str:
        """
        获取股票名称后缀

        Args:
            symbol: 股票代码

        Returns:
            名称后缀 (SH/SZ)
        """
        market = TuShareMarketUtils.get_market_code(symbol)
        return {"SH": "沪", "SZ": "深", "BJ": "北"}.get(market, "")

    @staticmethod
    def filter_by_market(symbols: List[str], market: str = None) -> List[str]:
        """
        按市场过滤股票代码

        Args:
            symbols: 股票代码列表
            market: 目标市场 (SH/SZ/BJ)

        Returns:
            过滤后的代码列表
        """
        if market is None:
            return symbols

        filtered_symbols = []
        for symbol in symbols:
            try:
                current_market = TuShareMarketUtils.get_market_code(symbol)
                if current_market == market.upper():
                    filtered_symbols.append(symbol)
            except:
                continue  # 忽略无效代码

        return filtered_symbols