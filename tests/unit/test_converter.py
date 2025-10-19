"""
转换器单元测试
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from app.converter import LiteConverter
from app.core.exceptions import ConversionError


class TestLiteConverter:
    """转换器测试类"""

    def test_init_no_mappings(self):
        """测试无映射初始化"""
        converter = LiteConverter()
        assert converter.model_mappings == []
        assert converter._model_mapping_cache == {}

    def test_init_with_mappings(self):
        """测试带映射初始化"""
        mappings = [
            {"anthropic": "claude-3", "openai": "gpt-4"},
            {"anthropic": "claude-2", "openai": "gpt-3.5"}
        ]
        converter = LiteConverter(mappings)
        assert converter.model_mappings == mappings
        assert converter._model_mapping_cache == {
            "claude-3": "gpt-4",
            "claude-2": "gpt-3.5"
        }

    def test_get_mapped_model_no_mappings(self):
        """测试无映射时的模型名称"""
        converter = LiteConverter()
        result = converter.get_mapped_model("claude-3-5-haiku-20241022")
        assert result == "claude-3-5-haiku-20241022"

    def test_get_mapped_model_with_mapping(self):
        """测试有映射时的模型名称"""
        mappings = [{"anthropic": "claude-3", "openai": "gpt-4"}]
        converter = LiteConverter(mappings)
        result = converter.get_mapped_model("claude-3")
        assert result == "gpt-4"

    def test_get_mapped_model_no_match(self):
        """测试无匹配时的模型名称"""
        mappings = [{"anthropic": "claude-3", "openai": "gpt-4"}]
        converter = LiteConverter(mappings)
        result = converter.get_mapped_model("claude-2")
        assert result == "claude-2"

    def test_get_mapped_model_caching(self, sample_config):
        """测试模型映射缓存"""
        converter = LiteConverter(sample_config["model_mappings"])

        # 第一次调用
        result1 = converter.get_mapped_model("claude-3-5-haiku-20241022")
        assert result1 == "gpt-4"

        # 第二次调用应该使用缓存
        result2 = converter.get_mapped_model("claude-3-5-haiku-20241022")
        assert result2 == "gpt-4"

    def test_convert_messages_basic(self, sample_anthropic_request):
        """测试基础消息转换"""
        converter = LiteConverter()
        result = converter.anthropic_to_openai(sample_anthropic_request)

        assert "messages" in result
        assert "model" in result
        assert "max_tokens" in result
        assert result["model"] == "claude-3-5-haiku-20241022"
        assert result["max_tokens"] == 1024

    def test_convert_messages_with_mapping(self, sample_anthropic_request, sample_config):
        """测试带映射的消息转换"""
        converter = LiteConverter(sample_config["model_mappings"])
        result = converter.anthropic_to_openai(sample_anthropic_request)

        assert result["model"] == "gpt-4"  # 应该被映射

    def test_convert_messages_with_system_message(self):
        """测试带系统消息的转换"""
        anthropic_request = {
            "model": "claude-3",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "system": "You are a helpful assistant."
        }

        converter = LiteConverter()
        result = converter.anthropic_to_openai(anthropic_request)

        # 系统消息应该被转换为第一条消息
        assert len(result["messages"]) == 2
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][0]["content"] == "You are a helpful assistant."

    def test_convert_messages_with_tools(self):
        """测试工具调用转换"""
        anthropic_request = {
            "model": "claude-3",
            "messages": [
                {"role": "user", "content": "What's the weather?"}
            ],
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather information",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"}
                        }
                    }
                }
            ]
        }

        converter = LiteConverter()
        result = converter.anthropic_to_openai(anthropic_request)

        assert "tools" in result
        assert len(result["tools"]) == 1
        assert result["tools"][0]["function"]["name"] == "get_weather"

    def test_convert_response_basic(self, sample_openai_response):
        """测试基础响应转换"""
        converter = LiteConverter()
        result = converter.openai_to_anthropic(sample_openai_response)

        assert "content" in result
        assert "model" in result
        assert "stop_reason" in result
        assert result["stop_reason"] == "end_turn"

    def test_convert_response_with_usage(self, sample_openai_response):
        """测试带使用统计的响应转换"""
        converter = LiteConverter()
        result = converter.openai_to_anthropic(sample_openai_response)

        assert "usage" in result
        assert result["usage"]["input_tokens"] == 20
        assert result["usage"]["output_tokens"] == 18

    def test_convert_response_with_tool_calls(self):
        """测试工具调用响应转换"""
        openai_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": "{\"location\": \"New York\"}"
                                }
                            }
                        ]
                    },
                    "finish_reason": "tool_calls"
                }
            ]
        }

        converter = LiteConverter()
        result = converter.openai_to_anthropic(openai_response)

        assert isinstance(result["content"], list)
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "tool_use"
        assert result["content"][0]["name"] == "get_weather"
        assert result["stop_reason"] == "tool_use"

    def test_convert_streaming_response(self):
        """测试流式响应转换"""
        converter = LiteConverter()

        # 模拟OpenAI流式数据块
        openai_chunks = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " world"}}]},
            {"choices": [{"finish_reason": "stop"}]}
        ]

        for chunk in openai_chunks:
            result = converter.openai_chunk_to_anthropic(chunk)
            assert isinstance(result, (str, dict))

    def test_error_handling_invalid_input(self):
        """测试错误处理 - 无效输入"""
        converter = LiteConverter()

        with pytest.raises(ConversionError):
            converter.anthropic_to_openai(None)

        with pytest.raises(ConversionError):
            converter.openai_to_anthropic(None)

    def test_error_handling_malformed_message(self):
        """测试错误处理 - 格式错误的消息"""
        converter = LiteConverter()

        # 缺少必需字段的消息
        malformed_request = {"model": "claude-3"}  # 缺少messages

        with pytest.raises(ConversionError):
            converter.anthropic_to_openai(malformed_request)

    @patch('app.converter.logger')
    def test_logging_on_conversion_error(self, mock_logger, sample_config):
        """测试转换错误的日志记录"""
        converter = LiteConverter(sample_config["model_mappings"])

        # 故意制造转换错误
        invalid_request = {"invalid": "structure"}

        with pytest.raises(ConversionError):
            converter.anthropic_to_openai(invalid_request)

        # 验证错误日志被记录
        mock_logger.error.assert_called_at_least_once()


@pytest.mark.integration
class TestConverterIntegration:
    """转换器集成测试"""

    def test_complete_conversion_cycle(self, sample_anthropic_request, sample_openai_response, sample_config):
        """测试完整的转换周期"""
        converter = LiteConverter(sample_config["model_mappings"])

        # Anthropic -> OpenAI
        openai_request = converter.anthropic_to_openai(sample_anthropic_request)
        assert "messages" in openai_request

        # OpenAI -> Anthropic
        anthropic_response = converter.openai_to_anthropic(sample_openai_response)
        assert "content" in anthropic_response

    def test_performance_with_large_message(self):
        """测试大消息的性能"""
        import time

        # 创建大消息
        large_message = {
            "model": "claude-3",
            "messages": [
                {"role": "user", "content": "Hello " * 1000}
            ]
        }

        converter = LiteConverter()

        start_time = time.time()
        result = converter.anthropic_to_openai(large_message)
        duration = time.time() - start_time

        # 应该在合理时间内完成（100ms）
        assert duration < 0.1
        assert "messages" in result