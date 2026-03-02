"""
LLM客户端
负责与大语言模型API进行交互
"""
import json
from typing import List, Dict, Any, Optional
try:
    from openai import OpenAI
except ImportError:
    print("警告: openai库未安装,请运行: pip install openai")
    OpenAI = None


class LLMClient:
    """
    LLM客户端类

    封装与大语言模型的交互逻辑

    属性:
        model: 模型名称
        client: OpenAI客户端实例
        temperature: 温度参数
        max_tokens: 最大token数
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ):
        """
        初始化LLM客户端

        参数:
            model: 模型名称(如 "gpt-4o")
            api_key: API密钥
            base_url: API基础URL
            temperature: 温度参数(0-2)
            max_tokens: 最大token数（None 表示不限制，使用模型默认值）
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # 初始化OpenAI客户端
        if OpenAI is None:
            raise ImportError("需要安装openai库: pip install openai")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> Dict[str, Any]:
        """
        发送聊天请求

        参数:
            messages: 消息列表
            tools: 可用工具列表
            tool_choice: 工具选择策略("auto", "none", "required")

        返回:
            LLM的响应
        """
        try:
            # 构建请求参数
            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
            }

            if self.max_tokens is not None:
                request_params["max_tokens"] = self.max_tokens

            # 如果提供了工具,添加工具参数
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = tool_choice

            # 发送请求
            response = self.client.chat.completions.create(**request_params)

            # 提取响应内容
            message = response.choices[0].message

            result = {
                "role": message.role,
                "content": message.content
            }

            # 如果有工具调用,添加到结果中
            if hasattr(message, 'tool_calls') and message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]

            return result

        except Exception as e:
            raise Exception(f"LLM请求失败: {str(e)}")

    def parse_tool_calls(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        解析工具调用

        参数:
            response: LLM响应

        返回:
            解析后的工具调用列表
        """
        if "tool_calls" not in response:
            return []

        parsed_calls = []
        for tool_call in response["tool_calls"]:
            try:
                # 解析参数JSON
                arguments = json.loads(tool_call["function"]["arguments"])

                parsed_calls.append({
                    "id": tool_call["id"],
                    "name": tool_call["function"]["name"],
                    "arguments": arguments
                })
            except json.JSONDecodeError as e:
                print(f"警告: 无法解析工具调用参数: {e}")
                continue

        return parsed_calls
