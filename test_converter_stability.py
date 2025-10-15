"""
API转换服务器核心转换功能测试用例
规范核心转换逻辑，确保稳定性和正确性
"""

import unittest
import json
from converter_class import AnthropicToOpenAIConverter
from config_manager import ConfigManager


class TestCoreConverterFunctionality(unittest.TestCase):
    """核心转换功能的全面测试套件"""

    def setUp(self):
        """测试前置设置"""
        self.config_manager = ConfigManager()
        self.converter = AnthropicToOpenAIConverter(self.config_manager)

    def test_simple_text_message_conversion(self):
        """测试：简单文本消息转换"""
        # 输入：Anthropic格式
        anthropic_messages = [
            {
                "role": "user",
                "content": "Hello, how are you?"
            },
            {
                "role": "assistant",
                "content": "I'm doing well, thank you!"
            }
        ]

        # 执行转换
        result = self.converter.convert_messages(anthropic_messages)

        # 验证结果
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['role'], 'user')
        self.assertEqual(result[0]['content'], 'Hello, how are you?')
        self.assertEqual(result[1]['role'], 'assistant')
        self.assertEqual(result[1]['content'], "I'm doing well, thank you!")

    def test_tool_call_message_conversion(self):
        """测试：工具调用消息转换 - 关键测试"""
        # 输入：包含工具调用的复杂消息
        anthropic_messages = [
            {
                "role": "user",
                "content": "Please tell me the current time"
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "I'll get the current time for you."
                    },
                    {
                        "type": "tool_use",
                        "id": "toolu_01ABC123XYZ",
                        "name": "get_current_time",
                        "input": {}
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_01ABC123XYZ",
                        "content": "2024-01-15 14:30:25"
                    }
                ]
            }
        ]

        # 执行转换
        result = self.converter.convert_messages(anthropic_messages)

        # 验证结果
        self.assertEqual(len(result), 3)

        # 第一条消息：用户请求
        self.assertEqual(result[0]['role'], 'user')
        self.assertEqual(result[0]['content'], 'Please tell me the current time')

        # 第二条消息：助手工具调用
        self.assertEqual(result[1]['role'], 'assistant')
        self.assertEqual(result[1]['content'], "I'll get the current time for you.")
        self.assertIn('tool_calls', result[1])

        tool_calls = result[1]['tool_calls']
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]['id'], 'toolu_01ABC123XYZ')
        self.assertEqual(tool_calls[0]['type'], 'function')
        self.assertEqual(tool_calls[0]['function']['name'], 'get_current_time')

        # 第三条消息：用户工具结果
        self.assertEqual(result[2]['role'], 'user')
        self.assertIn('Tool Result for toolu_01ABC123XYZ', result[2]['content'])
        self.assertIn('2024-01-15 14:30:25', result[2]['content'])

    def test_multiple_tool_calls_conversion(self):
        """测试：多个工具调用转换"""
        anthropic_messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "I'll help you with that."
                    },
                    {
                        "type": "tool_use",
                        "id": "toolu_01ABC123",
                        "name": "get_weather",
                        "input": {"location": "Beijing"}
                    },
                    {
                        "type": "tool_use",
                        "id": "toolu_01DEF456",
                        "name": "get_news",
                        "input": {"category": "tech"}
                    }
                ]
            }
        ]

        result = self.converter.convert_messages(anthropic_messages)

        # 验证多个工具调用
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['role'], 'assistant')
        self.assertIn('tool_calls', result[0])

        tool_calls = result[0]['tool_calls']
        self.assertEqual(len(tool_calls), 2)

        # 验证第一个工具调用
        self.assertEqual(tool_calls[0]['id'], 'toolu_01ABC123')
        self.assertEqual(tool_calls[0]['function']['name'], 'get_weather')

        # 验证第二个工具调用
        self.assertEqual(tool_calls[1]['id'], 'toolu_01DEF456')
        self.assertEqual(tool_calls[1]['function']['name'], 'get_news')

    def test_mixed_content_handling(self):
        """测试：混合内容处理（文本+工具）"""
        anthropic_messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Previous result: "
                    },
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_previous",
                        "content": "Previous data"
                    },
                    {
                        "type": "text",
                        "text": ". Now please help with new task."
                    }
                ]
            }
        ]

        result = self.converter.convert_messages(anthropic_messages)

        # 验证混合内容正确合并
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['role'], 'user')

        content = result[0]['content']
        self.assertIn('Previous result:', content)
        self.assertIn('Tool Result for toolu_previous', content)
        self.assertIn('Previous data', content)
        self.assertIn('Now please help with new task', content)

    def test_empty_and_none_handling(self):
        """测试：空值和None处理"""
        test_cases = [
            # 空内容
            {"role": "user", "content": ""},
            # None内容
            {"role": "user", "content": None},
            # 空数组
            {"role": "assistant", "content": []},
            # 缺少content字段
            {"role": "user"}
        ]

        for test_input in test_cases:
            with self.subTest(test_input=test_input):
                result = self.converter.convert_messages([test_input])
                # 验证不会抛出异常，并返回有效结果
                self.assertIsInstance(result, list)
                self.assertEqual(len(result), 1)
                self.assertIn('role', result[0])

    def test_large_message_handling(self):
        """测试：大消息处理"""
        # 生成大文本内容
        large_text = "This is a test message. " * 1000

        anthropic_messages = [
            {
                "role": "user",
                "content": large_text
            }
        ]

        result = self.converter.convert_messages(anthropic_messages)

        # 验证大消息正确处理
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['content'], large_text)

    def test_unicode_and_special_characters(self):
        """测试：Unicode和特殊字符处理"""
        test_messages = [
            {
                "role": "user",
                "content": "Hello 世界! 🌍 Testing special chars: 你好, café, naïve"
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_unicode",
                        "name": "process_unicode",
                        "input": {"text": "Unicode test: 测试文本 🚀"}
                    }
                ]
            }
        ]

        result = self.converter.convert_messages(test_messages)

        # 验证Unicode字符正确保留
        self.assertEqual(len(result), 2)
        self.assertIn("世界", result[0]['content'])
        self.assertIn("🚀", json.dumps(result[1]['tool_calls']))

    def test_role_mapping_edge_cases(self):
        """测试：角色映射边界情况"""
        test_cases = [
            {"role": "unknown_role", "content": "test"},
            {"role": "", "content": "test"},
            {"content": "test"}  # 无角色
        ]

        for test_input in test_cases:
            with self.subTest(test_input=test_input):
                result = self.converter.convert_messages([test_input])
                # 验证所有角色都映射为'user'
                self.assertEqual(result[0]['role'], 'user')

    def test_complex_argument_serialization(self):
        """测试：复杂参数序列化"""
        anthropic_message = {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_complex",
                    "name": "complex_function",
                    "input": {
                        "nested_dict": {"key": "value", "number": 123},
                        "list_data": [1, 2, "three", {"four": 4}],
                        "boolean": True,
                        "null_value": None
                    }
                }
            ]
        }

        result = self.converter.convert_messages([anthropic_message])

        # 验证复杂参数正确序列化
        tool_calls = result[0]['tool_calls']
        args = json.loads(tool_calls[0]['function']['arguments'])

        self.assertEqual(args['nested_dict']['key'], 'value')
        self.assertEqual(args['list_data'][3]['four'], 4)
        self.assertTrue(args['boolean'])
        self.assertIsNone(args['null_value'])


class TestConverterStressTest(unittest.TestCase):
    """转换器压力测试"""

    def setUp(self):
        self.converter = AnthropicToOpenAIConverter()

    def test_high_volume_tool_calls(self):
        """测试：大量工具调用处理"""
        # 生成包含多个工具调用的消息
        tool_uses = []
        for i in range(50):
            tool_uses.append({
                "type": "tool_use",
                "id": f"toolu_{i:03d}",
                "name": f"function_{i}",
                "input": {"index": i}
            })

        message = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Processing multiple tools..."}
            ] + tool_uses
        }

        result = self.converter.convert_messages([message])

        # 验证所有工具调用都被正确处理
        self.assertEqual(len(result[0]['tool_calls']), 50)

    def test_performance_benchmark_conversion(self):
        """测试：转换性能基准"""
        import time

        # 生成复杂的测试数据
        complex_message = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_001",
                    "content": "Large result data " * 100
                },
                {
                    "type": "text",
                    "text": "Additional text content " * 50
                }
            ]
        }

        # 执行性能测试
        start_time = time.time()
        for _ in range(100):
            result = self.converter.convert_messages([complex_message])
        end_time = time.time()

        # 验证性能要求（应在1秒内完成100次转换）
        conversion_time = end_time - start_time
        self.assertLess(conversion_time, 1.0,
                       f"Perfomance regression: {conversion_time:.3f}s for 100 conversions")


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)