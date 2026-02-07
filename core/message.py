"""
消息类
用于管理Agent与LLM之间的对话消息
"""
from typing import List, Dict, Any, Optional


class Message:
    """
    消息类

    表示对话中的一条消息

    属性:
        role: 消息角色(user/assistant/system/tool)
        content: 消息内容
        tool_calls: 工具调用列表(如果这是一个工具调用消息)
        tool_call_id: 工具调用ID(如果这是工具的返回消息)
    """

    def __init__(
        self,
        role: str,
        content: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None
    ):
        """
        初始化消息

        参数:
            role: 消息角色
            content: 消息内容
            tool_calls: 工具调用列表
            tool_call_id: 工具调用ID
            name: 工具名称(用于tool角色)
        """
        self.role = role
        self.content = content
        self.tool_calls = tool_calls
        self.tool_call_id = tool_call_id
        self.name = name

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式(用于API调用)

        返回:
            消息的字典表示
        """
        result = {
            "role": self.role
        }

        if self.content is not None:
            result["content"] = self.content

        if self.tool_calls is not None:
            result["tool_calls"] = self.tool_calls

        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id

        if self.name is not None:
            result["name"] = self.name

        return result

    @staticmethod
    def user_message(content: str) -> "Message":
        """
        创建用户消息

        参数:
            content: 消息内容

        返回:
            用户消息对象
        """
        return Message(role="user", content=content)

    @staticmethod
    def assistant_message(content: str) -> "Message":
        """
        创建助手消息

        参数:
            content: 消息内容

        返回:
            助手消息对象
        """
        return Message(role="assistant", content=content)

    @staticmethod
    def system_message(content: str) -> "Message":
        """
        创建系统消息

        参数:
            content: 消息内容

        返回:
            系统消息对象
        """
        return Message(role="system", content=content)

    @staticmethod
    def tool_message(tool_call_id: str, name: str, content: str) -> "Message":
        """
        创建工具返回消息

        参数:
            tool_call_id: 工具调用ID
            name: 工具名称
            content: 工具返回内容

        返回:
            工具消息对象
        """
        return Message(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=name
        )


class MessageHistory:
    """
    消息历史类

    管理对话的消息历史

    属性:
        messages: 消息列表
        max_messages: 最大保存消息数
    """

    def __init__(self, max_messages: int = 100):
        """
        初始化消息历史

        参数:
            max_messages: 最大保存的消息数量
        """
        self.messages: List[Message] = []
        self.max_messages = max_messages

    def add_message(self, message: Message):
        """
        添加一条消息

        参数:
            message: 要添加的消息
        """
        self.messages.append(message)

        # 如果超过最大数量,删除最旧的消息(保留系统消息)
        if len(self.messages) > self.max_messages:
            # 找到第一个非系统消息并删除
            for i, msg in enumerate(self.messages):
                if msg.role != "system":
                    self.messages.pop(i)
                    break

    def get_messages_as_dicts(self) -> List[Dict[str, Any]]:
        """
        获取所有消息的字典表示

        返回:
            消息字典列表
        """
        return [msg.to_dict() for msg in self.messages]

    def clear(self):
        """清空消息历史"""
        self.messages.clear()

    def get_last_n_messages(self, n: int) -> List[Message]:
        """
        获取最后n条消息

        参数:
            n: 消息数量

        返回:
            消息列表
        """
        return self.messages[-n:] if n > 0 else []
