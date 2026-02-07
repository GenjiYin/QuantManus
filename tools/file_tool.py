"""
文件操作工具
提供读取、写入、编辑文件的功能
"""
from pathlib import Path
from typing import Dict, Any
from .base_tool import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """
    读取文件工具
    """

    def __init__(self):
        super().__init__(
            name="read_file",
            description="读取指定路径的文件内容"
        )

    def execute(self, file_path: str) -> ToolResult:
        """
        读取文件

        参数:
            file_path: 文件路径

        返回:
            ToolResult: 包含文件内容或错误信息
        """
        try:
            path = Path(file_path)

            # 检查文件是否存在
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"文件不存在: {file_path}"
                )

            # 检查是否是文件(不是目录)
            if not path.is_file():
                return ToolResult(
                    success=False,
                    error=f"路径不是文件: {file_path}"
                )

            # 读取文件内容
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            return ToolResult(
                success=True,
                output=content
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"读取文件失败: {str(e)}"
            )

    def get_parameters(self) -> Dict[str, Any]:
        """定义工具参数"""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要读取的文件路径"
                }
            },
            "required": ["file_path"]
        }


class WriteFileTool(BaseTool):
    """
    写入文件工具
    """

    def __init__(self):
        super().__init__(
            name="write_file",
            description="将内容写入到指定路径的文件(会覆盖原有内容)"
        )

    def execute(self, file_path: str, content: str) -> ToolResult:
        """
        写入文件

        参数:
            file_path: 文件路径
            content: 要写入的内容

        返回:
            ToolResult: 执行结果
        """
        try:
            path = Path(file_path)

            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            return ToolResult(
                success=True,
                output=f"成功写入文件: {file_path}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"写入文件失败: {str(e)}"
            )

    def get_parameters(self) -> Dict[str, Any]:
        """定义工具参数"""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要写入的文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容"
                }
            },
            "required": ["file_path", "content"]
        }


class ListDirectoryTool(BaseTool):
    """
    列出目录内容工具
    """

    def __init__(self):
        super().__init__(
            name="list_directory",
            description="列出指定目录下的所有文件和子目录"
        )

    def execute(self, directory_path: str) -> ToolResult:
        """
        列出目录内容

        参数:
            directory_path: 目录路径

        返回:
            ToolResult: 包含目录内容列表或错误信息
        """
        try:
            path = Path(directory_path)

            # 检查目录是否存在
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"目录不存在: {directory_path}"
                )

            # 检查是否是目录
            if not path.is_dir():
                return ToolResult(
                    success=False,
                    error=f"路径不是目录: {directory_path}"
                )

            # 列出目录内容
            items = []
            for item in path.iterdir():
                item_type = "目录" if item.is_dir() else "文件"
                items.append(f"[{item_type}] {item.name}")

            output = "\n".join(items) if items else "目录为空"

            return ToolResult(
                success=True,
                output=output
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"列出目录失败: {str(e)}"
            )

    def get_parameters(self) -> Dict[str, Any]:
        """定义工具参数"""
        return {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "要列出的目录路径"
                }
            },
            "required": ["directory_path"]
        }
