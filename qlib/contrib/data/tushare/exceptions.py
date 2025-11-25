"""
TuShare数据源自定义异常类

定义TuShare数据源相关的所有自定义异常，提供精确的错误分类和处理。

异常层级：
TuShareError (基类)
├── TuShareConfigError    # 配置相关错误
├── TuShareAPIError       # API调用相关错误
├── TuShareDataError      # 数据相关错误
└── TuShareCacheError     # 缓存相关错误
"""

from typing import Optional, Any, Dict


class TuShareError(Exception):
    """
    TuShare数据源基础异常类

    所有TuShare相关异常的基类，提供统一的错误处理接口。

    Args:
        message: 错误消息
        error_code: 错误代码（可选）
        details: 错误详细信息（可选）
        cause: 原始异常（可选）
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause

    def __str__(self) -> str:
        """格式化错误信息"""
        error_str = f"[{self.__class__.__name__}] {self.message}"

        if self.error_code:
            error_str += f" (代码: {self.error_code})"

        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            error_str += f" | 详情: {details_str}"

        if self.cause:
            error_str += f" | 原因: {str(self.cause)}"

        return error_str

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，便于日志记录和调试"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
        }


class TuShareConfigError(TuShareError):
    """
    TuShare配置相关错误

    当配置参数无效、缺失或配置文件有问题时抛出。
    """

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(message, error_code="CONFIG_ERROR", **kwargs)
        self.config_key = config_key


class TuShareAPIError(TuShareError):
    """
    TuShare API调用相关错误

    当API请求失败、网络错误、限流等问题时抛出。

    Args:
        message: 错误消息
        status_code: HTTP状态码（可选）
        api_method: 调用的API方法（可选）
        request_params: 请求参数（可选）
        retry_count: 已重试次数（可选）
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        api_method: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None,
        retry_count: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, error_code="API_ERROR", **kwargs)
        self.status_code = status_code
        self.api_method = api_method
        self.request_params = request_params or {}
        self.retry_count = retry_count


class TuShareDataError(TuShareError):
    """
    TuShare数据相关错误

    当数据格式错误、数据缺失、数据验证失败等问题时抛出。

    Args:
        message: 错误消息
        symbol: 相关股票代码（可选）
        field: 相关数据字段（可选）
        date_range: 相关日期范围（可选）
        data_format: 期望的数据格式（可选）
    """

    def __init__(
        self,
        message: str,
        symbol: Optional[str] = None,
        field: Optional[str] = None,
        date_range: Optional[str] = None,
        data_format: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="DATA_ERROR", **kwargs)
        self.symbol = symbol
        self.field = field
        self.date_range = date_range
        self.data_format = data_format


class TuShareCacheError(TuShareError):
    """
    TuShare缓存相关错误

    当缓存读写失败、缓存损坏、缓存空间不足等问题时抛出。

    Args:
        message: 错误消息
        cache_key: 缓存键（可选）
        cache_path: 缓存文件路径（可选）
        cache_type: 缓存类型（memory/disk）（可选）
    """

    def __init__(
        self,
        message: str,
        cache_key: Optional[str] = None,
        cache_path: Optional[str] = None,
        cache_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, error_code="CACHE_ERROR", **kwargs)
        self.cache_key = cache_key
        self.cache_path = cache_path
        self.cache_type = cache_type


# 异常处理工具函数
def handle_tushare_error(func):
    """
    TuShare错误处理装饰器

    自动捕获和转换TuShare相关的异常，统一错误处理格式。

    Args:
        func: 被装饰的函数

    Returns:
        装饰后的函数
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TuShareError:
            # 已知的TuShare错误，直接抛出
            raise
        except Exception as e:
            # 未知异常，包装为TuShareError
            raise TuShareError(
                f"TuShare操作失败: {str(e)}",
                cause=e
            )

    return wrapper


def create_api_error_from_response(response, message: Optional[str] = None) -> TuShareAPIError:
    """
    从API响应创建TuShareAPIError

    Args:
        response: HTTP响应对象
        message: 自定义错误消息（可选）

    Returns:
        TuShareAPIError实例
    """
    status_code = getattr(response, 'status_code', None)

    # 根据状态码生成默认消息
    if not message:
        if status_code == 400:
            message = "请求参数错误"
        elif status_code == 401:
            message = "Token无效或过期"
        elif status_code == 403:
            message = "无权限访问"
        elif status_code == 429:
            message = "API调用频率超限"
        elif status_code >= 500:
            message = "服务器内部错误"
        else:
            message = f"API请求失败 (HTTP {status_code})"

    return TuShareAPIError(
        message=message,
        status_code=status_code,
        details={
            "response_text": getattr(response, 'text', ''),
            "headers": dict(getattr(response, 'headers', {})),
        }
    )