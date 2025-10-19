"""
异常处理单元测试
"""

import pytest
from app.core.exceptions import (
    APIServiceError, ConversionError, UpstreamAPIError,
    ValidationError, RateLimitError, ConfigurationError,
    TimeoutError, StreamingError,
    handle_upstream_response, create_validation_error
)


class TestAPIServiceError:
    """基础API服务异常测试"""

    def test_basic_initialization(self):
        """测试基础初始化"""
        error = APIServiceError("Test message")
        assert error.message == "Test message"
        assert error.error_code == "api_service_error"
        assert error.status_code == 500
        assert error.details == {}

    def test_custom_initialization(self):
        """测试自定义初始化"""
        error = APIServiceError(
            message="Custom message",
            error_code="custom_error",
            status_code=400,
            details={"field": "test"}
        )
        assert error.message == "Custom message"
        assert error.error_code == "custom_error"
        assert error.status_code == 400
        assert error.details == {"field": "test"}

    def test_to_dict(self):
        """测试转换为字典"""
        error = ConversionError("Conversion failed", details={"step": "parsing"})
        result = error.to_dict()

        assert result["type"] == "error"
        assert result["error"]["type"] == "conversion_error"
        assert result["error"]["message"] == "Conversion failed"
        assert result["error"]["details"]["step"] == "parsing"


class TestConversionError:
    """转换错误测试"""

    def test_conversion_error_properties(self):
        """测试转换错误属性"""
        error = ConversionError("Cannot convert format")
        assert error.error_code == "conversion_error"
        assert error.status_code == 400

    def test_conversion_error_with_details(self):
        """测试带详情的转换错误"""
        error = ConversionError(
            "Invalid mapping",
            details={"source_format": "anthropic", "target_format": "openai"}
        )
        assert error.details["source_format"] == "anthropic"


class TestUpstreamAPIError:
    """上游API错误测试"""

    def test_upstream_api_error_properties(self):
        """测试上游API错误属性"""
        error = UpstreamAPIError("API call failed")
        assert error.error_code == "upstream_error"
        assert error.status_code == 502

    def test_upstream_api_error_with_status(self):
        """测试带状态码的上游API错误"""
        error = UpstreamAPIError(
            "Rate limited",
            upstream_status_code=429,
            details={"retry_after": 60}
        )
        assert error.upstream_status_code == 429
        assert error.details["retry_after"] == 60


class TestValidationError:
    """验证错误测试"""

    def test_validation_error_properties(self):
        """测试验证错误属性"""
        error = ValidationError("Invalid input")
        assert error.error_code == "validation_error"
        assert error.status_code == 422

    def test_validation_error_with_field(self):
        """测试带字段的验证错误"""
        error = ValidationError("Missing field", field="messages")
        assert error.field == "messages"
        assert error.details["field"] == "messages"


class TestRateLimitError:
    """限流错误测试"""

    def test_rate_limit_error_properties(self):
        """测试限流错误属性"""
        error = RateLimitError("Too many requests")
        assert error.error_code == "rate_limit_error"
        assert error.status_code == 429

    def test_rate_limit_error_with_retry_after(self):
        """测试带重试时间的限流错误"""
        error = RateLimitError("Rate limited", retry_after=120)
        assert error.retry_after == 120
        assert error.details["retry_after"] == 120


class TestConfigurationError:
    """配置错误测试"""

    def test_configuration_error_properties(self):
        """测试配置错误属性"""
        error = ConfigurationError("Invalid config")
        assert error.error_code == "configuration_error"
        assert error.status_code == 500

    def test_configuration_error_with_key(self):
        """测试带配置键的配置错误"""
        error = ConfigurationError("Missing key", config_key="api_key")
        assert error.config_key == "api_key"
        assert error.details["config_key"] == "api_key"


class TestTimeoutError:
    """超时错误测试"""

    def test_timeout_error_properties(self):
        """测试超时错误属性"""
        error = TimeoutError("Request timeout")
        assert error.error_code == "timeout_error"
        assert error.status_code == 504

    def test_timeout_error_with_duration(self):
        """测试带持续时间的超时错误"""
        error = TimeoutError("Slow response", timeout_duration=30)
        assert error.timeout_duration == 30
        assert error.details["timeout_duration"] == 30


class TestStreamingError:
    """流式错误测试"""

    def test_streaming_error_properties(self):
        """测试流式错误属性"""
        error = StreamingError("Stream interrupted")
        assert error.error_code == "streaming_error"
        assert error.status_code == 500

    def test_streaming_error_with_position(self):
        """测试带位置的流式错误"""
        error = StreamingError("Chunk error", stream_position=150)
        assert error.stream_position == 150
        assert error.details["stream_position"] == 150


class TestUtilityFunctions:
    """工具函数测试"""

    @pytest.fixture
    def mock_response(self):
        """模拟响应对象"""
        from unittest.mock import Mock
        response = Mock()
        response.status_code = 400
        response.url = "https://api.example.com/v1/chat"
        response.json.return_value = {
            "error": {
                "message": "Invalid request",
                "type": "invalid_request"
            }
        }
        response.text = '{"error": {"message": "Invalid request", "type": "invalid_request"}}'
        return response

    def test_handle_upstream_response_json_error(self, mock_response):
        """测试处理JSON格式的上游错误"""
        error = handle_upstream_response(mock_response, "Custom upstream error")

        assert isinstance(error, UpstreamAPIError)
        assert "Custom upstream error: Invalid request" in error.message
        assert error.upstream_status_code == 400
        assert error.details["upstream_error_type"] == "invalid_request"

    def test_handle_upstream_response_text_error(self):
        """测试处理文本格式的上游错误"""
        from unittest.mock import Mock
        response = Mock()
        response.status_code = 500
        response.url = "https://api.example.com/v1/chat"
        response.json.side_effect = ValueError("No JSON")
        response.text = "Internal Server Error"

        error = handle_upstream_response(response, "Server error")

        assert isinstance(error, UpstreamAPIError)
        assert "Server error: Internal Server Error" in error.message

    def test_handle_upstream_response_no_json(self):
        """测试处理无JSON的上游错误"""
        from unittest.mock import Mock
        response = Mock()
        response.status_code = 503
        response.url = "https://api.example.com/v1/chat"
        response.json.side_effect = ValueError("No JSON")
        response.text = ""

        error = handle_upstream_response(response, "Service unavailable")

        assert isinstance(error, UpstreamAPIError)
        assert "Service unavailable: " in error.message

    def test_create_validation_error_basic(self):
        """测试创建基础验证错误"""
        error = create_validation_error("Missing required field", "messages")

        assert isinstance(error, ValidationError)
        assert error.message == "Missing required field"
        assert error.field == "messages"

    def test_create_validation_error_with_value(self):
        """测试创建带值的验证错误"""
        error = create_validation_error(
            "Invalid type",
            field="max_tokens",
            value="invalid"
        )

        assert error.field == "max_tokens"
        assert error.details["value"] == "invalid"

    def test_create_validation_error_no_field(self):
        """测试创建无字段的验证错误"""
        error = create_validation_error("General validation error")

        assert isinstance(error, ValidationError)
        assert error.message == "General validation error"
        assert error.field is None


class TestExceptionInheritance:
    """异常继承测试"""

    def test_all_exceptions_inherit_from_api_service_error(self):
        """测试所有异常都继承自APIServiceError"""
        exceptions = [
            ConversionError, UpstreamAPIError, ValidationError,
            RateLimitError, ConfigurationError, TimeoutError, StreamingError
        ]

        for exception_class in exceptions:
            assert issubclass(exception_class, APIServiceError)

    def test_exception_hierarchy(self):
        """测试异常层次结构"""
        try:
            raise ValidationError("Test error")
        except APIServiceError as e:
            assert isinstance(e, ValidationError)
            assert e.message == "Test error"
        else:
            pytest.fail("ValidationError should be caught by APIServiceError")

    def test_exception_chaining(self):
        """测试异常链"""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as original:
                raise ConversionError("Conversion failed") from original
        except ConversionError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)
            assert str(e.__cause__) == "Original error"