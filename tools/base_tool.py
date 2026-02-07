"""
工具基类
定义了所有工具的基本接口和行为
"""
from typing import Dict, Any


class ToolResult:
    """
    工具执行结果类

    属性:
        success: 是否执行成功
        output: 执行输出内容
        error: 错误信息(如果有)
    """

    def __init__(self, success: bool = True, output: str = "", error: str = ""):
        """
        初始化工具结果

        参数:
            success: 是否成功
            output: 输出内容
            error: 错误信息
        """
        self.success = success
        self.output = output
        self.error = error

    def __str__(self):
        """返回可读的字符串表示"""
        if self.success:
            return f"成功: {self.output}"
        else:
            return f"失败: {self.error}"


class BaseTool:
    """
    工具基类

    所有工具都需要继承这个类并实现 execute 方法

    属性:
        name: 工具名称
        description: 工具描述
    """

    def __init__(self, name: str, description: str):
        """
        初始化工具

        参数:
            name: 工具名称
            description: 工具描述
        """
        self.name = name
        self.description = description

    def execute(self, **kwargs) -> ToolResult:
        """
        执行工具

        这是一个抽象方法,子类必须实现它

        参数:
            **kwargs: 工具执行所需的参数

        返回:
            ToolResult: 工具执行结果
        """
        raise NotImplementedError("子类必须实现 execute 方法")

    def get_schema(self) -> Dict[str, Any]:
        """
        获取工具的参数定义(用于LLM理解如何调用工具)

        返回:
            工具的JSON Schema定义
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters()
            }
        }

    def get_parameters(self) -> Dict[str, Any]:
        """
        获取工具的参数定义

        子类可以重写这个方法来定义具体的参数

        返回:
            参数的JSON Schema
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
