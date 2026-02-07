"""
记忆管理模块
实现智能的上下文记忆管理,防止大模型幻觉

核心功能:
1. 短期记忆 - 保存最近的对话
2. 长期记忆 - 压缩重要信息
3. 语义检索 - 根据相关性提取重要上下文
4. Token 管理 - 精确控制上下文窗口大小
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


@dataclass
class CompressedMemory:
    """
    压缩记忆

    存储一段对话的摘要
    """
    summary: str
    original_messages: int
    original_tokens: int
    compressed_tokens: int
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


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


class MemoryCompressor:
    """
    记忆压缩器

    将长对话压缩成简洁的摘要
    """

    def __init__(self, llm_client=None):
        """
        初始化压缩器

        参数:
            llm_client: LLM客户端(用于生成摘要)
        """
        self.llm_client = llm_client
        self.token_counter = TokenCounter()

    def compress_messages(
        self,
        messages: List[Dict[str, Any]],
        target_ratio: float = 0.3
    ) -> CompressedMemory:
        """
        压缩消息列表

        参数:
            messages: 要压缩的消息列表
            target_ratio: 目标压缩比(压缩后/原始)

        返回:
            压缩后的记忆对象
        """
        if not messages:
            return CompressedMemory(
                summary="",
                original_messages=0,
                original_tokens=0,
                compressed_tokens=0,
                timestamp=time.time()
            )

        original_tokens = self.token_counter.count_messages_tokens(messages)

        # 如果没有LLM客户端,使用简单的提取式摘要
        if self.llm_client is None:
            summary = self._simple_compress(messages)
        else:
            summary = self._llm_compress(messages, target_ratio)

        compressed_tokens = self.token_counter.count_tokens(summary)

        return CompressedMemory(
            summary=summary,
            original_messages=len(messages),
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            timestamp=time.time(),
            metadata={
                "compression_ratio": compressed_tokens / original_tokens if original_tokens > 0 else 0
            }
        )

    def _simple_compress(self, messages: List[Dict[str, Any]]) -> str:
        """
        简单压缩(不使用LLM)

        提取关键信息:任务、工具调用、重要结果
        """
        key_points = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                # 保留用户的任务描述(截断过长内容)
                key_points.append(f"任务: {content[:200]}")

            elif role == "assistant" and "tool_calls" in msg:
                # 记录工具调用
                tool_names = [tc["function"]["name"] for tc in msg.get("tool_calls", [])]
                if tool_names:
                    key_points.append(f"执行工具: {', '.join(tool_names)}")

            elif role == "tool":
                # 记录工具结果(只保留简短摘要)
                tool_name = msg.get("name", "未知工具")
                result_preview = content[:150] if content else "无结果"
                key_points.append(f"{tool_name}结果: {result_preview}")

        return "\n".join(key_points) if key_points else "无重要信息"

    def _llm_compress(self, messages: List[Dict[str, Any]], target_ratio: float) -> str:
        """
        使用LLM进行智能压缩

        参数:
            messages: 消息列表
            target_ratio: 目标压缩比

        返回:
            压缩后的摘要
        """
        # 构建压缩提示词
        compress_prompt = f"""请将以下对话历史压缩成简洁的摘要。

要求:
1. 保留所有关键信息:任务目标、重要决策、执行步骤、结果
2. 删除冗余对话和不重要的细节
3. 使用要点形式,清晰简洁
4. 目标长度:原文的{int(target_ratio * 100)}%

对话历史:
{json.dumps(messages, ensure_ascii=False, indent=2)}

请直接输出压缩后的摘要:"""

        try:
            response = self.llm_client.chat(
                messages=[{"role": "user", "content": compress_prompt}],
                tools=None
            )
            return response.get("content", self._simple_compress(messages))

        except Exception as e:
            print(f"LLM压缩失败,使用简单压缩: {e}")
            return self._simple_compress(messages)


class MemoryManager:
    """
    智能记忆管理器

    实现三层记忆架构:
    1. 短期记忆(Working Memory) - 最近的对话
    2. 长期记忆(Long-term Memory) - 压缩的历史摘要
    3. 系统记忆(System Memory) - 系统提示词等固定内容
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
            compression_threshold: 触发压缩的阈值
            llm_client: LLM客户端(用于智能压缩)
            model: 模型名称
        """
        self.max_working_memory_tokens = max_working_memory_tokens
        self.max_total_tokens = max_total_tokens
        self.compression_threshold = compression_threshold

        # 三层记忆
        self.system_messages: List[Dict[str, Any]] = []  # 系统消息(最高优先级)
        self.working_memory: deque = deque(maxlen=100)  # 短期记忆(最近对话)
        self.long_term_memory: List[CompressedMemory] = []  # 长期记忆(压缩摘要)

        # 工具
        self.token_counter = TokenCounter(model)
        self.compressor = MemoryCompressor(llm_client)

        # 统计信息
        self.stats = {
            "total_messages": 0,
            "compressions": 0,
            "total_tokens_saved": 0
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

        # 检查是否需要压缩
        self._check_and_compress()

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

        # 2. 添加长期记忆摘要
        for compressed in self.long_term_memory:
            summary_msg = {
                "role": "system",
                "content": f"[历史摘要] {compressed.summary}"
            }
            summary_tokens = self.token_counter.count_messages_tokens([summary_msg])

            if current_tokens + summary_tokens < max_tokens * 0.3:  # 长期记忆最多占30%
                messages.append(summary_msg)
                current_tokens += summary_tokens
            else:
                break

        # 3. 添加短期记忆(从最新往前添加，确保工具调用完整性)
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

        # 过滤：只保留完整的消息
        # - tool消息：必须有对应的assistant tool_calls
        # - assistant tool_calls消息：可以没有对应的tool消息（可能还在执行中）
        working_messages = []
        for memory_item, msg_dict, _ in temp_messages:
            # tool消息：必须有对应的tool_calls
            if memory_item.role == "tool":
                tc_id = memory_item.metadata.get("tool_call_id")
                if tc_id and tc_id in tool_call_ids_in_assistant:
                    working_messages.append(msg_dict)
                # 否则跳过这条孤立的tool消息

            # assistant消息包含tool_calls：检查是否有孤立的tool_call
            elif memory_item.role == "assistant" and "tool_calls" in memory_item.metadata:
                # 创建新的tool_calls列表，只包含有对应tool消息的调用
                valid_tool_calls = []
                for tc in memory_item.metadata.get("tool_calls", []):
                    tc_id = tc.get("id")
                    # 如果这个tool_call_id有对应的tool消息，或者后续可能有，都保留
                    # 简化处理：全部保留，因为可能工具还在执行中
                    valid_tool_calls.append(tc)

                if valid_tool_calls:
                    # 更新msg_dict的tool_calls
                    msg_dict_copy = msg_dict.copy()
                    msg_dict_copy["tool_calls"] = valid_tool_calls
                    working_messages.append(msg_dict_copy)
                elif msg_dict.get("content"):
                    # 如果没有有效的tool_calls但有content，作为普通消息保留
                    msg_dict_copy = msg_dict.copy()
                    msg_dict_copy.pop("tool_calls", None)
                    working_messages.append(msg_dict_copy)

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

    def _check_and_compress(self):
        """
        检查是否需要压缩短期记忆

        当短期记忆超过阈值时,将较旧的消息压缩到长期记忆
        """
        # 计算短期记忆的总tokens
        working_tokens = sum(item.tokens for item in self.working_memory)

        # 如果超过压缩阈值,执行压缩
        if working_tokens > self.compression_threshold:
            # 确定要压缩的消息数量(保留最近的一半)
            compress_count = len(self.working_memory) // 2

            if compress_count < 2:  # 至少压缩2条消息
                return

            # 提取要压缩的消息，确保工具调用的完整性
            messages_to_compress = []
            pending_tool_calls = {}  # 记录待匹配的tool_calls {tool_call_id: True}

            for _ in range(compress_count):
                if not self.working_memory:
                    break

                item = self.working_memory.popleft()
                msg_dict = self._memory_item_to_message_dict(item)
                messages_to_compress.append(msg_dict)

                # 如果是assistant消息且包含tool_calls，记录所有tool_call_id
                if item.role == "assistant" and "tool_calls" in item.metadata:
                    for tool_call in item.metadata["tool_calls"]:
                        tool_call_id = tool_call.get("id")
                        if tool_call_id:
                            pending_tool_calls[tool_call_id] = True

                # 如果是tool消息，从待匹配列表中移除
                if item.role == "tool" and "tool_call_id" in item.metadata:
                    tool_call_id = item.metadata["tool_call_id"]
                    pending_tool_calls.pop(tool_call_id, None)

            # 如果还有未匹配的tool_calls，继续提取tool消息直到匹配完成
            while pending_tool_calls and self.working_memory:
                item = self.working_memory[0]  # 先查看但不移除

                # 只处理tool消息
                if item.role == "tool":
                    tool_call_id = item.metadata.get("tool_call_id")
                    if tool_call_id in pending_tool_calls:
                        # 找到匹配的tool消息，移除并添加到压缩列表
                        item = self.working_memory.popleft()
                        msg_dict = self._memory_item_to_message_dict(item)
                        messages_to_compress.append(msg_dict)
                        pending_tool_calls.pop(tool_call_id, None)
                        continue

                # 如果不是匹配的tool消息，停止查找
                break

            # 执行压缩
            compressed = self.compressor.compress_messages(messages_to_compress)

            # 添加到长期记忆
            self.long_term_memory.append(compressed)

            # 更新统计
            self.stats["compressions"] += 1
            tokens_saved = compressed.original_tokens - compressed.compressed_tokens
            self.stats["total_tokens_saved"] += tokens_saved

            print(f"✓ 记忆压缩完成: {compressed.original_messages}条消息 -> "
                  f"{compressed.compressed_tokens} tokens "
                  f"(节省 {tokens_saved} tokens)")

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
                msg[key] = item.metadata[key]

        return msg

    def clear(self):
        """清空所有记忆(保留系统消息)"""
        self.working_memory.clear()
        self.long_term_memory.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        获取记忆统计信息

        返回:
            统计信息字典
        """
        working_tokens = sum(item.tokens for item in self.working_memory)
        long_term_tokens = sum(cm.compressed_tokens for cm in self.long_term_memory)

        return {
            **self.stats,
            "working_memory_messages": len(self.working_memory),
            "working_memory_tokens": working_tokens,
            "long_term_memory_summaries": len(self.long_term_memory),
            "long_term_memory_tokens": long_term_tokens,
            "total_context_tokens": working_tokens + long_term_tokens
        }

    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        print("\n" + "="*50)
        print("📊 记忆管理统计")
        print("="*50)
        print(f"总消息数: {stats['total_messages']}")
        print(f"短期记忆: {stats['working_memory_messages']}条 ({stats['working_memory_tokens']} tokens)")
        print(f"长期记忆: {stats['long_term_memory_summaries']}个摘要 ({stats['long_term_memory_tokens']} tokens)")
        print(f"压缩次数: {stats['compressions']}")
        print(f"节省tokens: {stats['total_tokens_saved']}")
        print(f"当前上下文: {stats['total_context_tokens']} / {self.max_total_tokens} tokens")
        print("="*50 + "\n")
