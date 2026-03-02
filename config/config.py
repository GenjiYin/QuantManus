"""
简化的配置管理系统
这个文件负责加载和管理应用的配置信息

全局配置存放在 ~/.quantmanus/config.json
工作空间跟随当前工作目录 (os.getcwd())
"""
import json
from pathlib import Path
from typing import Dict, Optional


class SimpleConfig:
    """
    简单的配置类

    功能:
    1. 从 ~/.quantmanus/config.json 加载全局配置
    2. 首次运行时自动创建默认配置文件
    3. 工作空间 = 当前工作目录
    """

    def __init__(self):
        """
        初始化配置

        配置文件固定位于 ~/.quantmanus/config.json
        """
        self.config_dir = Path.home() / ".quantmanus"
        self.config_path = self.config_dir / "config.json"

        # 加载配置（文件不存在时用默认值）
        if self.config_path.exists():
            self.config_data = self._load_config()
            self._migrate_config()
        else:
            self.config_data = self._get_default_config()

    @property
    def is_configured(self) -> bool:
        """检查是否已完成配置（API Key 不是占位符）"""
        api_key = self.get("llm.api_key", "")
        return bool(api_key) and api_key != "your-api-key-here"

    def save(self):
        """将当前配置写入磁盘"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config_data, f, indent=2, ensure_ascii=False)

    def _load_config(self) -> Dict:
        """
        从JSON文件加载配置

        返回:
            配置字典
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return self._get_default_config()

    def _migrate_config(self):
        """迁移旧配置：将 max_tokens=4096 改为 None（不限制，使用模型默认值）"""
        llm = self.config_data.get("llm", {})
        if llm.get("max_tokens") == 4096:
            llm["max_tokens"] = None
            self.save()

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
                "max_tokens": None
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
        获取工作空间目录（当前工作目录）

        返回:
            当前工作目录路径
        """
        return Path.cwd()

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
