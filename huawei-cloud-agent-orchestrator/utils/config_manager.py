"""
配置文件管理器
加载和管理应用的配置
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """配置管理器 - 单例模式"""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """加载配置文件"""
        config_path = Path("config.yaml")

        if not config_path.exists():
            # 使用默认配置
            print("警告: 未找到config.yaml文件，使用默认配置")
            self._config = self._get_default_config()
        else:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f)
                print("✓ 配置文件加载成功")
            except Exception as e:
                print(f"加载配置文件失败: {e}，使用默认配置")
                self._config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "llm": {
                "provider": "anthropic",
                "api_key": os.environ.get("LLM_API_KEY", ""),
                "endpoint": "",
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 4096,
                "temperature": 0.1
            },
            "huaweicloud": {
                "ak": os.environ.get("HUAWEICLOUD_SDK_AK", ""),
                "sk": os.environ.get("HUAWEICLOUD_SDK_SK", ""),
                "region": "cn-north-4",
                "project_id": ""
            },
            "services": {
                "enabled_services": ["ecs", "vpc", "rds", "obs", "cce", "elb"]
            },
            "workflow": {
                "max_concurrent_tasks": 10,
                "default_timeout": 600,
                "retry_policy": {
                    "max_attempts": 3,
                    "backoff_type": "exponential",
                    "initial_delay": 1
                }
            },
            "server": {
                "host": "0.0.0.0",
                "port": 8000
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号分隔的路径

        Args:
            key: 配置键，如 "llm.api_key" 或 "huaweicloud.region"
            default: 默认值

        Returns:
            配置值
        """
        if not self._config:
            return default

        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置"""
        return self.get('llm', {})

    def get_huaweicloud_config(self) -> Dict[str, Any]:
        """获取华为云配置"""
        return self.get('huaweicloud', {})

    def get_workflow_config(self) -> Dict[str, Any]:
        """获取工作流配置"""
        return self.get('workflow', {})

    def get_server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return self.get('server', {})

    def set(self, key: str, value: Any):
        """设置配置值"""
        if not self._config:
            self._config = {}

        keys = key.split('.')
        config = self._config

        # 遍历到倒数第二层
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # 设置最终值
        config[keys[-1]] = value

    def reload(self):
        """重新加载配置文件"""
        self._load_config()

    def save(self, path: str = "config.yaml"):
        """保存配置到文件"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
            print(f"配置已保存到 {path}")
        except Exception as e:
            print(f"保存配置文件失败: {e}")


# 全局配置管理器实例
def get_config():
    """获取配置管理器实例"""
    return ConfigManager()


if __name__ == "__main__":
    # 测试配置管理器
    config = get_config()

    print("LLM配置:")
    print(f"  Provider: {config.get('llm.provider')}")
    print(f"  Model: {config.get('llm.model')}")
    print(f"  API Key: {'***' if config.get('llm.api_key') else 'None'}")

    print("\n华为云配置:")
    print(f"  Region: {config.get('huaweicloud.region')}")
    print(f"  AK: {'***' if config.get('huaweicloud.ak') else 'None'}")

    print("\n服务器配置:")
    print(f"  Host: {config.get('server.host')}")
    print(f"  Port: {config.get('server.port')}")
