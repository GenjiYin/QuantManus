"""
持久化记忆系统
实现两层持久化记忆:
- MEMORY.md — 长期事实记忆（关键信息摘要，覆盖式更新）
- HISTORY.md — 时间线日志（grep 可搜索，追加式）

记忆整合通过 LLM 完成，利用 save_memory 虚拟工具调用获取结构化输出
"""
import json
from pathlib import Path
from typing import Optional
from .logger import get_logger


# save_memory 虚拟工具定义
# 整合时提供给 LLM，让 LLM 通过 tool_call 返回结构化的整合结果
SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": (
                "Save the memory consolidation result to persistent storage."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": (
                            "A paragraph (2-5 sentences) summarizing key events, "
                            "decisions, and topics from the conversation. "
                            "Start with [YYYY-MM-DD HH:MM]. "
                            "Include detail useful for grep search."
                        ),
                    },
                    "memory_update": {
                        "type": "string",
                        "description": (
                            "Full updated long-term memory as markdown. "
                            "Include ALL existing facts plus any new ones. "
                            "Return the existing memory unchanged if nothing new to add."
                        ),
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]


class MemoryStore:
    """
    持久化记忆存储

    管理 workspace/memory/ 目录下的两个文件:
    - MEMORY.md: 长期事实记忆，由 LLM 整合时覆盖更新
    - HISTORY.md: 时间线日志，追加式写入，每条记录以 [YYYY-MM-DD HH:MM] 开头
    """

    def __init__(self, workspace: Path):
        """
        初始化记忆存储

        参数:
            workspace: 工作空间目录路径
        """
        self.memory_dir = workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"
        self.logger = get_logger("MemoryStore")

    # ====== 基本读写操作 ======

    def read_long_term(self) -> str:
        """
        读取 MEMORY.md 长期记忆

        返回:
            文件内容，不存在则返回空字符串
        """
        if self.memory_file.exists():
            try:
                return self.memory_file.read_text(encoding="utf-8")
            except Exception as e:
                self.logger.error(f"读取 MEMORY.md 失败: {e}")
        return ""

    def write_long_term(self, content: str) -> None:
        """
        覆盖写入 MEMORY.md

        参数:
            content: 新的长期记忆内容
        """
        try:
            self.memory_file.write_text(content, encoding="utf-8")
        except Exception as e:
            self.logger.error(f"写入 MEMORY.md 失败: {e}")

    def append_history(self, entry: str) -> None:
        """
        追加一条记录到 HISTORY.md

        参数:
            entry: 历史记录条目（应以 [YYYY-MM-DD HH:MM] 开头）
        """
        try:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(entry.rstrip() + "\n\n")
        except Exception as e:
            self.logger.error(f"追加 HISTORY.md 失败: {e}")

    def get_memory_context(self) -> str:
        """
        获取用于注入 System Prompt 的记忆上下文

        返回:
            格式化的记忆内容，为空则返回空字符串
        """
        long_term = self.read_long_term()
        if long_term:
            return f"## Long-term Memory\n{long_term}"
        return ""

    # ====== 记忆整合 ======

    def consolidate(
        self,
        session,
        llm_client,
        memory_window: int = 50,
        archive_all: bool = False,
    ) -> bool:
        """
        将旧消息整合到 MEMORY.md 和 HISTORY.md

        通过一次 LLM 调用 + save_memory 虚拟工具获取结构化的整合结果

        整合策略:
        - 普通自动整合: 保留最近一半窗口的消息，整合较旧的部分
        - archive_all=True: 归档所有消息（用于 /new 命令清空会话时）

        参数:
            session:       要整合的 Session 对象
            llm_client:    LLMClient 实例
            memory_window: 触发整合的消息窗口大小
            archive_all:   是否归档所有消息

        返回:
            整合是否成功
        """
        # 1. 确定要整合的消息范围
        if archive_all:
            old_messages = session.messages
            keep_count = 0
        else:
            keep_count = memory_window // 2
            if len(session.messages) <= keep_count:
                return True  # 消息太少，不需要整合
            old_messages = session.messages[
                session.last_consolidated: len(session.messages) - keep_count
            ]
            if not old_messages:
                return True

        # 2. 格式化对话为文本
        lines = []
        for m in old_messages:
            content = m.get("content")
            if not content:
                continue
            role = m.get("role", "unknown").upper()
            ts = m.get("timestamp", "?")[:16]
            # 标注工具调用
            tools_info = ""
            if m.get("tool_calls"):
                tool_names = [
                    tc["function"]["name"]
                    for tc in m["tool_calls"]
                    if "function" in tc
                ]
                if tool_names:
                    tools_info = f" [tools: {', '.join(tool_names)}]"
            lines.append(f"[{ts}] {role}{tools_info}: {content}")

        if not lines:
            return True

        # 3. 读取当前长期记忆
        current_memory = self.read_long_term()

        # 4. 构建整合 prompt
        prompt = (
            "Process this conversation and call the save_memory tool "
            "with your consolidation.\n\n"
            f"## Current Long-term Memory\n{current_memory or '(empty)'}\n\n"
            f"## Conversation to Process\n" + "\n".join(lines)
        )

        # 5. 调用 LLM（使用 save_memory 工具）
        try:
            response = llm_client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a memory consolidation agent. "
                            "Call the save_memory tool with your consolidation "
                            "of the conversation. Preserve all existing memory "
                            "facts and add new ones. "
                            "Write history_entry and memory_update in the same "
                            "language as the conversation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=SAVE_MEMORY_TOOL,
                tool_choice="auto",
            )
        except Exception as e:
            self.logger.error(f"整合 LLM 调用失败: {e}")
            return False

        # 6. 解析工具调用结果
        if "tool_calls" not in response:
            self.logger.warning("LLM 未调用 save_memory 工具")
            return False

        tool_call = response["tool_calls"][0]
        args_str = tool_call["function"]["arguments"]
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError as e:
            self.logger.error(f"解析 save_memory 参数失败: {e}")
            return False

        # 7. 写入文件
        history_entry = args.get("history_entry")
        memory_update = args.get("memory_update")

        if history_entry:
            self.append_history(history_entry)
            self.logger.info(f"已追加历史记录: {history_entry[:80]}...")

        if memory_update and memory_update != current_memory:
            self.write_long_term(memory_update)
            self.logger.info("已更新 MEMORY.md")

        # 8. 更新整合指针
        if archive_all:
            session.last_consolidated = 0
        else:
            session.last_consolidated = len(session.messages) - keep_count

        self.logger.info(
            f"记忆整合完成，指针移动到 {session.last_consolidated}"
        )
        return True
