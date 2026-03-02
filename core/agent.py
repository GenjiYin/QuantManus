"""
AI Agent核心类
这是整个系统的核心,负责协调LLM、工具和任务执行

支持三种记忆模式:
1. use_persistence=True (推荐) - 持久化模式，会话保存到磁盘，支持长期记忆
2. use_memory_manager=True - 内存记忆管理模式（旧版，不持久化）
3. 两者都为 False - 简单消息历史模式
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
from .message import Message, MessageHistory
from .llm_client import LLMClient
from .logger import get_logger
from .memory_manager import MemoryManager
from .planner import Planner
from .plan_executor import PlanExecutor


class SimpleAgent:
    """
    简单的AI Agent

    这个Agent能够:
    1. 接收用户任务
    2. 调用LLM进行思考和决策
    3. 使用工具执行具体操作
    4. 返回执行结果

    属性:
        name: Agent名称
        llm_client: LLM客户端
        tools: 可用工具列表
        max_steps: 最大执行步数
    """

    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        tools: List[Any],
        system_prompt: Optional[str] = None,
        max_steps: int = 20,
        use_memory_manager: bool = False,
        max_context_tokens: int = 6000,
        enable_planning: bool = False,
        # 持久化模式参数
        use_persistence: bool = True,
        workspace: Optional[Path] = None,
        session_key: str = "cli:direct",
        consolidation_threshold: int = 50,
    ):
        """
        初始化Agent

        参数:
            name: Agent名称
            llm_client: LLM客户端实例
            tools: 工具列表
            system_prompt: 系统提示词
            max_steps: 最大执行步数
            use_memory_manager: 是否使用内存记忆管理(旧版)
            max_context_tokens: 最大上下文token数
            enable_planning: 是否启用任务规划模式
            use_persistence: 是否启用持久化模式(推荐)
            workspace: 工作空间目录路径
            session_key: 会话标识
            consolidation_threshold: 触发记忆整合的消息数阈值
        """
        self.name = name
        self.llm_client = llm_client
        self.tools = tools
        self.max_steps = max_steps
        self.enable_planning = enable_planning
        self.use_persistence = use_persistence
        self.use_memory_manager = use_memory_manager if not use_persistence else False
        self.base_system_prompt = system_prompt or ""

        # 创建日志记录器
        self.logger = get_logger(f"Agent.{name}")

        # 初始化规划器和执行器
        if enable_planning:
            self.planner = Planner(llm_client, tools, self.logger)
            self.plan_executor = PlanExecutor(self, self.logger)
        else:
            self.planner = None
            self.plan_executor = None

        # 根据配置选择记忆管理方式
        if use_persistence:
            # 持久化模式: 使用 SessionManager + MemoryStore + ContextBuilder
            from .session import SessionManager
            from .memory_store import MemoryStore
            from .context_builder import ContextBuilder

            if workspace is None:
                from config.config import global_config
                workspace = global_config.get_workspace_dir()

            self.workspace = Path(workspace)
            self.session_manager = SessionManager(self.workspace)
            self.memory_store = MemoryStore(self.workspace)
            self.context_builder = ContextBuilder(self.workspace, self.memory_store)
            self.session = self.session_manager.get_or_create(session_key)
            self.consolidation_threshold = consolidation_threshold

            # 持久化模式下不使用旧的记忆管理
            self.memory_manager = None
            self.message_history = None

        elif self.use_memory_manager:
            # 内存记忆管理模式（旧版）
            self.memory_manager = MemoryManager(
                max_working_memory_tokens=max_context_tokens // 3,
                max_total_tokens=max_context_tokens,
                compression_threshold=max_context_tokens // 2,
                llm_client=llm_client,
                model=llm_client.model
            )
            self.message_history = None
            self.session = None

            if system_prompt:
                self.memory_manager.add_system_message(system_prompt)
        else:
            # 简单消息历史模式
            self.message_history = MessageHistory()
            self.memory_manager = None
            self.session = None

            if system_prompt:
                self.message_history.add_message(
                    Message.system_message(system_prompt)
                )

        # 创建工具名称到工具对象的映射
        self.tool_map = {tool.name: tool for tool in tools}

    def run(self, task: str) -> str:
        """
        运行Agent执行任务

        参数:
            task: 用户任务描述

        返回:
            任务执行结果
        """
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"Agent '{self.name}' 开始执行任务")
        self.logger.info(f"任务: {task}")
        self.logger.info(f"{'='*50}\n")

        # 如果启用了规划模式，先制定计划
        if self.enable_planning:
            return self._run_with_planning(task)
        else:
            return self._run_without_planning(task)

    def _run_with_planning(self, task: str) -> str:
        """
        使用规划模式执行任务

        参数:
            task: 用户任务描述

        返回:
            任务执行结果
        """
        try:
            # 1. 制定计划
            self.logger.info("\n正在分析任务并制定执行计划...")
            plan = self.planner.create_plan(task)

            # 2. 显示计划并询问用户确认
            print("\n" + str(plan))
            confirm = input("\n是否执行此计划？(y/n，直接回车表示确认): ").strip().lower()

            if confirm and confirm != 'y':
                self.logger.info("用户取消执行")
                return "任务已取消"

            # 3. 执行计划
            result = self.plan_executor.execute_plan(plan)

            if result["success"]:
                return result["final_result"]
            else:
                return f"计划执行失败: {result.get('error', '未知错误')}"

        except Exception as e:
            self.logger.error(f"规划模式执行失败: {str(e)}")
            self.logger.info("回退到普通执行模式")
            return self._run_without_planning(task)

    def _run_without_planning(self, task: str) -> str:
        """
        不使用规划模式执行任务

        参数:
            task: 用户任务描述

        返回:
            任务执行结果
        """
        # 添加用户消息
        if self.use_persistence:
            self.session.add_message("user", task)
        elif self.use_memory_manager:
            self.memory_manager.add_message("user", task, importance=0.9)
        else:
            self.message_history.add_message(Message.user_message(task))

        # 执行循环
        for step in range(1, self.max_steps + 1):
            self.logger.info(f"\n--- 步骤 {step}/{self.max_steps} ---")

            # 调用LLM进行思考
            continue_execution = self._think_and_act()

            # 如果Agent决定结束,跳出循环
            if not continue_execution:
                self.logger.info("\nAgent决定任务已完成")
                break

            # 如果达到最大步数
            if step == self.max_steps:
                self.logger.warning(f"\n达到最大步数限制({self.max_steps}),任务结束")

        # 获取最终结果
        final_result = self._get_final_result()

        # 持久化模式: 检查是否需要整合记忆，然后保存会话
        if self.use_persistence:
            self._maybe_consolidate()
            self.session_manager.save(self.session)

        self.logger.info(f"\n{'='*50}")
        self.logger.info("任务执行完成")
        self.logger.info(f"{'='*50}\n")

        return final_result

    def execute_subtask(self, task: str, max_steps: int = 5) -> str:
        """
        执行子任务（用于计划执行器调用）

        参数:
            task: 子任务描述
            max_steps: 最大执行步数

        返回:
            子任务执行结果
        """
        original_max_steps = self.max_steps
        self.max_steps = max_steps

        try:
            result = self._run_without_planning(task)
            return result
        finally:
            self.max_steps = original_max_steps

    def _think_and_act(self) -> bool:
        """
        思考并执行行动

        返回:
            是否继续执行(True表示继续,False表示结束)
        """
        try:
            # 获取消息列表
            if self.use_persistence:
                # 从 session key 解析渠道信息，如 "cli:direct" → channel="cli", chat_id="direct"
                channel, _, chat_id = self.session.key.partition(":")
                messages = self.context_builder.build_messages(
                    session=self.session,
                    base_system_prompt=self.base_system_prompt,
                    channel=channel or None,
                    chat_id=chat_id or None,
                )
            elif self.use_memory_manager:
                messages = self.memory_manager.get_context_messages()
            else:
                messages = self.message_history.get_messages_as_dicts()

            # 获取工具定义
            tools = [tool.get_schema() for tool in self.tools]

            # 调用LLM
            self.logger.debug("正在调用LLM思考...")
            response = self.llm_client.chat(
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )

            # 如果LLM要调用工具
            if "tool_calls" in response:
                # 显示LLM的回复内容(如果有)
                if response.get("content"):
                    self.logger.info(f"LLM回复: {response['content']}")

                # 添加包含工具调用的助手消息
                if self.use_persistence:
                    self.session.add_message(
                        "assistant",
                        response.get("content"),
                        tool_calls=response["tool_calls"]
                    )
                elif self.use_memory_manager:
                    self.memory_manager.add_message(
                        "assistant",
                        response.get("content"),
                        importance=0.7,
                        tool_calls=response["tool_calls"]
                    )
                else:
                    self.message_history.add_message(
                        Message(
                            role="assistant",
                            content=response.get("content"),
                            tool_calls=response["tool_calls"]
                        )
                    )

                # 执行工具调用
                self._execute_tool_calls(response["tool_calls"])

                return True

            # 如果LLM只返回了文本内容(没有工具调用)
            if response.get("content"):
                self.logger.info(f"LLM回复: {response['content']}")

                # 添加助手消息
                if self.use_persistence:
                    self.session.add_message("assistant", response["content"])
                elif self.use_memory_manager:
                    self.memory_manager.add_message(
                        "assistant",
                        response["content"],
                        importance=0.8
                    )
                else:
                    self.message_history.add_message(
                        Message.assistant_message(response["content"])
                    )

                # 没有工具调用,说明任务完成
                return False

            return False

        except Exception as e:
            self.logger.error(f"执行出错: {str(e)}")
            return False

    def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """
        执行工具调用

        参数:
            tool_calls: 工具调用列表
        """
        import json

        for tool_call in tool_calls:
            tool_id = tool_call.get("id", "")
            tool_name = tool_call["function"]["name"]
            tool_args_str = tool_call["function"]["arguments"]

            # 验证tool_id不为空
            if not tool_id or tool_id.strip() == "":
                self.logger.error(f"工具调用缺少有效的ID: {tool_call}")
                continue

            self.logger.info(f"\n调用工具: {tool_name}")
            self.logger.debug(f"参数: {tool_args_str}")

            try:
                # 解析参数
                tool_args = json.loads(tool_args_str)

                # 获取工具实例
                if tool_name not in self.tool_map:
                    error_msg = f"工具 '{tool_name}' 不存在"
                    self.logger.error(f"错误: {error_msg}")
                    self._add_tool_message(tool_id, tool_name, error_msg)
                    continue

                tool = self.tool_map[tool_name]

                # 执行工具
                result = tool.execute(**tool_args)

                # 记录结果
                if hasattr(result, 'success') and result.success:
                    self.logger.info(f"工具执行成功: {result.output if hasattr(result, 'output') else result}")
                else:
                    self.logger.warning(f"工具执行结果: {result}")

                result_str = str(result)
                self._add_tool_message(tool_id, tool_name, result_str)

            except Exception as e:
                error_msg = f"工具执行失败: {str(e)}"
                self.logger.error(f"错误: {error_msg}")
                self._add_tool_message(tool_id, tool_name, error_msg)

    def _add_tool_message(self, tool_id: str, tool_name: str, content: str):
        """
        添加工具返回消息到当前活跃的记忆系统

        参数:
            tool_id: 工具调用ID
            tool_name: 工具名称
            content: 工具返回内容
        """
        if self.use_persistence:
            self.session.add_message(
                "tool", content,
                tool_call_id=tool_id,
                name=tool_name
            )
        elif self.use_memory_manager:
            # 评估工具结果的重要性
            tool_importance = 0.6
            if "error" in content.lower() or "错误" in content.lower():
                tool_importance = 0.8
            elif len(content) > 1000:
                tool_importance = 0.7
            self.memory_manager.add_message(
                "tool", content,
                importance=tool_importance,
                tool_call_id=tool_id,
                name=tool_name
            )
        else:
            self.message_history.add_message(
                Message.tool_message(tool_id, tool_name, content)
            )

    def _get_final_result(self) -> str:
        """
        获取最终结果

        返回:
            任务执行结果摘要
        """
        if self.use_persistence:
            # 从 session 中找最后一条 assistant 消息
            for msg in reversed(self.session.messages[-10:]):
                if msg.get("role") == "assistant" and msg.get("content"):
                    return msg["content"]
            return "任务已完成"

        elif self.use_memory_manager:
            recent_messages = list(self.memory_manager.working_memory)[-5:]
            for item in reversed(recent_messages):
                if item.role == "assistant" and item.content:
                    return item.content
            return "任务已完成"

        else:
            recent_messages = self.message_history.get_last_n_messages(5)
            for msg in reversed(recent_messages):
                if msg.role == "assistant" and msg.content:
                    return msg.content
            return "任务已完成"

    def _maybe_consolidate(self):
        """
        检查是否需要整合记忆

        当未整合的消息数超过阈值时，触发 LLM 驱动的记忆整合
        """
        if not self.use_persistence:
            return

        unconsolidated = self.session.get_unconsolidated_count()
        if unconsolidated >= self.consolidation_threshold:
            self.logger.info(
                f"未整合消息数 ({unconsolidated}) >= 阈值 ({self.consolidation_threshold})，"
                "触发记忆整合..."
            )
            success = self.memory_store.consolidate(
                session=self.session,
                llm_client=self.llm_client,
                memory_window=self.consolidation_threshold,
            )
            if success:
                self.session_manager.save(self.session)
                self.logger.info("记忆整合完成")
            else:
                self.logger.warning("记忆整合失败")

    def clear_session(self, archive: bool = True):
        """
        清空当前会话

        参数:
            archive: 是否在清空前归档会话内容到长期记忆
        """
        if not self.use_persistence:
            if self.use_memory_manager:
                self.memory_manager.clear()
            elif self.message_history:
                self.message_history.clear()
            return

        # 持久化模式: 先归档再清空
        if archive and self.session.messages:
            self.logger.info("正在归档当前会话到长期记忆...")
            self.memory_store.consolidate(
                self.session, self.llm_client, archive_all=True
            )

        self.session.clear()
        self.session_manager.save(self.session)
        self.logger.info("会话已清空")

    def save_session(self):
        """手动保存当前会话到磁盘"""
        if self.use_persistence:
            self.session_manager.save(self.session)

    def print_memory_stats(self):
        """打印记忆管理统计信息"""
        if self.use_persistence:
            memory_content = self.memory_store.read_long_term()
            msg_count = len(self.session.messages)
            unconsolidated = self.session.get_unconsolidated_count()
            print("\n" + "=" * 50)
            print("记忆系统统计")
            print("=" * 50)
            print(f"会话消息总数: {msg_count}")
            print(f"未整合消息数: {unconsolidated}")
            print(f"整合阈值: {self.consolidation_threshold}")
            print(f"长期记忆: {'有内容' if memory_content else '空'}")
            if memory_content:
                print(f"长期记忆大小: {len(memory_content)} 字符")
            print("=" * 50 + "\n")
        elif self.use_memory_manager:
            self.memory_manager.print_stats()
        else:
            self.logger.info("未启用智能记忆管理")
