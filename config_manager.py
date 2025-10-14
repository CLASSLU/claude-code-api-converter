import json
import os
from typing import Dict, List, Any

class ConfigManager:
    def __init__(self, config_file: str = 'config.json'):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    print(f"成功加载配置文件: {self.config_file}")
                    return config
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"配置文件加载失败: {self.config_file}, 错误: {e}")
        
        # 返回默认配置
        print("使用默认配置")
        return self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "openai": {
                "api_key": "sk-3b7873164cc06ed48ebd1816ad8874df",
                "base_url": "https://apis.iflow.cn/v1"
            },
            "server": {
                "host": "0.0.0.0",
                "port": 8080,
                "debug": True
            }
        }
    
    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            print(f"配置已成功保存到: {self.config_file}")
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def get_openai_config(self) -> Dict[str, str]:
        """获取OpenAI配置"""
        return self.config.get("openai", {})
    
    def get_server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return self.config.get("server", {})
    
    def update_openai_config(self, api_key: str = None, base_url: str = None) -> None:
        """更新OpenAI配置"""
        if "openai" not in self.config:
            self.config["openai"] = {}
        
        if api_key is not None:
            self.config["openai"]["api_key"] = api_key
        if base_url is not None:
            self.config["openai"]["base_url"] = base_url
    
    def update_server_config(self, host: str = None, port: int = None, debug: bool = None) -> None:
        """更新服务器配置"""
        if "server" not in self.config:
            self.config["server"] = {}
        
        if host is not None:
            self.config["server"]["host"] = host
        if port is not None:
            self.config["server"]["port"] = port
        if debug is not None:
            self.config["server"]["debug"] = debug
