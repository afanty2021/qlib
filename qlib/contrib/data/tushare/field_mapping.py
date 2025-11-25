"""
TuShare数据字段映射定义

定义TuShare数据源的字段到Qlib标准字段的映射关系，支持数据格式转换和验证。

字段映射分类：
1. 基础行情字段：OHLCV等核心交易数据
2. 技术指标字段：各种技术分析指标
3. 基本面字段：公司基本面数据
4. 市场数据字段：市场统计数据
"""

from typing import Dict, Any, Optional, List
import pandas as pd
from datetime import datetime

from .exceptions import TuShareDataError


class TuShareFieldMapping:
    """
    TuShare字段映射管理器

    管理TuShare数据字段到Qlib标准字段的映射关系，提供字段转换和验证功能。
    """

    # TuShare原始字段名到Qlib标准字段名的映射
    TUShare_TO_QLIB = {
        # 基础行情数据
        "ts_code": "instrument",        # 股票代码
        "trade_date": "date",          # 交易日期
        "open": "open",                # 开盘价
        "high": "high",                # 最高价
        "low": "low",                  # 最低价
        "close": "close",              # 收盘价
        "pre_close": "pre_close",      # 昨收价
        "change": "change",            # 涨跌额
        "pct_chg": "pct_change",       # 涨跌幅
        "vol": "volume",               # 成交量（手）
        "amount": "amount",            # 成交额（千元）

        # 复权因子
        "adj_factor": "adj_factor",    # 复权因子

        # 基本面数据
        "total_share": "total_share",          # 总股本
        "float_share": "float_share",          # 流通股本
        "free_share": "free_share",            # 自由流通股本
        "total_mv": "total_mv",                # 总市值
        "circ_mv": "circ_mv",                  # 流通市值

        # 财务指标
        "pe": "pe",                    # 市盈率
        "pe_ttm": "pe_ttm",            # 滚动市盈率
        "pb": "pb",                    # 市净率
        "ps": "ps",                    # 市销率
        "ps_ttm": "ps_ttm",            # 滚动市销率
        "dv_ratio": "dividend_ratio",  # 股息率
        "dv_ttm": "dividend_ttm",      # 滚动股息率

        # 指数成分
        "weight": "weight",            # 成分权重
        "in_date": "index_in_date",    # 纳入日期
        "out_date": "index_out_date",  # 剔除日期
    }

    # Qlib标准字段名到TuShare字段名的反向映射
    QLIB_TO_TUShare = {v: k for k, v in TUShare_TO_QLIB.items()}

    # 数值型字段列表
    NUMERIC_FIELDS = {
        "open", "high", "low", "close", "pre_close", "change", "pct_change",
        "volume", "amount", "adj_factor", "total_share", "float_share", "free_share",
        "total_mv", "circ_mv", "pe", "pe_ttm", "pb", "ps", "ps_ttm",
        "dividend_ratio", "dividend_ttm", "weight"
    }

    # 日期型字段列表
    DATE_FIELDS = {
        "date", "index_in_date", "index_out_date", "trade_date"
    }

    # 字符串型字段列表
    STRING_FIELDS = {
        "instrument", "ts_code"
    }

    # 字段单位映射（用于单位转换）
    FIELD_UNITS = {
        "volume": 100,          # 手转换为股
        "amount": 1000,         # 千元转换为元
        "total_mv": 10000,      # 万元转换为元
        "circ_mv": 10000,       # 万元转换为元
    }

    @classmethod
    def get_qlib_field(cls, tushare_field: str) -> Optional[str]:
        """
        获取TuShare字段对应的Qlib字段名

        Args:
            tushare_field: TuShare字段名

        Returns:
            Qlib标准字段名，如果不存在则返回None
        """
        return cls.TUShare_TO_QLIB.get(tushare_field)

    @classmethod
    def get_tushare_field(cls, qlib_field: str) -> Optional[str]:
        """
        获取Qlib字段对应的TuShare字段名

        Args:
            qlib_field: Qlib标准字段名

        Returns:
            TuShare字段名，如果不存在则返回None
        """
        return cls.QLIB_TO_TUShare.get(qlib_field)

    @classmethod
    def map_dataframe_columns(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换DataFrame的列名

        将TuShare字段名转换为Qlib标准字段名。

        Args:
            df: 原始DataFrame

        Returns:
            列名转换后的DataFrame
        """
        # 过滤存在的列名
        rename_dict = {
            col: cls.TUShare_TO_QLIB[col]
            for col in df.columns
            if col in cls.TUShare_TO_QLIB
        }

        if rename_dict:
            df = df.rename(columns=rename_dict)

        return df

    @classmethod
    def convert_data_types(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换DataFrame的数据类型

        根据字段映射规则转换数据类型。

        Args:
            df: 原始DataFrame

        Returns:
            数据类型转换后的DataFrame

        Raises:
            TuShareDataError: 当数据类型转换失败时
        """
        try:
            # 创建副本避免修改原数据
            converted_df = df.copy()

            # 日期字段转换
            for field in cls.DATE_FIELDS:
                if field in converted_df.columns:
                    if field == "date" or field == "trade_date":
                        # 日期字段转换为datetime类型
                        converted_df[field] = pd.to_datetime(
                            converted_df[field], format="%Y%m%d", errors="coerce"
                        )
                    else:
                        # 其他日期字段
                        converted_df[field] = pd.to_datetime(
                            converted_df[field], errors="coerce"
                        )

            # 数值字段转换
            for field in cls.NUMERIC_FIELDS:
                if field in converted_df.columns:
                    # 转换为数值类型
                    converted_df[field] = pd.to_numeric(
                        converted_df[field], errors="coerce"
                    )

                    # 单位转换
                    if field in cls.FIELD_UNITS:
                        converted_df[field] = converted_df[field] * cls.FIELD_UNITS[field]

            # 字符串字段转换
            for field in cls.STRING_FIELDS:
                if field in converted_df.columns:
                    converted_df[field] = converted_df[field].astype(str)

            return converted_df

        except Exception as e:
            raise TuShareDataError(
                f"数据类型转换失败: {str(e)}",
                details={"columns": list(df.columns), "dtypes": df.dtypes.to_dict()},
                cause=e
            )

    @classmethod
    def validate_required_fields(cls, df: pd.DataFrame, required_fields: List[str]) -> None:
        """
        验证DataFrame是否包含必需字段

        Args:
            df: 要验证的DataFrame
            required_fields: 必需字段列表（Qlib字段名）

        Raises:
            TuShareDataError: 当缺少必需字段时
        """
        missing_fields = []

        for field in required_fields:
            if field not in df.columns:
                # 检查是否需要字段映射
                tushare_field = cls.get_tushare_field(field)
                if tushare_field and tushare_field in df.columns:
                    continue
                missing_fields.append(field)

        if missing_fields:
            raise TuShareDataError(
                f"缺少必需字段: {missing_fields}",
                details={
                    "missing_fields": missing_fields,
                    "available_fields": list(df.columns)
                }
            )

    @classmethod
    def get_tushare_fields(cls, qlib_fields: List[str]) -> List[str]:
        """
        将Qlib字段名列表转换为TuShare字段名列表

        Args:
            qlib_fields: Qlib字段名列表

        Returns:
            TuShare字段名列表
        """
        tushare_fields = []

        for field in qlib_fields:
            tushare_field = cls.get_tushare_field(field)
            if tushare_field:
                tushare_fields.append(tushare_field)
            else:
                # 如果没有映射关系，保持原字段名
                tushare_fields.append(field)

        return tushare_fields

    @classmethod
    def filter_dataframe_fields(cls, df: pd.DataFrame, fields: List[str]) -> pd.DataFrame:
        """
        过滤DataFrame，只保留指定字段

        Args:
            df: 原始DataFrame
            fields: 要保留的字段列表（Qlib字段名）

        Returns:
            过滤后的DataFrame
        """
        # 先转换字段名
        mapped_df = cls.map_dataframe_columns(df)

        # 获取实际存在的字段
        available_fields = [field for field in fields if field in mapped_df.columns]

        if available_fields:
            return mapped_df[available_fields]
        else:
            raise TuShareDataError(
                f"指定字段在数据中都不存在: {fields}",
                details={
                    "requested_fields": fields,
                    "available_fields": list(mapped_df.columns)
                }
            )

    @classmethod
    def get_field_info(cls, field_name: str) -> Dict[str, Any]:
        """
        获取字段的详细信息

        Args:
            field_name: 字段名（Qlib或TuShare格式）

        Returns:
            字段信息字典
        """
        # 确定字段类型和映射
        is_qlib_field = field_name in cls.QLIB_TO_TUShare
        is_tushare_field = field_name in cls.TUShare_TO_QLIB

        field_info = {
            "name": field_name,
            "is_qlib_field": is_qlib_field,
            "is_tushare_field": is_tushare_field,
        }

        if is_qlib_field:
            field_info["tushare_name"] = cls.QLIB_TO_TUShare[field_name]
            field_info["qlib_name"] = field_name
        elif is_tushare_field:
            field_info["tushare_name"] = field_name
            field_info["qlib_name"] = cls.TUShare_TO_QLIB[field_name]

        # 确定数据类型
        qlib_name = field_info.get("qlib_name", field_name)
        if qlib_name in cls.NUMERIC_FIELDS:
            field_info["data_type"] = "numeric"
        elif qlib_name in cls.DATE_FIELDS:
            field_info["data_type"] = "date"
        elif qlib_name in cls.STRING_FIELDS:
            field_info["data_type"] = "string"
        else:
            field_info["data_type"] = "unknown"

        # 添加单位信息
        if qlib_name in cls.FIELD_UNITS:
            field_info["unit_multiplier"] = cls.FIELD_UNITS[qlib_name]

        return field_info

    @classmethod
    def get_all_mappings(cls) -> Dict[str, Dict[str, str]]:
        """
        获取所有字段映射信息

        Returns:
            完整的字段映射字典
        """
        return {
            "tushare_to_qlib": cls.TUShare_TO_QLIB.copy(),
            "qlib_to_tushare": cls.QLIB_TO_TUShare.copy(),
        }

    @classmethod
    def export_field_mappings(cls, file_path: str) -> None:
        """
        导出字段映射到文件

        Args:
            file_path: 导出文件路径
        """
        import json

        mappings = {
            "field_mappings": cls.get_all_mappings(),
            "numeric_fields": list(cls.NUMERIC_FIELDS),
            "date_fields": list(cls.DATE_FIELDS),
            "string_fields": list(cls.STRING_FIELDS),
            "field_units": cls.FIELD_UNITS,
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(mappings, f, indent=2, ensure_ascii=False)