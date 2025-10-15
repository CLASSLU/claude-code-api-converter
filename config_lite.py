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

    def _load_default_config(self):
        """加载默认配置"""
        return {
            "openai": {
                "api_key": os.getenv('OPENAI_API_KEY', ''),
                "base_url": os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
            },
            "server": {
                "host": os.getenv('SERVER_HOST', '0.0.0.0'),
                "port": int(os.getenv('SERVER_PORT', '8080')),
                "debug": os.getenv('DEBUG', 'false').lower() == 'true'
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
                # 合并配置，环境变量优先
                self.config.update(file_config)
            return True
        except:
            return False