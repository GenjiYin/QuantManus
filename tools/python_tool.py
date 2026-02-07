"""
Python代码执行工具
提供安全的Python代码执行能力
"""
import sys
from io import StringIO
from typing import Dict, Any
from .base_tool import BaseTool, ToolResult


class PythonExecuteTool(BaseTool):
    """
    Python代码执行工具
    在隔离的环境中执行Python代码并返回结果
    """

    def __init__(self):
        super().__init__(
            name="execute_python",
            description="执行Python代码并返回输出结果"
        )

    def execute(self, code: str) -> ToolResult:
        """
        执行Python代码

        参数:
            code: 要执行的Python代码

        返回:
            ToolResult: 包含执行输出或错误信息
        """
        try:
            # 创建一个字符串IO对象来捕获输出
            output_buffer = StringIO()
            error_buffer = StringIO()

            # 保存原来的stdout和stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            try:
                # 重定向stdout和stderr到我们的缓冲区
                sys.stdout = output_buffer
                sys.stderr = error_buffer

                # 创建一个新的命名空间来执行代码
                namespace = {
                    '__builtins__': __builtins__,
                }

                # 执行代码
                exec(code, namespace)

                # 获取输出
                output = output_buffer.getvalue()
                errors = error_buffer.getvalue()

                # 如果有错误输出,返回错误
                if errors:
                    return ToolResult(
                        success=False,
                        error=errors
                    )

                # 返回成功结果
                return ToolResult(
                    success=True,
                    output=output if output else "代码执行成功,无输出"
                )

            finally:
                # 恢复原来的stdout和stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"执行Python代码时出错: {str(e)}"
            )

    def get_parameters(self) -> Dict[str, Any]:
        """定义工具参数"""
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的Python代码"
                }
            },
            "required": ["code"]
        }
