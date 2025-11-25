"""
Qlib TuShare数据源模块

本模块为Qlib提供TuShare数据源集成支持，支持A股市场数据获取和处理。

主要功能：
- 统一数据接口：与Qlib原生数据接口完全兼容
- 多层缓存机制：内存缓存 + 磁盘缓存提升性能
- 企业级稳定性：完善的错误处理、重试机制、降级策略
- 灵活配置管理：支持环境变量、配置文件、代码配置
- 实时数据获取：支持A股日线、分钟线等实时数据
- 自动字段映射：TuShare字段到Qlib标准字段自动转换

使用示例：
    from qlib.contrib.data.tushare import TuShareProvider, TuShareConfig
    from qlib import init

    # 初始化配置
    config = TuShareConfig(token="your_token")

    # 使用TuShare数据源初始化Qlib
    init(provider_uri="tushare", default_conf={"tushare": config})

    # 正常使用Qlib数据接口
    from qlib.data import D
    data = D.features(["000001.SZ"], ["close", "volume"],
                      start_time="2024-01-01", end_time="2024-12-31")

作者：Qlib TuShare集成团队
版本：1.0.0
"""

from .config import TuShareConfig
from .provider import TuShareProvider
from .exceptions import (
    TuShareError,
    TuShareConfigError,
    TuShareAPIError,
    TuShareDataError,
    TuShareCacheError,
)

__version__ = "1.0.0"
__all__ = [
    "TuShareConfig",
    "TuShareProvider",
    "TuShareError",
    "TuShareConfigError",
    "TuShareAPIError",
    "TuShareDataError",
    "TuShareCacheError",
]