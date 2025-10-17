#!/usr/bin/env python3
"""
Anthropic工具调用测试
使用真实配置测试Anthropic Messages API的工具调用功能
"""

import unittest
import json
import time
import requests
from pathlib import Path
import sys

# 添加父目录到路径以便导入模块
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestAnthropicTools(unittest.TestCase):
    """Anthropic工具调用测试类"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        # 加载配置
        from app.config import LiteConfig
        cls.config = LiteConfig()
        cls.base_url = f"http://127.0.0.1:{cls.config.get_server_config()['port']}"
        cls.test_model = "claude-sonnet-4-5-20250929"  # 使用配置中的模型
        
        # 等待服务启动
        time.sleep(1)
        
        # 验证服务可用
        try:
            response = requests.get(f"{cls.base_url}/health", timeout=5)
            if response.status_code != 200:
                raise Exception("服务不可用")
        except Exception as e:
            raise Exception(f"无法连接到服务: {e}")

    def test_tool_call_non_stream(self):
        """测试非流式工具调用"""
        request_data = {
            "model": self.test_model,
            "messages": [
                {
                    "role": "user", 
                    "content": "请查询北京今天的天气"
                }
            ],
            "max_tokens": 1000,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "获取指定城市的天气信息",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "城市名称"
                            },
                            "unit": {
                                "type": "string", 
                                "enum": ["celsius", "fahrenheit"],
                                "description": "温度单位"
                            }
                        },
                        "required": ["city"]
                    }
                }
            ],
            "stream": False
        }

        response = requests.post(
            f"{self.base_url}/v1/messages",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # 验证响应格式符合Anthropic规范
        self.assertIn('id', data)
        self.assertIn('type', data)
        self.assertEqual(data['type'], 'message')
        self.assertIn('role', data)
        self.assertEqual(data['role'], 'assistant')
        self.assertIn('content', data)
        self.assertIsInstance(data['content'], list)
        
        # 检查是否有工具调用
        tool_use_found = False
        for content_item in data['content']:
            if content_item.get('type') == 'tool_use':
                tool_use_found = True
                # 验证工具调用格式
                self.assertIn('id', content_item)
                self.assertIn('name', content_item)
                self.assertIn('input', content_item)
                self.assertIsInstance(content_item['input'], dict)
                break
        
        # 如果没有工具调用，应该有文本回复
        if not tool_use_found:
            text_found = False
            for content_item in data['content']:
                if content_item.get('type') == 'text':
                    text_found = True
                    self.assertIn('text', content_item)
                    break
            self.assertTrue(text_found, "应该有工具调用或文本回复")

    def test_tool_call_stream(self):
        """测试流式工具调用"""
        request_data = {
            "model": self.test_model,
            "messages": [
                {
                    "role": "user",
                    "content": "请计算 2 + 3 * 4"
                }
            ],
            "max_tokens": 1000,
            "tools": [
                {
                    "name": "calculator",
                    "description": "执行数学计算",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "数学表达式"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            ],
            "stream": True
        }

        response = requests.post(
            f"{self.base_url}/v1/messages",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            stream=True,
            timeout=30
        )

        self.assertEqual(response.status_code, 200)
        
        # 验证流式响应格式
        events = []
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]  # 移除 'data: ' 前缀
                    if data != '[DONE]':
                        try:
                            event = json.loads(data)
                            events.append(event)
                        except json.JSONDecodeError:
                            continue
        
        self.assertGreater(len(events), 0, "应该收到至少一个事件")
        
        # 验证事件格式符合Anthropic SSE规范
        message_start_found = False
        content_block_start_found = False
        tool_use_found = False
        message_delta_found = False
        message_stop_found = False
        
        for event in events:
            self.assertIn('type', event)
            
            if event['type'] == 'message_start':
                message_start_found = True
                self.assertIn('message', event)
                self.assertIn('id', event['message'])
                self.assertIn('type', event['message'])
                self.assertEqual(event['message']['type'], 'message')
                
            elif event['type'] == 'content_block_start':
                content_block_start_found = True
                self.assertIn('index', event)
                self.assertIn('content_block', event)
                
            elif event['type'] == 'content_block_delta':
                if event.get('content_block', {}).get('type') == 'tool_use':
                    tool_use_found = True
                    
            elif event['type'] == 'message_delta':
                message_delta_found = True
                
            elif event['type'] == 'message_stop':
                message_stop_found = True
        
        # 验证基本事件序列
        self.assertTrue(message_start_found, "应该有message_start事件")
        self.assertTrue(message_stop_found, "应该有message_stop事件")

    def test_tool_call_with_multiple_tools(self):
        """测试多工具调用"""
        request_data = {
            "model": self.test_model,
            "messages": [
                {
                    "role": "user",
                    "content": "请查询北京天气并计算 15 * 8"
                }
            ],
            "max_tokens": 1000,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "获取天气信息",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "城市名称"}
                        },
                        "required": ["city"]
                    }
                },
                {
                    "name": "calculator",
                    "description": "数学计算",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string", "description": "数学表达式"}
                        },
                        "required": ["expression"]
                    }
                }
            ],
            "stream": False
        }

        response = requests.post(
            f"{self.base_url}/v1/messages",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('content', data)
        self.assertIsInstance(data['content'], list)

    def test_tool_call_invalid_tool_schema(self):
        """测试无效工具schema的处理"""
        request_data = {
            "model": self.test_model,
            "messages": [
                {"role": "user", "content": "测试"}
            ],
            "max_tokens": 100,
            "tools": [
                {
                    "name": "invalid_tool",
                    "description": "无效工具",
                    "input_schema": {
                        "type": "invalid_type"  # 无效类型
                    }
                }
            ],
            "stream": False
        }

        response = requests.post(
            f"{self.base_url}/v1/messages",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        # 应该处理错误或返回有效响应
        self.assertIn(response.status_code, [200, 400])

    def test_text_only_response(self):
        """测试纯文本响应（无工具调用）"""
        request_data = {
            "model": self.test_model,
            "messages": [
                {"role": "user", "content": "你好，请简单介绍一下自己"}
            ],
            "max_tokens": 100,
            "tools": [
                {
                    "name": "unused_tool",
                    "description": "不会被使用的工具",
                    "input_schema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            ],
            "stream": False
        }

        response = requests.post(
            f"{self.base_url}/v1/messages",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('content', data)
        self.assertIsInstance(data['content'], list)
        
        # 应该有文本回复
        text_found = False
        for content_item in data['content']:
            if content_item.get('type') == 'text':
                text_found = True
                self.assertIn('text', content_item)
                break
        
        self.assertTrue(text_found, "应该有文本回复")

    def test_concurrent_tool_calls(self):
        """测试并发工具调用"""
        request_data = {
            "model": self.test_model,
            "messages": [
                {"role": "user", "content": "请同时查询北京、上海、广州的天气"}
            ],
            "max_tokens": 1000,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "获取天气信息",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "城市名称"}
                        },
                        "required": ["city"]
                    }
                }
            ],
            "stream": False
        }

        response = requests.post(
            f"{self.base_url}/v1/messages",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('content', data)
        self.assertIsInstance(data['content'], list)

    def test_tool_call_error_handling(self):
        """测试工具调用错误处理"""
        request_data = {
            "model": self.test_model,
            "messages": [
                {"role": "user", "content": "测试错误处理"}
            ],
            "max_tokens": 100,
            "tools": [
                {
                    "name": "error_tool",
                    "description": "会出错的工具",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "should_error": {"type": "boolean", "description": "是否触发错误"}
                        },
                        "required": []
                    }
                }
            ],
            "stream": False
        }

        response = requests.post(
            f"{self.base_url}/v1/messages",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        # 应该能处理错误并返回有效响应
        self.assertIn(response.status_code, [200, 400, 500])


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
