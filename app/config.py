"""
轻量级配置管理 - 优先使用环境变量
简单、快速、无依赖
"""

import os
import json


class LiteConfig:
    """轻量级配置管理器"""

    def __init__(self):
        self.config = self._load_default_config()
        self.load_config()  # 尝试加载配置文件
        # 重新加载环境变量以确保优先级
        self._load_env_overrides()

    def _load_default_config(self):
        """加载默认配置"""
        return {
            "openai": {
                "api_key": os.getenv('OPENAI_API_KEY', ''),
                "base_url": os.getenv('OPENAI_BASE_URL', 'https://apis.iflow.cn/v1')
            },
            "server": {
                "host": os.getenv('SERVER_HOST', '127.0.0.1'),
                "port": int(os.getenv('SERVER_PORT', '10000')),
                "debug": os.getenv('DEBUG', 'false').lower() == 'true'
            },
            "features": {
                "disable_stream": False
            }
        }

    def get_openai_config(self):
        """获取OpenAI配置"""
        return self.config['openai']

    def get_server_config(self):
        """获取服务器配置"""
        return self.config['server']

    def update_openai_config(self, api_key=None, base_url=None):
        """更新OpenAI配置"""
        if api_key is not None:
            self.config['openai']['api_key'] = api_key
        if base_url is not None:
            self.config['openai']['base_url'] = base_url

    def update_server_config(self, host=None, port=None, debug=None):
        """更新服务器配置"""
        if host is not None:
            self.config['server']['host'] = host
        if port is not None:
            self.config['server']['port'] = port
        if debug is not None:
            self.config['server']['debug'] = debug

    def get_features(self):
        """获取功能开关"""
        return self.config.get('features', {"disable_stream": False})

    def save_config(self):
        """保存配置到文件（可选）"""
        try:
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False

    def load_config(self):
        """从文件加载配置（可选）"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                # 深度合并配置
                self._deep_merge(self.config, file_config)
            return True
        except:
            return False

    def _deep_merge(self, base_dict, update_dict):
        """深度合并字典"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value

    def _load_env_overrides(self):
        """加载环境变量覆盖配置"""
        # OpenAI配置
        if os.getenv('OPENAI_API_KEY'):
            self.config['openai']['api_key'] = os.getenv('OPENAI_API_KEY')
        if os.getenv('OPENAI_BASE_URL'):
            self.config['openai']['base_url'] = os.getenv('OPENAI_BASE_URL')
        
        # 服务器配置
        if os.getenv('SERVER_HOST'):
            self.config['server']['host'] = os.getenv('SERVER_HOST')
        if os.getenv('SERVER_PORT'):
            self.config['server']['port'] = int(os.getenv('SERVER_PORT'))
        if os.getenv('DEBUG'):
            self.config['server']['debug'] = os.getenv('DEBUG').lower() == 'true'
