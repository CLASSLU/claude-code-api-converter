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
        # OpenAI配置环境变量覆盖
        if os.getenv('OPENAI_API_KEY'):
            self.config['openai']['api_key'] = os.getenv('OPENAI_API_KEY')
        if os.getenv('OPENAI_BASE_URL'):
            self.config['openai']['base_url'] = os.getenv('OPENAI_BASE_URL')

        # 服务器配置环境变量覆盖
        if os.getenv('SERVER_HOST'):
            self.config['server']['host'] = os.getenv('SERVER_HOST')
        if os.getenv('SERVER_PORT'):
            try:
                self.config['server']['port'] = int(os.getenv('SERVER_PORT'))
            except ValueError:
                pass  # 保持默认值
        if os.getenv('DEBUG'):
            self.config['server']['debug'] = os.getenv('DEBUG').lower() == 'true'

        # 日志配置环境变量覆盖
        if 'logging' not in self.config:
            self.config['logging'] = {}
        if os.getenv('LOG_LEVEL'):
            self.config['logging']['level'] = os.getenv('LOG_LEVEL')
        if os.getenv('LOG_TO_FILE'):
            self.config['logging']['log_to_file'] = os.getenv('LOG_TO_FILE').lower() == 'true'

    def get_flask_config(self):
        """
        获取Flask应用配置
        返回Flask可用的配置字典
        """
        flask_config = {}

        # 服务器配置
        server_config = self.config.get('server', {})
        flask_config['SERVER_HOST'] = server_config.get('host', '0.0.0.0')
        flask_config['SERVER_PORT'] = server_config.get('port', 8080)
        flask_config['DEBUG'] = server_config.get('debug', False)

        # 日志配置
        flask_config['LOGGING_CONFIG'] = self.config.get('logging', {})

        # 功能开关
        flask_config['ENABLE_PERFORMANCE_MONITORING'] = self.config.get('features', {}).get('enable_performance_monitoring', True)
        flask_config['ENABLE_CACHING'] = self.config.get('features', {}).get('enable_caching', True)

        return flask_config

    def update_config(self, new_config):
        """
        更新配置
        深度合并新配置到现有配置
        """
        if not isinstance(new_config, dict):
            raise ValueError("Configuration must be a dictionary")

        self._deep_merge(self.config, new_config)
        # 重新加载环境变量以确保优先级
        self._load_env_overrides()

    def get_safe_config(self):
        """
        获取安全的配置信息（脱敏敏感信息）
        """
        safe_config = {}

        # 深度复制配置
        import copy
        safe_config = copy.deepcopy(self.config)

        # 脱敏API密钥
        if 'openai' in safe_config and 'api_key' in safe_config['openai']:
            api_key = safe_config['openai']['api_key']
            if api_key:
                # 只显示前4位和后4位
                safe_config['openai']['api_key'] = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"

        return safe_config

    def reload_from_file(self):
        """
        从文件重新加载配置
        """
        # 重新加载默认配置
        self.config = self._load_default_config()

        # 重新加载文件配置
        self.load_config()

        # 重新加载环境变量
        self._load_env_overrides()

    # 服务器配置
        if os.getenv('SERVER_HOST'):
            self.config['server']['host'] = os.getenv('SERVER_HOST')
