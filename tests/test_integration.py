"""
API服务器集成测试
测试所有端点的功能和响应格式
"""

import unittest
import json
import time
import threading
import requests
from pathlib import Path
import sys

# 添加父目录到路径以便导入模块
sys.path.insert(0, str(Path(__file__).parent.parent))



class TestAPIServer(unittest.TestCase):
    """API服务器集成测试类"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化，启动服务器"""
        # 设置测试环境变量
        import os
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['LOG_LEVEL'] = 'ERROR'  # 测试时减少日志输出

        # 启动测试服务器
        from app.server import app as flask_app
        cls.app = flask_app
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        # 启动实际服务器进行完整测试
        cls.server_thread = threading.Thread(
            target=lambda: cls.app.run(
                host='127.0.0.1',
                port=8081,
                debug=False,
                use_reloader=False
            ),
            daemon=True
        )
        cls.server_thread.start()

        # 等待服务器启动
        time.sleep(2)
        cls.base_url = 'http://127.0.0.1:8081'  # unchanged, uses test thread

    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')

    def test_models_endpoint(self):
        """测试模型列表端点"""
        response = self.client.get('/v1/models')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data['object'], 'list')
        self.assertIsInstance(data['data'], list)
        self.assertGreater(len(data['data']), 0)

    def test_config_endpoint_get(self):
        """测试配置获取端点"""
        response = self.client.get('/config')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIn('openai', data)
        self.assertIn('server', data)
        self.assertIn('logging', data)

    def test_count_tokens_endpoint(self):
        """测试token计数端点"""
        # 测试messages参数
        request_data = {
            "messages": [
                {"role": "user", "content": "Hello, how are you?"}
            ]
        }

        response = self.client.post(
            '/v1/messages/count_tokens',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('input_tokens', data)
        self.assertGreater(data['input_tokens'], 0)

    def test_count_tokens_text_parameter(self):
        """测试token计数端点的text参数"""
        request_data = {
            "text": "This is a test message for token counting."
        }

        response = self.client.post(
            '/v1/messages/count_tokens',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('input_tokens', data)
        self.assertGreater(data['input_tokens'], 0)

    def test_messages_endpoint_invalid_request(self):
        """测试消息端点的无效请求"""
        # 缺少messages字段
        request_data = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 10
        }

        response = self.client.post(
            '/v1/messages',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_messages_endpoint_valid_request(self):
        """测试消息端点的有效请求（使用模拟响应）"""
        request_data = {
            "model": "claude-3-sonnet-20240229",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 10
        }

        response = self.client.post(
            '/v1/messages',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        # 由于GitCode API不支持，应该返回模拟响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # 检查是否是模拟响应
        if 'content' in data:
            self.assertIsInstance(data['content'], list)
            if data['content'] and isinstance(data['content'][0], dict):
                self.assertIn('text', data['content'][0])

    def test_chat_completions_endpoint_invalid_request(self):
        """测试OpenAI聊天端点的无效请求"""
        # 缺少messages字段
        request_data = {
            "model": "gpt-4",
            "max_tokens": 10
        }

        response = self.client.post(
            '/v1/chat/completions',
            data=json.dumps(request_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_config_endpoint_update(self):
        """测试配置更新端点"""
        update_data = {
            "server": {
                "host": "0.0.0.0",
                "port": 8080,
                "debug": False
            }
        }

        response = self.client.post(
            '/config',
            data=json.dumps(update_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')

    def test_error_handling_invalid_json(self):
        """测试无效JSON的错误处理"""
        response = self.client.post(
            '/v1/messages',
            data='invalid json',
            content_type='application/json'
        )

        # 应该返回400错误
        self.assertEqual(response.status_code, 400)

    def test_error_handling_missing_endpoint(self):
        """测试不存在端点的错误处理"""
        response = self.client.get('/nonexistent/endpoint')
        self.assertEqual(response.status_code, 404)

    def test_response_headers(self):
        """测试响应头"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)

        # 检查Content-Type
        self.assertIn('Content-Type', response.headers)
        self.assertIn('application/json', response.headers['Content-Type'])

    def test_utf8_encoding(self):
        """测试UTF-8编码处理"""
        request_data = {
            "messages": [
                {"role": "user", "content": "你好，世界！🌍"}
            ]
        }

        response = self.client.post(
            '/v1/messages/count_tokens',
            data=json.dumps(request_data, ensure_ascii=False),
            content_type='application/json; charset=utf-8'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('input_tokens', data)

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        # 清理环境变量
        import os
        if 'FLASK_ENV' in os.environ:
            del os.environ['FLASK_ENV']
        if 'LOG_LEVEL' in os.environ:
            del os.environ['LOG_LEVEL']


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)