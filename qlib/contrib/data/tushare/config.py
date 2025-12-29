"""
TuShare数据源配置管理

提供TuShare数据源的配置管理功能，支持多种配置来源和格式验证。

配置优先级（从高到低）：
1. 代码直接配置
2. 环境变量配置
3. 配置文件配置
4. 默认配置

支持的配置项：
- token: TuShare API Token
- cache_dir: 缓存目录路径
- max_retries: 最大重试次数
- retry_delay: 重试延迟时间（秒）
- timeout: 请求超时时间（秒）
- rate_limit: API调用频率限制
- enable_cache: 是否启用缓存
- cache_ttl: 缓存生存时间（秒）
- log_level: 日志级别
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field

from .exceptions import TuShareConfigError


@dataclass
class TuShareConfig:
    """
    TuShare数据源配置类

    管理TuShare数据源的所有配置参数，支持多种配置来源和验证机制。
    """

    # TuShare API配置
    token: Optional[str] = None
    api_url: str = "https://api.tushare.pro"

    # 缓存配置
    enable_cache: bool = True
    cache_dir: Optional[str] = None
    cache_ttl: int = 86400  # 24小时
    max_cache_size: int = 1024 * 1024 * 1024  # 1GB

    # 重试和超时配置
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    timeout: float = 30.0

    # 频率限制配置
    rate_limit: int = 200  # 每分钟最大请求数
    rate_limit_window: int = 60  # 频率限制窗口（秒）

    # 数据获取配置
    batch_size: int = 5000  # 批量获取大小
    default_fields: list = field(default_factory=lambda: [
        "open", "high", "low", "close", "volume", "amount"
    ])

    # 日志配置
    log_level: str = "INFO"
    enable_api_logging: bool = False

    # 数据验证配置
    validate_data: bool = True
    remove_holidays: bool = True
    adjust_price: bool = True  # 是否复权

    def __post_init__(self):
        """
        初始化后处理和验证
        """
        # 设置默认缓存目录
        if self.cache_dir is None:
            self.cache_dir = str(Path.home() / ".qlib" / "cache" / "tushare")

        # 验证配置
        self.validate()

    def validate(self) -> None:
        """
        验证配置参数的有效性

        Raises:
            TuShareConfigError: 当配置参数无效时
        """
        errors = []

        # 验证Token格式
        if self.token and not isinstance(self.token, str):
            errors.append("Token必须是字符串类型")
        elif self.token and len(self.token.strip()) == 0:
            errors.append("Token不能为空字符串")

        # 验证数值参数
        if self.max_retries < 0:
            errors.append("max_retries不能为负数")
        if self.retry_delay < 0:
            errors.append("retry_delay不能为负数")
        if self.retry_backoff < 1:
            errors.append("retry_backoff不能小于1")
        if self.timeout <= 0:
            errors.append("timeout必须大于0")
        if self.rate_limit <= 0:
            errors.append("rate_limit必须大于0")
        if self.batch_size <= 0:
            errors.append("batch_size必须大于0")

        # 验证日志级别
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            errors.append(f"log_level必须是以下之一: {valid_log_levels}")

        # 验证缓存目录
        if self.cache_dir:
            cache_path = Path(self.cache_dir)
            if not cache_path.parent.exists():
                errors.append(f"缓存目录的父目录不存在: {cache_path.parent}")

        if errors:
            raise TuShareConfigError(
                f"配置验证失败: {'; '.join(errors)}",
                details={"validation_errors": errors}
            )

    @classmethod
    def from_env(cls) -> "TuShareConfig":
        """
        从环境变量加载配置

        环境变量命名规则：TUSHARE_<配置项名>
        例如：TUSHARE_TOKEN, TUSHARE_MAX_RETRIES

        Returns:
            TuShareConfig实例
        """
        config = cls()

        # 环境变量映射
        env_mapping = {
            "token": "TUSHARE_TOKEN",
            "api_url": "TUSHARE_API_URL",
            "enable_cache": "TUSHARE_ENABLE_CACHE",
            "cache_dir": "TUSHARE_CACHE_DIR",
            "cache_ttl": "TUSHARE_CACHE_TTL",
            "max_retries": "TUSHARE_MAX_RETRIES",
            "retry_delay": "TUSHARE_RETRY_DELAY",
            "retry_backoff": "TUSHARE_RETRY_BACKOFF",
            "timeout": "TUSHARE_TIMEOUT",
            "rate_limit": "TUSHARE_RATE_LIMIT",
            "batch_size": "TUSHARE_BATCH_SIZE",
            "log_level": "TUSHARE_LOG_LEVEL",
            "enable_api_logging": "TUSHARE_ENABLE_API_LOGGING",
            "validate_data": "TUSHARE_VALIDATE_DATA",
            "remove_holidays": "TUSHARE_REMOVE_HOLIDAYS",
            "adjust_price": "TUSHARE_ADJUST_PRICE",
        }

        # 从环境变量更新配置
        for attr_name, env_var in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # 类型转换
                if hasattr(config, attr_name):
                    attr_type = type(getattr(config, attr_name))
                    if attr_type == bool:
                        setattr(config, attr_name, env_value.lower() in ("true", "1", "yes"))
                    elif attr_type == int:
                        setattr(config, attr_name, int(env_value))
                    elif attr_type == float:
                        setattr(config, attr_name, float(env_value))
                    else:
                        setattr(config, attr_name, env_value)

        return config

    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> "TuShareConfig":
        """
        从配置文件加载配置

        支持JSON和YAML格式的配置文件。

        Args:
            config_path: 配置文件路径

        Returns:
            TuShareConfig实例

        Raises:
            TuShareConfigError: 当配置文件读取失败时
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise TuShareConfigError(
                f"配置文件不存在: {config_path}",
                details={"config_path": str(config_path)}
            )

        try:
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.suffix.lower() in ['.yaml', '.yml']:
                    config_data = yaml.safe_load(f)
                elif config_path.suffix.lower() == '.json':
                    config_data = json.load(f)
                else:
                    raise TuShareConfigError(
                        f"不支持的配置文件格式: {config_path.suffix}",
                        details={
                            "config_path": str(config_path),
                            "supported_formats": [".json", ".yaml", ".yml"]
                        }
                    )

            # 创建配置对象
            config = cls(**config_data)
            return config

        except yaml.YAMLError as e:
            raise TuShareConfigError(
                f"YAML配置文件格式错误: {str(e)}",
                details={"config_path": str(config_path)},
                cause=e
            )
        except json.JSONDecodeError as e:
            raise TuShareConfigError(
                f"JSON配置文件格式错误: {str(e)}",
                details={"config_path": str(config_path)},
                cause=e
            )
        except Exception as e:
            raise TuShareConfigError(
                f"读取配置文件失败: {str(e)}",
                details={"config_path": str(config_path)},
                cause=e
            )

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "TuShareConfig":
        """
        从字典创建配置

        Args:
            config_dict: 配置字典

        Returns:
            TuShareConfig实例
        """
        return cls(**config_dict)

    def merge_with(self, other: "TuShareConfig") -> "TuShareConfig":
        """
        合并两个配置对象

        优先使用当前配置的值，如果当前值为None则使用other的值。

        Args:
            other: 另一个配置对象

        Returns:
            合并后的新配置对象
        """
        merged_config_dict = {}

        # 获取所有配置项
        for field_name in self.__dataclass_fields__:
            current_value = getattr(self, field_name)
            other_value = getattr(other, field_name)

            # 优先使用非None的当前值
            if current_value is not None:
                merged_config_dict[field_name] = current_value
            elif other_value is not None:
                merged_config_dict[field_name] = other_value

        return TuShareConfig(**merged_config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        Returns:
            配置字典
        """
        return {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }

    def save_to_file(self, config_path: Union[str, Path], format: str = "json") -> None:
        """
        保存配置到文件

        Args:
            config_path: 配置文件路径
            format: 文件格式 ("json" 或 "yaml")

        Raises:
            TuShareConfigError: 当保存失败时
        """
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            config_dict = self.to_dict()

            with open(config_path, 'w', encoding='utf-8') as f:
                if format.lower() == "yaml":
                    yaml.dump(config_dict, f, default_flow_style=False,
                             allow_unicode=True, indent=2)
                else:
                    json.dump(config_dict, f, indent=2, ensure_ascii=False)

        except Exception as e:
            raise TuShareConfigError(
                f"保存配置文件失败: {str(e)}",
                details={"config_path": str(config_path), "format": format},
                cause=e
            )

    def __str__(self) -> str:
        """
        格式化配置信息（隐藏敏感信息）
        """
        config_dict = self.to_dict()

        # 隐藏Token敏感信息
        if "token" in config_dict and config_dict["token"]:
            config_dict["token"] = f"***{config_dict['token'][-4:]}" if len(config_dict["token"]) > 4 else "***"

        return f"TuShareConfig({config_dict})"

    def get_cache_path(self, *subpaths) -> Path:
        """
        获取缓存路径

        Args:
            *subpaths: 子路径

        Returns:
            完整的缓存路径
        """
        cache_path = Path(self.cache_dir)
        for subpath in subpaths:
            cache_path = cache_path / subpath
        return cache_path

    def ensure_cache_dir(self) -> None:
        """
        确保缓存目录存在
        """
        if self.enable_cache:
            cache_path = Path(self.cache_dir)
            cache_path.mkdir(parents=True, exist_ok=True)