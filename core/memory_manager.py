"""
记忆管理模块
实现智能的上下文记忆管理,防止大模型幻觉

核心功能:
1. 短期记忆 - 保存最近的对话
2. Token 管理 - 精确控制上下文窗口大小

注意: 推荐使用新版持久化记忆系统 (SessionManager + MemoryStore + ContextBuilder)。
本模块保留为简化的工作记忆管理器,供向后兼容使用。
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import json
import time
from collections import deque
import tiktoken


@dataclass
class MemoryItem:
    """
    记忆项

    属性:
        content: 消息内容
        role: 角色(user/assistant/system/tool)
        timestamp: 时间戳
        importance: 重要性评分(0-1)
        tokens: token数量
        metadata: 额外元数据
    """
    content: str
    role: str
    timestamp: float
    importance: float = 0.5
    tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_message_dict(self) -> Dict[str, Any]:
        """转换为消息字典格式"""
        return {
            "role": self.role,
            "content": self.content
        }


class TokenCounter:
    """Token计数器"""

    def __init__(self, model: str = "gpt-4"):
        """
        初始化Token计数器

        参数:
            model: 模型名称,用于选择合适的编码器
        """
        try:
            # 尝试加载对应模型的编码器
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # 如果模型不存在,使用默认的cl100k_base编码器(GPT-4)
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        计算文本的token数量

        参数:
            text: 输入文本

        返回:
            token数量
        """
        return len(self.encoding.encode(text))

    def count_messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        计算消息列表的总token数

        参数:
            messages: 消息列表

        返回:
            总token数
        """
        total_tokens = 0
        for message in messages:
            # 消息格式的固定开销(角色等)
            total_tokens += 4

            # 内容tokens
            if isinstance(message.get("content"), str):
                total_tokens += self.count_tokens(message["content"])

            # 如果有tool_calls,也计算其tokens
            if "tool_calls" in message:
                total_tokens += self.count_tokens(json.dumps(message["tool_calls"]))

        # 固定的对话开销
        total_tokens += 2

        return total_tokens


class MemoryManager:
    """
    简化的工作记忆管理器

    管理短期记忆(Working Memory)和系统记忆(System Memory),
    精确控制上下文窗口大小。
    """

    def __init__(
        self,
        max_working_memory_tokens: int = 2000,
        max_total_tokens: int = 6000,
        compression_threshold: int = 1500,
        llm_client=None,
        model: str = "gpt-4"
    ):
        """
        初始化记忆管理器

        参数:
            max_working_memory_tokens: 短期记忆最大token数
            max_total_tokens: 总上下文最大token数
            compression_threshold: (已废弃,保留参数兼容性)
            llm_client: (已废弃,保留参数兼容性)
            model: 模型名称
        """
        self.max_working_memory_tokens = max_working_memory_tokens
        self.max_total_tokens = max_total_tokens

        # 记忆层
        self.system_messages: List[Dict[str, Any]] = []  # 系统消息(最高优先级)
        self.working_memory: deque = deque(maxlen=100)  # 短期记忆(最近对话)

        # 工具
        self.token_counter = TokenCounter(model)

        # 统计信息
        self.stats = {
            "total_messages": 0,
        }

    def add_system_message(self, content: str):
        """
        添加系统消息

        系统消息会一直保留在上下文中

        参数:
            content: 系统消息内容
        """
        self.system_messages.append({
            "role": "system",
            "content": content
        })

    def add_message(
        self,
        role: str,
        content: str,
        importance: Optional[float] = None,
        **kwargs
    ):
        """
        添加消息到记忆

        参数:
            role: 消息角色
            content: 消息内容
            importance: 重要性评分(0-1),None则自动评估
            **kwargs: 其他消息属性(如tool_calls, tool_call_id等)
        """
        # 自动评估重要性
        if importance is None:
            importance = self._evaluate_importance(role, content, kwargs)

        # 计算tokens
        tokens = self.token_counter.count_tokens(content or "")

        # 创建记忆项
        memory_item = MemoryItem(
            content=content,
            role=role,
            timestamp=time.time(),
            importance=importance,
            tokens=tokens,
            metadata=kwargs
        )

        # 添加到短期记忆
        self.working_memory.append(memory_item)
        self.stats["total_messages"] += 1

        # 当超出容量时,丢弃最旧的消息(deque maxlen自动处理)

    def get_context_messages(self, max_tokens: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取当前上下文消息

        根据token限制和重要性,智能选择要包含的消息

        参数:
            max_tokens: 最大token数(None则使用默认值)

        返回:
            消息列表(按时间顺序)
        """
        if max_tokens is None:
            max_tokens = self.max_total_tokens

        messages = []
        current_tokens = 0

        # 1. 先添加系统消息(最高优先级)
        for sys_msg in self.system_messages:
            messages.append(sys_msg)
            current_tokens += self.token_counter.count_messages_tokens([sys_msg])

        # 2. 添加短期记忆(从最新往前添加，确保工具调用完整性)
        # 策略：先收集所有消息，然后验证并过滤掉不完整的工具调用对
        temp_messages = []  # [(memory_item, msg_dict, msg_tokens), ...]

        for memory_item in reversed(self.working_memory):
            msg_dict = self._memory_item_to_message_dict(memory_item)
            msg_tokens = self.token_counter.count_messages_tokens([msg_dict])

            if current_tokens + msg_tokens <= max_tokens:
                temp_messages.insert(0, (memory_item, msg_dict, msg_tokens))
                current_tokens += msg_tokens
            else:
                # 如果重要性很高,尝试强制包含
                if memory_item.importance >= 0.8 and current_tokens + msg_tokens <= max_tokens * 1.1:
                    temp_messages.insert(0, (memory_item, msg_dict, msg_tokens))
                    current_tokens += msg_tokens
                else:
                    break

        # 验证工具调用完整性
        # 构建tool_call_id映射
        tool_call_ids_in_assistant = set()  # assistant消息中的tool_call_id
        tool_call_ids_in_tool = set()  # tool消息中的tool_call_id

        # 第一遍：收集所有的tool_call_id
        for memory_item, _, _ in temp_messages:
            if memory_item.role == "assistant" and "tool_calls" in memory_item.metadata:
                for tc in memory_item.metadata.get("tool_calls", []):
                    tc_id = tc.get("id")
                    if tc_id:
                        tool_call_ids_in_assistant.add(tc_id)

            if memory_item.role == "tool":
                tc_id = memory_item.metadata.get("tool_call_id")
                if tc_id:
                    tool_call_ids_in_tool.add(tc_id)

        # 过滤：确保工具调用的完整性
        # 策略：优先保留完整的调用对，如果不完整则全部移除以避免API错误
        working_messages = []
        for memory_item, msg_dict, _ in temp_messages:
            # tool消息：必须有对应的assistant tool_calls
            if memory_item.role == "tool":
                tc_id = memory_item.metadata.get("tool_call_id")
                if tc_id:
                    # 只保留有对应assistant调用的tool响应
                    if tc_id in tool_call_ids_in_assistant:
                        working_messages.append(msg_dict)
                    # 否则跳过孤立的tool消息
                else:
                    # tool_call_id为空，这是个问题，直接跳过
                    pass

            # assistant消息包含tool_calls：只保留有对应tool响应的调用
            elif memory_item.role == "assistant" and "tool_calls" in memory_item.metadata:
                # 过滤tool_calls，只保留有对应tool响应的
                valid_tool_calls = []
                for tc in memory_item.metadata.get("tool_calls", []):
                    tc_id = tc.get("id")
                    if tc_id and tc_id in tool_call_ids_in_tool:
                        # 有对应的tool响应，保留
                        valid_tool_calls.append(tc)
                    # 否则跳过（没有对应的tool响应会导致API错误）

                # 构建消息
                if valid_tool_calls:
                    # 有有效的tool_calls，构建包含tool_calls的消息
                    msg_dict_copy = msg_dict.copy()
                    msg_dict_copy["tool_calls"] = valid_tool_calls
                    # 如果原消息没有content，设置为None（符合API要求）
                    if not msg_dict_copy.get("content"):
                        msg_dict_copy["content"] = None
                    working_messages.append(msg_dict_copy)
                elif msg_dict.get("content"):
                    # 没有有效的tool_calls但有content，作为普通assistant消息保留
                    msg_dict_copy = msg_dict.copy()
                    msg_dict_copy.pop("tool_calls", None)
                    working_messages.append(msg_dict_copy)
                # 否则完全跳过（既没有有效tool_calls也没有content）

            # 其他消息：直接包含
            else:
                working_messages.append(msg_dict)

        messages.extend(working_messages)

        return messages

    def _evaluate_importance(self, role: str, content: str, metadata: Dict) -> float:
        """
        评估消息的重要性

        参数:
            role: 消息角色
            content: 消息内容
            metadata: 元数据

        返回:
            重要性评分(0-1)
        """
        importance = 0.5  # 默认中等重要性

        # 用户消息通常重要
        if role == "user":
            importance = 0.8

        # 包含工具调用的消息重要
        if "tool_calls" in metadata:
            importance = max(importance, 0.7)

        # 工具返回结果的重要性取决于内容长度和是否有错误
        if role == "tool":
            if content and len(content) > 500:
                importance = max(importance, 0.6)
            if "error" in content.lower() or "错误" in content.lower():
                importance = max(importance, 0.8)

        # 助手的最终回复重要
        if role == "assistant" and content and "tool_calls" not in metadata:
            if len(content) > 100:  # 详细回复
                importance = 0.7

        return importance

    def _memory_item_to_message_dict(self, item: MemoryItem) -> Dict[str, Any]:
        """
        将MemoryItem转换为消息字典

        参数:
            item: 记忆项

        返回:
            消息字典
        """
        msg = {
            "role": item.role,
            "content": item.content
        }

        # 添加元数据中的其他字段
        for key in ["tool_calls", "tool_call_id", "name"]:
            if key in item.metadata:
                value = item.metadata[key]
                # 验证tool_call_id不为空
                if key == "tool_call_id" and (not value or value.strip() == ""):
                    continue  # 跳过空的tool_call_id
                msg[key] = value

        return msg

    def clear(self):
        """清空所有记忆(保留系统消息)"""
        self.working_memory.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        获取记忆统计信息

        返回:
            统计信息字典
        """
        working_tokens = sum(item.tokens for item in self.working_memory)

        return {
            **self.stats,
            "working_memory_messages": len(self.working_memory),
            "working_memory_tokens": working_tokens,
            "total_context_tokens": working_tokens
        }

    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        print("\n" + "="*50)
        print("记忆管理统计")
        print("="*50)
        print(f"总消息数: {stats['total_messages']}")
        print(f"短期记忆: {stats['working_memory_messages']}条 ({stats['working_memory_tokens']} tokens)")
        print(f"当前上下文: {stats['total_context_tokens']} / {self.max_total_tokens} tokens")
        print("="*50 + "\n")
