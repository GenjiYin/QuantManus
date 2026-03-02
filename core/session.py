"""
会话持久化模块
使用 JSONL 格式将对话历史持久化到磁盘

核心功能:
1. Session 数据类 - 管理单个会话的消息和元数据
2. SessionManager - 管理会话的加载、保存、缓存
3. JSONL 格式存储 - 第一行元数据，后续每行一条消息
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


def safe_filename(name: str) -> str:
    """
    将 session key 转为安全文件名

    例如: "cli:direct" → "cli_direct"
    """
    return re.sub(r'[^\w\-.]', '_', name)


@dataclass
class Session:
    """
    会话数据类

    属性:
        key:               会话唯一标识，如 "cli:direct"
        messages:          所有消息列表（追加式，只增不删）
        created_at:        创建时间
        updated_at:        最后更新时间
        metadata:          会话元数据
        last_consolidated: 已整合到长期记忆的消息索引
    """
    key: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0

    def add_message(self, role: str, content: Optional[str], **kwargs):
        """
        追加一条消息到会话

        参数:
            role: 消息角色 (user/assistant/tool/system)
            content: 消息内容
            **kwargs: 额外字段，如 tool_calls, tool_call_id, name
        """
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        # 合并工具相关字段
        for k in ("tool_calls", "tool_call_id", "name"):
            if k in kwargs and kwargs[k] is not None:
                msg[k] = kwargs[k]
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(self, max_messages: int = 500) -> List[Dict[str, Any]]:
        """
        返回未整合的消息（用于 LLM 输入）

        处理逻辑:
        1. 只取 last_consolidated 之后的消息
        2. 取最近 max_messages 条
        3. 丢弃开头的非 user 消息（避免孤立的 tool_result）
        4. 只保留标准 LLM API 字段

        参数:
            max_messages: 最大返回消息数

        返回:
            消息字典列表
        """
        unconsolidated = self.messages[self.last_consolidated:]
        sliced = unconsolidated[-max_messages:]

        # 找到第一条 user 消息作为起点
        start = 0
        for i, m in enumerate(sliced):
            if m.get("role") == "user":
                start = i
                break
        sliced = sliced[start:]

        # 只保留标准字段
        out = []
        for m in sliced:
            entry = {"role": m["role"], "content": m.get("content", "")}
            for k in ("tool_calls", "tool_call_id", "name"):
                if k in m:
                    entry[k] = m[k]
            out.append(entry)
        return out

    def get_unconsolidated_count(self) -> int:
        """返回未整合的消息数量"""
        return len(self.messages) - self.last_consolidated

    def clear(self):
        """清空会话消息并重置整合指针"""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()


class SessionManager:
    """
    会话持久化管理器

    使用 JSONL 格式存储会话到磁盘:
    - 文件路径: {workspace}/sessions/{safe_key}.jsonl
    - 第一行: 元数据行 (_type="metadata")
    - 后续行: 每行一条消息 JSON

    内存缓存避免重复磁盘 I/O
    """

    def __init__(self, workspace: Path):
        """
        初始化会话管理器

        参数:
            workspace: 工作空间目录路径
        """
        self.workspace = workspace
        self.sessions_dir = workspace / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Session] = {}

    def get_or_create(self, key: str) -> Session:
        """
        获取或创建会话

        优先从缓存获取，其次从磁盘加载，最后新建

        参数:
            key: 会话标识

        返回:
            Session 对象
        """
        if key in self._cache:
            return self._cache[key]

        session = self._load(key)
        if session is None:
            session = Session(key=key)

        self._cache[key] = session
        return session

    def save(self, session: Session):
        """
        保存会话到 JSONL 文件（全量写入）

        每次保存都完整重写文件，以保证元数据行（last_consolidated 等）的一致性

        参数:
            session: 要保存的会话
        """
        path = self._get_session_path(session.key)
        try:
            with open(path, "w", encoding="utf-8") as f:
                # 写入元数据行
                meta = {
                    "_type": "metadata",
                    "key": session.key,
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                    "metadata": session.metadata,
                    "last_consolidated": session.last_consolidated,
                }
                f.write(json.dumps(meta, ensure_ascii=False) + "\n")

                # 写入消息（经过清洗）
                for msg in session.messages:
                    sanitized = self._sanitize_message(msg)
                    if sanitized is not None:
                        f.write(json.dumps(sanitized, ensure_ascii=False) + "\n")

            self._cache[session.key] = session
        except Exception as e:
            print(f"保存会话失败: {e}")

    def _load(self, key: str) -> Optional[Session]:
        """
        从 JSONL 文件加载会话

        参数:
            key: 会话标识

        返回:
            Session 对象，文件不存在则返回 None
        """
        path = self._get_session_path(key)
        if not path.exists():
            return None

        messages = []
        metadata = {}
        created_at = datetime.now()
        last_consolidated = 0

        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"])
                        last_consolidated = data.get("last_consolidated", 0)
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at,
                metadata=metadata,
                last_consolidated=last_consolidated,
            )
        except Exception as e:
            print(f"加载会话失败: {e}")
            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        列出所有保存的会话（只读取元数据行）

        返回:
            按更新时间降序排列的会话信息列表
        """
        sessions = []
        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                with open(path, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if not first_line:
                        continue
                    data = json.loads(first_line)
                    if data.get("_type") == "metadata":
                        sessions.append({
                            "key": data.get("key"),
                            "created_at": data.get("created_at"),
                            "updated_at": data.get("updated_at"),
                            "path": str(path),
                        })
            except Exception:
                continue
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

    def delete_session(self, key: str):
        """
        删除会话文件和缓存

        参数:
            key: 会话标识
        """
        path = self._get_session_path(key)
        if path.exists():
            path.unlink()
        self._cache.pop(key, None)

    def invalidate(self, key: str):
        """
        清除缓存中的会话（下次访问将从磁盘重新加载）

        参数:
            key: 会话标识
        """
        self._cache.pop(key, None)

    def _get_session_path(self, key: str) -> Path:
        """获取会话文件路径"""
        return self.sessions_dir / f"{safe_filename(key)}.jsonl"

    @staticmethod
    def _sanitize_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        清洗消息后再持久化

        规则:
        - 跳过空的 assistant 消息（无 content 且无 tool_calls）
        - 截断超过 500 字符的 tool 结果
        - 跳过运行时上下文消息
        - 将 base64 图片替换为 [image] 占位符

        参数:
            msg: 原始消息字典

        返回:
            清洗后的消息字典，如果应跳过则返回 None
        """
        role = msg.get("role", "")
        content = msg.get("content")

        # 跳过运行时上下文消息
        if role == "user" and isinstance(content, str):
            if content.startswith("[Runtime Context"):
                return None

        # 跳过空的 assistant 消息
        if role == "assistant":
            if not content and "tool_calls" not in msg:
                return None

        # 构建清洗后的副本
        sanitized = dict(msg)

        # 截断过长的 tool 结果
        if role == "tool" and isinstance(content, str) and len(content) > 500:
            sanitized["content"] = content[:500] + "\n... (truncated)"

        # 将 base64 图片替换为占位符
        if isinstance(content, list):
            new_content = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    new_content.append({"type": "text", "text": "[image]"})
                else:
                    new_content.append(item)
            sanitized["content"] = new_content

        return sanitized
