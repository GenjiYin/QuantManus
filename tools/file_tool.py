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

            # 如果文件已存在，请求用户确认覆盖
            if path.exists():
                print(f"\n⚠️  文件已存在: {file_path}")
                confirm = input("是否覆盖该文件？(y/n): ").strip().lower()
                if confirm != 'y':
                    return ToolResult(
                        success=False,
                        error=f"用户取消了文件覆盖: {file_path}"
                    )

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


class DeleteFileTool(BaseTool):
    """
    删除文件工具
    """

    def __init__(self):
        super().__init__(
            name="delete_file",
            description="删除指定路径的文件，执行前会请求用户确认"
        )

    def execute(self, file_path: str) -> ToolResult:
        """
        删除文件

        参数:
            file_path: 文件路径

        返回:
            ToolResult: 执行结果
        """
        try:
            path = Path(file_path)

            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"文件不存在: {file_path}"
                )

            if not path.is_file():
                return ToolResult(
                    success=False,
                    error=f"路径不是文件: {file_path}"
                )

            print(f"\n⚠️  即将删除文件: {file_path}")
            confirm = input("确认删除？(y/n): ").strip().lower()
            if confirm != 'y':
                return ToolResult(
                    success=False,
                    error=f"用户取消了文件删除: {file_path}"
                )

            path.unlink()
            return ToolResult(
                success=True,
                output=f"已删除文件: {file_path}"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"删除文件失败: {str(e)}"
            )

    def get_parameters(self) -> Dict[str, Any]:
        """定义工具参数"""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要删除的文件路径"
                }
            },
            "required": ["file_path"]
        }


class ListDirectoryTool(BaseTool):
    """
    列出目录内容工具
    """

    def __init__(self):
        super().__init__(
            name="list_directory",
            description="列出指定目录下的所有文件和子目录。可选择是否递归列出所有子目录的内容。"
        )

    def execute(self, directory_path: str, recursive: bool = False, max_depth: int = 3) -> ToolResult:
        """
        列出目录内容

        参数:
            directory_path: 目录路径
            recursive: 是否递归列出子目录内容（默认False）
            max_depth: 递归的最大深度（默认3层，防止过深）

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
            if recursive:
                output = self._list_recursive(path, max_depth=max_depth)
            else:
                output = self._list_single_level(path)

            return ToolResult(
                success=True,
                output=output
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"列出目录失败: {str(e)}"
            )

    def _list_single_level(self, path: Path) -> str:
        """列出单层目录内容"""
        items = []
        files = []
        dirs = []

        for item in sorted(path.iterdir()):
            if item.is_dir():
                # 使用完整绝对路径，方便AI后续使用
                dirs.append(f"📁 [目录] {item.name}\n   完整路径: {item.absolute()}")
            else:
                # 显示文件大小
                size = item.stat().st_size
                size_str = self._format_size(size)
                files.append(f"📄 [文件] {item.name} ({size_str})\n   完整路径: {item.absolute()}")

        # 先显示目录，再显示文件
        items = dirs + files

        if not items:
            return f"目录为空: {path}"

        header = f"目录: {path.absolute()}\n" + "=" * 60 + "\n"
        summary = f"\n" + "-" * 60 + f"\n共 {len(dirs)} 个子目录, {len(files)} 个文件\n\n💡 提示：使用上面的'完整路径'来访问文件或子目录"

        return header + "\n".join(items) + summary

    def _list_recursive(self, path: Path, max_depth: int, current_depth: int = 0, prefix: str = "") -> str:
        """递归列出目录内容"""
        if current_depth > max_depth:
            return f"{prefix}[已达最大深度限制]"

        items = []
        try:
            sorted_items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))

            for i, item in enumerate(sorted_items):
                is_last = (i == len(sorted_items) - 1)
                connector = "└── " if is_last else "├── "
                next_prefix = prefix + ("    " if is_last else "│   ")

                if item.is_dir():
                    # 显示目录名和完整路径
                    items.append(f"{prefix}{connector}📁 {item.name}/ → {item.absolute()}")
                    # 递归列出子目录
                    sub_items = self._list_recursive(item, max_depth, current_depth + 1, next_prefix)
                    if sub_items:
                        items.append(sub_items)
                else:
                    size = item.stat().st_size
                    size_str = self._format_size(size)
                    items.append(f"{prefix}{connector}📄 {item.name} ({size_str}) → {item.absolute()}")

        except PermissionError:
            items.append(f"{prefix}[权限不足]")

        return "\n".join(items)

    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}TB"

    def get_parameters(self) -> Dict[str, Any]:
        """定义工具参数"""
        return {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "要列出的目录路径（绝对路径或相对路径）"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出所有子目录的内容。True=显示目录树结构，False=仅显示当前目录（默认False）",
                    "default": False
                },
                "max_depth": {
                    "type": "integer",
                    "description": "递归时的最大深度，防止过深（默认3层）",
                    "default": 3
                }
            },
            "required": ["directory_path"]
        }
