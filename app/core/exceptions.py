"""
自定义异常类层次结构
提供结构化的错误处理机制
"""


class APIServiceError(Exception):
    """API服务基础异常"""

    def __init__(self, message, error_code=None, status_code=500):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "api_service_error"
        self.status_code = status_code
        self.details = {}

    def to_dict(self):
        """转换为字典格式"""
        return {
            'type': 'error',
            'error': {
                'type': self.error_code,
                'message': self.message,
                'details': self.details
            }
        }


class ConversionError(APIServiceError):
    """转换异常"""

    def __init__(self, message, details=None):
        super().__init__(
            message=message,
            error_code="conversion_error",
            status_code=400
        )
        if details:
            self.details.update(details)


class UpstreamAPIError(APIServiceError):
    """上游API异常"""

    def __init__(self, message, upstream_status_code=None, details=None):
        super().__init__(
            message=message,
            error_code="upstream_error",
            status_code=502
        )
        self.upstream_status_code = upstream_status_code
        if details:
            self.details.update(details)


class ValidationError(APIServiceError):
    """数据验证异常"""

    def __init__(self, message, field=None, details=None):
        super().__init__(
            message=message,
            error_code="validation_error",
            status_code=422
        )
        self.field = field
        if details:
            self.details.update(details)
        if field:
            self.details['field'] = field


class RateLimitError(APIServiceError):
    """限流异常"""

    def __init__(self, message, retry_after=None, details=None):
        super().__init__(
            message=message,
            error_code="rate_limit_error",
            status_code=429
        )
        self.retry_after = retry_after
        if details:
            self.details.update(details)
        if retry_after:
            self.details['retry_after'] = retry_after


class ConfigurationError(APIServiceError):
    """配置异常"""

    def __init__(self, message, config_key=None, details=None):
        super().__init__(
            message=message,
            error_code="configuration_error",
            status_code=500
        )
        self.config_key = config_key
        if details:
            self.details.update(details)
        if config_key:
            self.details['config_key'] = config_key


class TimeoutError(APIServiceError):
    """超时异常"""

    def __init__(self, message, timeout_duration=None, details=None):
        super().__init__(
            message=message,
            error_code="timeout_error",
            status_code=504
        )
        self.timeout_duration = timeout_duration
        if details:
            self.details.update(details)
        if timeout_duration:
            self.details['timeout_duration'] = timeout_duration


class StreamingError(APIServiceError):
    """流式处理异常"""

    def __init__(self, message, stream_position=None, details=None):
        super().__init__(
            message=message,
            error_code="streaming_error",
            status_code=500
        )
        self.stream_position = stream_position
        if details:
            self.details.update(details)
        if stream_position:
            self.details['stream_position'] = stream_position


# 异常处理工具函数
def handle_upstream_response(response, default_message="Upstream API error"):
    """
    处理上游API响应，生成适当的异常

    Args:
        response: requests.Response对象
        default_message: 默认错误消息

    Returns:
        UpstreamAPIError异常实例
    """
    try:
        error_data = response.json()
        message = error_data.get('error', {}).get('message', default_message)
        error_type = error_data.get('error', {}).get('type', 'unknown')
    except (ValueError, KeyError):
        message = response.text or default_message
        error_type = 'unknown'

    return UpstreamAPIError(
        message=f"{default_message}: {message}",
        upstream_status_code=response.status_code,
        details={
            'upstream_error_type': error_type,
            'upstream_status': response.status_code,
            'upstream_url': response.url
        }
    )


def create_validation_error(message, field=None, value=None):
    """
    创建验证错误

    Args:
        message: 错误消息
        field: 字段名
        value: 字段值

    Returns:
        ValidationError异常实例
    """
    details = {}
    if value is not None:
        details['value'] = str(value)

    return ValidationError(
        message=message,
        field=field,
        details=details
    )