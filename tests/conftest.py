"""
pytest配置文件
提供测试夹具和全局配置
"""

import pytest
import sys
import tempfile
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_config():
    """测试配置夹具"""
    return {
        "openai": {
            "api_key": "test-api-key-123456",
            "base_url": "https://api.example.com/v1"
        },
        "server": {
            "host": "127.0.0.1",
            "port": 8080,
            "debug": False
        },
        "logging": {
            "level": "INFO",
            "log_to_file": False
        },
        "features": {
            "enable_performance_monitoring": True,
            "enable_caching": True
        },
        "model_mappings": [
            {
                "anthropic": "claude-3-5-haiku-20241022",
                "openai": "gpt-4"
            }
        ]
    }


@pytest.fixture
def sample_anthropic_request():
    """示例Anthropic请求"""
    return {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": "Hello, how are you?"
            }
        ],
        "stream": False
    }


@pytest.fixture
def sample_openai_request():
    """示例OpenAI请求"""
    return {
        "model": "gpt-4",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": "Hello, how are you?"
            }
        ],
        "stream": False
    }


@pytest.fixture
def sample_openai_response():
    """示例OpenAI响应"""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello! I'm doing well, thank you for asking. How can I help you today?"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 18,
            "total_tokens": 38
        }
    }


@pytest.fixture
def temp_config_file(sample_config):
    """临时配置文件夹具"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        import json
        json.dump(sample_config, f)
        temp_path = f.name

    yield temp_path

    # 清理
    os.unlink(temp_path)


@pytest.fixture
def app_context(sample_config):
    """Flask应用上下文夹具"""
    from app import create_app
    app = create_app()

    # 模拟配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        import json
        json.dump(sample_config, f)
        config_path = f.name

    # 设置配置文件路径
    os.environ['CONFIG_FILE'] = config_path

    with app.app_context():
        yield app

    # 清理
    os.unlink(config_path)
    if 'CONFIG_FILE' in os.environ:
        del os.environ['CONFIG_FILE']


@pytest.fixture
def client(app_context):
    """Flask测试客户端"""
    return app_context.test_client()


@pytest.fixture
def mock_requests(monkeypatch):
    """模拟requests库"""
    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self.json_data = json_data
            self.status_code = status_code
            self.content = json.dumps(json_data).encode()

        def json(self):
            return self.json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")

    def mock_post(*args, **kwargs):
        return MockResponse({"test": "response"})

    def mock_get(*args, **kwargs):
        return MockResponse({"data": [{"id": "model1", "object": "model"}]})

    monkeypatch.setattr("requests.post", mock_post)
    monkeypatch.setattr("requests.get", mock_get)


@pytest.fixture(scope="session", autouse=True)
def configure_test_logging():
    """配置测试日志"""
    import logging
    logging.getLogger().setLevel(logging.WARNING)


# 性能测试标记
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )