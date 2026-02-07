"""
简化的配置管理系统
这个文件负责加载和管理应用的配置信息
"""
import json
from pathlib import Path
from typing import Dict, Optional


class SimpleConfig:
    """
    简单的配置类

    功能:
    1. 从JSON文件加载配置
    2. 提供访问配置的简单方法
    3. 不使用复杂的单例模式或线程锁
    """

    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置

        参数:
            config_file: 配置文件路径(相对于config目录)
        """
        # 获取配置文件的完整路径
        self.config_dir = Path(__file__).parent
        self.config_path = self.config_dir / config_file

        # 加载配置
        self.config_data = self._load_config()

    def _load_config(self) -> Dict:
        """
        从JSON文件加载配置

        返回:
            配置字典
        """
        # 如果配置文件不存在,返回默认配置
        if not self.config_path.exists():
            print(f"警告: 配置文件 {self.config_path} 不存在,使用默认配置")
            return self._get_default_config()

        # 读取并解析JSON配置
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """
        获取默认配置

        返回:
            默认配置字典
        """
        return {
            "llm": {
                "model": "gpt-4o",
                "api_key": "your-api-key-here",
                "base_url": "https://api.openai.com/v1",
                "temperature": 0.7,
                "max_tokens": 4096
            },
            "workspace": {
                "root_dir": "./workspace",
                "max_file_size": 1048576  # 1MB
            },
            "agent": {
                "max_steps": 20,
                "max_retry": 3
            }
        }

    def get(self, key: str, default=None):
        """
        获取配置项的值

        参数:
            key: 配置项的键,支持点号分隔的嵌套键(如 "llm.model")
            default: 如果键不存在返回的默认值

        返回:
            配置项的值
        """
        # 支持嵌套的键,如 "llm.model"
        keys = key.split('.')
        value = self.config_data

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_llm_config(self) -> Dict:
        """
        获取LLM配置

        返回:
            LLM配置字典
        """
        return self.get("llm", {})

    def get_workspace_dir(self) -> Path:
        """
        获取工作空间目录

        返回:
            工作空间目录路径
        """
        workspace_dir = self.get("workspace.root_dir", "./workspace")
        path = Path(workspace_dir)

        # 如果目录不存在,创建它
        path.mkdir(parents=True, exist_ok=True)

        return path

    def get_max_steps(self) -> int:
        """
        获取Agent最大执行步数

        返回:
            最大步数
        """
        return self.get("agent.max_steps", 20)


# 创建一个全局配置实例,方便其他模块使用
# 注意:这是一个简单的全局变量,不是复杂的单例模式
global_config = SimpleConfig()
