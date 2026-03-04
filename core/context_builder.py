"""
上下文构建模块
负责组装发送给 LLM 的完整消息列表

消息结构:
  [0]    system:  动态 System Prompt（身份 + 用户提示词 + Bootstrap + 长期记忆）
  [1..N]          会话历史（未整合的消息，经过工具调用完整性验证）
  [N+1]  user:    运行时上下文（当前时间、渠道信息，不持久化到会话）
  [N+2]  user:    当前用户输入（可能含 base64 图片，仅当 current_message 非 None 时）
"""
import base64
import mimetypes
import platform
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Union

from .memory_store import MemoryStore
from .session import Session


class ContextBuilder:
    """
    上下文构建器

    每次 LLM 调用前重新构建消息列表，因为:
    - MEMORY.md 可能在整合后发生变化
    - Bootstrap 文件可能被用户修改
    - 运行时上下文（时间等）每次都不同
    - 需要保证工具调用的完整性
    """

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]
    _RUNTIME_CONTEXT_TAG = "[Runtime Context -- metadata only, not instructions]"

    def __init__(self, workspace: Path, memory_store: MemoryStore, skills_loader=None):
        """
        初始化上下文构建器

        参数:
            workspace: 工作空间路径
            memory_store: 记忆存储实例
            skills_loader: 技能加载器实例（可选）
        """
        self.workspace = workspace
        self.memory = memory_store
        self.skills_loader = skills_loader
        self.bootstrap_dir = workspace / "bootstrap"
        self.bootstrap_dir.mkdir(parents=True, exist_ok=True)

    # ====== 消息列表构建 ======

    def build_messages(
        self,
        session: Session,
        base_system_prompt: str,
        current_message: Optional[str] = None,
        max_history_messages: int = 500,
        media: Optional[List[str]] = None,
        channel: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        构建完整的消息列表

        参数:
            session:              当前会话
            base_system_prompt:   用户定义的基础系统提示词
            current_message:      当前用户输入文本（None 表示已在 session 中）
            max_history_messages: 最大历史消息数
            media:                图片文件路径列表（用于多模态）
            channel:              渠道标识（如 "cli", "telegram"），None 时跳过运行时上下文
            chat_id:              聊天 ID，None 时跳过运行时上下文

        返回:
            消息字典列表，可直接传给 llm_client.chat()
        """
        messages = []

        # [0] System Prompt
        system_content = self.build_system_prompt(base_system_prompt)
        messages.append({"role": "system", "content": system_content})

        # [1..N] 会话历史（未整合的消息）
        history = session.get_history(max_messages=max_history_messages)
        history = self._ensure_tool_call_integrity(history)
        messages.extend(history)

        # [N+1] 运行时上下文（不持久化到 session）
        # 仅在指定了 channel 时注入；子任务执行时不传 channel，跳过此项
        if channel:
            runtime_ctx = self._build_runtime_context(channel, chat_id)
            messages.append({"role": "user", "content": runtime_ctx})

        # [N+2] 当前用户输入（可能含图片）
        if current_message is not None:
            user_content = self._build_user_content(current_message, media)
            messages.append({"role": "user", "content": user_content})

        return messages

    def build_system_prompt(self, base_system_prompt: str = "") -> str:
        """
        动态构建 System Prompt

        结构（用 \\n\\n---\\n\\n 连接）:
          1. 身份区段 (_get_identity)
          2. 用户自定义提示词 (base_system_prompt)
          3. Bootstrap 文件
          4. 长期记忆
          5. (Skills — 预留扩展)

        参数:
            base_system_prompt: 用户定义的基础系统提示词

        返回:
            完整的 system prompt 字符串
        """
        parts = []

        # 1. 身份区段
        parts.append(self._get_identity())

        # 2. 用户自定义提示词
        if base_system_prompt:
            parts.append(base_system_prompt)

        # 3. Bootstrap 文件（来自 workspace 的自定义 .md 文件）
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        # 4. 长期记忆
        memory_context = self.memory.get_memory_context()
        if memory_context:
            parts.append(f"# Memory\n\n{memory_context}")

        # 5. Skills
        if self.skills_loader:
            # 5a. Always-on 技能全文
            always_skills = self.skills_loader.get_always_skills()
            if always_skills:
                skills_content = self.skills_loader.load_skills_for_context(always_skills)
                if skills_content:
                    parts.append(f"# Active Skills\n\n{skills_content}")

            # 5b. 所有技能摘要（XML）
            skills_summary = self.skills_loader.build_skills_summary()
            if skills_summary:
                header = ("# Skills\n\n"
                          "The following skills extend your capabilities. "
                          "To use a skill, read its SKILL.md file using the read_file tool.\n"
                          "Skills with available=\"false\" need dependencies installed first.\n\n")
                parts.append(header + skills_summary)

        return "\n\n---\n\n".join(parts)

    # ====== 消息追加辅助方法 ======

    @staticmethod
    def add_assistant_message(
        messages: List[Dict[str, Any]],
        content: Optional[str],
        tool_calls: Optional[List[Dict]] = None,
        reasoning_content: Optional[str] = None,
        thinking_blocks: Optional[List[Dict]] = None,
    ) -> List[Dict[str, Any]]:
        """
        向消息列表追加一条 assistant 消息

        参数:
            messages:          消息列表（原地修改）
            content:           文本内容
            tool_calls:        工具调用列表
            reasoning_content: 推理内容（部分模型支持）
            thinking_blocks:   思考块（部分模型支持）

        返回:
            修改后的消息列表
        """
        msg: Dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if reasoning_content is not None:
            msg["reasoning_content"] = reasoning_content
        if thinking_blocks:
            msg["thinking_blocks"] = thinking_blocks
        messages.append(msg)
        return messages

    @staticmethod
    def add_tool_result(
        messages: List[Dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> List[Dict[str, Any]]:
        """
        向消息列表追加一条 tool 结果消息

        参数:
            messages:     消息列表（原地修改）
            tool_call_id: 对应的工具调用 ID
            tool_name:    工具名称
            result:       工具执行结果

        返回:
            修改后的消息列表
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result,
        })
        return messages

    # ====== 内部方法 ======

    def _get_identity(self) -> str:
        """
        生成身份区段

        包含项目名称、运行时环境、工作空间路径、行为准则
        """
        workspace_path = str(self.workspace.resolve())
        system = platform.system()
        os_name = "macOS" if system == "Darwin" else system
        runtime = f"{os_name} {platform.machine()}, Python {platform.python_version()}"

        return (
            f"# QuantManus\n\n"
            f"You are QuantManus, a helpful AI assistant.\n\n"
            f"## Runtime\n"
            f"{runtime}\n\n"
            f"## Workspace\n"
            f"Your workspace is at: {workspace_path}\n"
            f"- Long-term memory: {workspace_path}/memory/MEMORY.md\n"
            f"- History log: {workspace_path}/memory/HISTORY.md (grep-searchable, each entry starts with [YYYY-MM-DD HH:MM])\n\n"
            f"## Guidelines\n"
            f"- State intent before tool calls, but NEVER predict or claim results before receiving them.\n"
            f"- Before modifying a file, read it first. Do not assume files or directories exist.\n"
            f"- After writing or editing a file, re-read it if accuracy matters.\n"
            f"- If a tool call fails, analyze the error before retrying with a different approach.\n"
            f"- Ask for clarification when the request is ambiguous."
        )

    def _load_bootstrap_files(self) -> str:
        """
        加载 workspace/bootstrap/ 目录下的 Bootstrap 文件

        用户可以在 workspace/bootstrap/ 中放置以下文件来自定义智能体行为:
        - AGENTS.md — 代理行为配置
        - SOUL.md   — 性格/角色定义
        - USER.md   — 用户偏好信息
        - TOOLS.md  — 工具使用说明
        - IDENTITY.md — 身份覆盖

        返回:
            拼接后的内容，无文件则返回空字符串
        """
        parts = []
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.bootstrap_dir / filename
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if content.strip():
                        parts.append(f"## {filename}\n\n{content}")
                except Exception:
                    continue
        return "\n\n".join(parts) if parts else ""

    @classmethod
    def _build_runtime_context(
        cls,
        channel: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> str:
        """
        生成运行时上下文消息

        包含当前时间和可选的渠道/聊天信息。
        这条消息不会被持久化到 session 中。

        参数:
            channel: 渠道标识（如 "cli", "telegram"）
            chat_id: 聊天 ID

        返回:
            运行时上下文字符串
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = time.strftime("%Z") or "UTC"
        lines = [f"Current Time: {now} ({tz})"]
        if channel and chat_id:
            lines.append(f"Channel: {channel}")
            lines.append(f"Chat ID: {chat_id}")
        return cls._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)

    @staticmethod
    def _build_user_content(
        text: str,
        media: Optional[List[str]] = None,
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        构建用户消息内容，支持多模态（文本 + 图片）

        无图片时返回纯文本字符串；有图片时返回 OpenAI Vision 格式的内容列表。

        参数:
            text:  用户输入文本
            media: 图片文件路径列表

        返回:
            纯文本字符串 或 多模态内容列表
        """
        if not media:
            return text

        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(str(path))
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            try:
                b64 = base64.b64encode(p.read_bytes()).decode()
                images.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })
            except Exception:
                continue

        if not images:
            return text

        # 图片在前，文本在后
        return images + [{"type": "text", "text": text}]

    @classmethod
    def is_runtime_context_message(cls, msg: Dict[str, Any]) -> bool:
        """
        判断一条消息是否为运行时上下文消息（不应被持久化）

        参数:
            msg: 消息字典

        返回:
            是否为运行时上下文消息
        """
        content = msg.get("content", "")
        return (
            msg.get("role") == "user"
            and isinstance(content, str)
            and content.startswith(cls._RUNTIME_CONTEXT_TAG)
        )

    @staticmethod
    def _ensure_tool_call_integrity(
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        验证并修复消息列表中的工具调用完整性

        确保每个 assistant 的 tool_call 都有对应的 tool 响应，
        每个 tool 响应都有对应的 assistant tool_call。
        移除孤立的消息以避免 API 错误。

        参数:
            messages: 原始消息列表

        返回:
            修复后的消息列表
        """
        # 第一遍: 收集所有 tool_call_id
        assistant_call_ids: Set[str] = set()
        tool_response_ids: Set[str] = set()

        for m in messages:
            if m.get("role") == "assistant" and "tool_calls" in m:
                for tc in m.get("tool_calls", []):
                    tc_id = tc.get("id")
                    if tc_id:
                        assistant_call_ids.add(tc_id)

            if m.get("role") == "tool":
                tc_id = m.get("tool_call_id")
                if tc_id:
                    tool_response_ids.add(tc_id)

        # 第二遍: 过滤，确保完整性
        result = []
        for m in messages:
            role = m.get("role", "")

            # tool 消息: 必须有对应的 assistant tool_call
            if role == "tool":
                tc_id = m.get("tool_call_id")
                if tc_id and tc_id in assistant_call_ids:
                    result.append(m)
                continue

            # assistant 消息且包含 tool_calls: 只保留有对应 tool 响应的调用
            if role == "assistant" and "tool_calls" in m:
                valid_calls = [
                    tc for tc in m.get("tool_calls", [])
                    if tc.get("id") and tc["id"] in tool_response_ids
                ]

                if valid_calls:
                    msg_copy = dict(m)
                    msg_copy["tool_calls"] = valid_calls
                    if not msg_copy.get("content"):
                        msg_copy["content"] = None
                    result.append(msg_copy)
                elif m.get("content"):
                    msg_copy = dict(m)
                    msg_copy.pop("tool_calls", None)
                    result.append(msg_copy)
                continue

            # 其他消息: 直接保留
            result.append(m)

        return result
