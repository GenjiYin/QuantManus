"""
AI Agent 核心模块

简化版：仅使用持久化模式（SessionManager + MemoryStore + ContextBuilder）。
已移除 MemoryManager 和 MessageHistory 的分支逻辑。
"""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from .llm_client import LLMClient
from .logger import get_logger
from .planner import Planner
from .plan_executor import PlanExecutor


class SimpleAgent:
    """
    AI 智能体

    使用持久化会话 + 长期记忆 + 上下文构建器进行对话管理。
    支持规划模式（Planner + PlanExecutor）和直接执行模式。
    """

    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        tools: List[Any],
        system_prompt: Optional[str] = None,
        max_steps: int = 20,
        enable_planning: bool = False,
        workspace: Optional[Path] = None,
        session_key: str = "cli:direct",
        consolidation_threshold: int = 50,
        **kwargs,  # 兼容旧参数（use_persistence 等），直接忽略
    ):
        """
        初始化 Agent

        参数:
            name:                     Agent 名称
            llm_client:               LLM 客户端实例
            tools:                    工具列表
            system_prompt:            基础系统提示词
            max_steps:                单次执行最大步数
            enable_planning:          是否启用规划模式
            workspace:                工作空间路径（默认 cwd）
            session_key:              会话标识
            consolidation_threshold:  触发记忆整合的消息数阈值
        """
        self.name = name
        self.llm_client = llm_client
        self.tools = tools
        self.max_steps = max_steps
        self.enable_planning = enable_planning
        self.base_system_prompt = system_prompt or ""
        self.logger = get_logger(f"Agent.{name}")

        # 保留兼容属性
        self.use_persistence = True

        # ====== 持久化模式初始化 ======
        from .session import SessionManager
        from .memory_store import MemoryStore
        from .context_builder import ContextBuilder
        from config.config import global_config

        if workspace is None:
            workspace = global_config.get_workspace_dir()
        self.workspace = Path(workspace)

        self.session_manager = SessionManager(self.workspace)
        self.memory_store = MemoryStore(self.workspace)

        from .skills_loader import SkillsLoader
        self.skills_loader = SkillsLoader(global_config.get_skills_dir())

        self.context_builder = ContextBuilder(
            self.workspace, self.memory_store, skills_loader=self.skills_loader
        )
        self.session = self.session_manager.get_or_create(session_key)
        self.consolidation_threshold = consolidation_threshold

        # ====== 工具映射 ======
        self.tool_map = {tool.name: tool for tool in tools}

        # ====== 规划器 ======
        if self.enable_planning:
            self.planner = Planner(
                llm_client, tools, self.logger,
                skills_loader=self.skills_loader,
            )
            self.plan_executor = PlanExecutor(self, self.logger)
        else:
            self.planner = None
            self.plan_executor = None

    # ====== 公共接口 ======

    def run(self, task: str) -> str:
        """
        执行任务（主入口）

        参数:
            task: 用户输入的任务描述

        返回:
            最终结果文本
        """
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"Agent '{self.name}' 开始执行任务")
        self.logger.info(f"{'='*50}\n")

        if self.enable_planning:
            return self._run_with_planning(task)
        else:
            return self._run_without_planning(task)

    def execute_subtask(
        self,
        task: str,
        max_steps: int = 5,
        allowed_tools: Optional[List[str]] = None,
    ) -> str:
        """
        执行子任务（由 PlanExecutor 调用）

        子任务模式下会额外收集工具原始输出到 _subtask_tool_outputs，
        由 PlanExecutor 读取后存入 step.tool_output，实现独立数据通道。

        参数:
            task:          执行提示
            max_steps:     最大步数
            allowed_tools: 允许使用的工具名称列表（None = 全部）

        返回:
            LLM 的最终汇报文本
        """
        original_max_steps = self.max_steps
        self.max_steps = max_steps
        self._allowed_tools = allowed_tools
        self._is_subtask = True
        self._subtask_tool_outputs = []

        try:
            result = self._run_without_planning(task)
            return result
        finally:
            self.max_steps = original_max_steps
            self._allowed_tools = None
            self._is_subtask = False
            # 注意：_subtask_tool_outputs 不在此清空
            # PlanExecutor._execute_step 会在读取后清空

    def clear_session(self, archive: bool = True):
        """
        清空当前会话

        参数:
            archive: 是否先归档到长期记忆
        """
        if archive and self.session.messages:
            self.logger.info("正在归档当前会话到长期记忆...")
            self.memory_store.consolidate(
                self.session, self.llm_client, archive_all=True
            )
        self.session.clear()
        self.session_manager.save(self.session)
        self.logger.info("会话已清空")

    def save_session(self):
        """保存当前会话"""
        self.session_manager.save(self.session)

    def print_memory_stats(self):
        """打印记忆系统统计"""
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

    # ====== 内部方法 ======

    def _run_with_planning(self, task: str) -> str:
        """规划模式执行"""
        self.session.add_message("user", task)

        try:
            self.logger.info("\n正在分析任务...")

            recent_history = self._get_recent_history_summary()
            plan_or_answer = self.planner.create_plan(task, context=recent_history)

            # 直接回答（planner 判断无需规划）
            if isinstance(plan_or_answer, str):
                final_result = plan_or_answer
            else:
                # 展示计划并请求确认
                plan = plan_or_answer
                print("\n" + str(plan))
                confirm = input("\n是否执行此计划？(y/n，直接回车表示确认): ").strip().lower()

                if confirm and confirm != 'y':
                    self.logger.info("用户取消执行")
                    final_result = "任务已取消"
                else:
                    result = self.plan_executor.execute_plan(plan)
                    final_result = result["final_result"] or f"计划执行失败: {result.get('error', '未知错误')}"

        except Exception as e:
            self.logger.error(f"规划模式执行失败: {str(e)}")
            final_result = f"执行失败: {str(e)}"

        # 持久化
        self.session.add_message("assistant", final_result)
        self._maybe_consolidate()
        self.session_manager.save(self.session)

        return final_result

    def _run_without_planning(self, task: str) -> str:
        """直接执行模式（也被 execute_subtask 调用）"""
        self.session.add_message("user", task)

        for step in range(1, self.max_steps + 1):
            self.logger.info(f"\n--- 步骤 {step}/{self.max_steps} ---")

            continue_execution = self._think_and_act()
            if not continue_execution:
                self.logger.info("\nAgent 决定任务已完成")
                break

            if step == self.max_steps:
                self.logger.warning(f"\n达到最大步数限制({self.max_steps})")

        final_result = self._get_final_result()

        # 非子任务模式才持久化（子任务由 _run_with_planning 统一管理）
        if not getattr(self, '_is_subtask', False):
            self._maybe_consolidate()
            self.session_manager.save(self.session)

        return final_result

    def _think_and_act(self) -> bool:
        """
        单轮思考-行动循环

        返回:
            True = 继续执行, False = 任务完成
        """
        try:
            # 构建消息
            is_subtask = getattr(self, '_is_subtask', False)
            if is_subtask:
                messages = self.context_builder.build_messages(
                    session=self.session,
                    base_system_prompt=self.base_system_prompt,
                )
            else:
                channel, _, chat_id = self.session.key.partition(":")
                messages = self.context_builder.build_messages(
                    session=self.session,
                    base_system_prompt=self.base_system_prompt,
                    channel=channel or None,
                    chat_id=chat_id or None,
                )

            # 工具 schema
            allowed = getattr(self, '_allowed_tools', None)
            if allowed:
                tools = [tool.get_schema() for tool in self.tools if tool.name in allowed]
            else:
                tools = [tool.get_schema() for tool in self.tools]

            # 调用 LLM
            self.logger.debug("正在调用 LLM 思考...")
            response = self.llm_client.chat(
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )

            # 有工具调用：执行工具，继续循环
            if "tool_calls" in response:
                if response.get("content"):
                    self.logger.info(f"LLM 回复: {response['content']}")
                self.session.add_message(
                    "assistant",
                    response.get("content"),
                    tool_calls=response["tool_calls"],
                )
                self._execute_tool_calls(response["tool_calls"])
                return True

            # 纯文本回复：任务完成
            if response.get("content"):
                self.logger.info(f"LLM 回复: {response['content']}")
                self.session.add_message("assistant", response["content"])
                return False

            return False

        except Exception as e:
            self.logger.error(f"执行出错: {str(e)}")
            return False

    def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]]):
        """执行工具调用列表"""
        self._last_tool_had_error = False

        for tool_call in tool_calls:
            tool_id = tool_call.get("id", "")
            tool_name = tool_call["function"]["name"]
            tool_args_str = tool_call["function"]["arguments"]

            if not tool_id or tool_id.strip() == "":
                self.logger.error(f"工具调用缺少有效的 ID: {tool_call}")
                continue

            self.logger.info(f"\n调用工具: {tool_name}")
            self.logger.debug(f"参数: {tool_args_str}")

            try:
                tool_args = json.loads(tool_args_str)

                if tool_name not in self.tool_map:
                    error_msg = f"工具 '{tool_name}' 不存在"
                    self.logger.error(f"错误: {error_msg}")
                    self._add_tool_message(tool_id, tool_name, error_msg)
                    continue

                tool = self.tool_map[tool_name]
                result = tool.execute(**tool_args)

                # 检查是否有错误
                if hasattr(result, 'success') and not result.success:
                    self._last_tool_had_error = True

                if hasattr(result, 'success') and result.success:
                    self.logger.info(f"工具执行成功: {result.output if hasattr(result, 'output') else result}")
                else:
                    self.logger.warning(f"工具执行结果: {result}")

                result_str = str(result)
                self._add_tool_message(tool_id, tool_name, result_str)

                # 子任务模式：收集工具原始输出到独立数据通道
                if getattr(self, '_is_subtask', False) and hasattr(self, '_subtask_tool_outputs'):
                    if hasattr(result, 'success') and result.success and hasattr(result, 'output'):
                        self._subtask_tool_outputs.append(result.output)

            except Exception as e:
                self._last_tool_had_error = True
                error_msg = f"工具执行失败: {str(e)}"
                self.logger.error(f"错误: {error_msg}")
                self._add_tool_message(tool_id, tool_name, error_msg)

    def _add_tool_message(self, tool_id: str, tool_name: str, content: str):
        """添加工具结果消息到会话"""
        self.session.add_message(
            "tool", content,
            tool_call_id=tool_id,
            name=tool_name,
        )

    def _get_final_result(self) -> str:
        """从会话历史中提取最后一条 assistant 回复"""
        for msg in reversed(self.session.messages[-10:]):
            if msg.get("role") == "assistant" and msg.get("content"):
                return msg["content"]
        return "任务已完成"

    def _get_recent_history_summary(self, max_pairs: int = 5) -> str:
        """
        获取近期对话摘要，供 planner 了解上下文

        只提取最近 max_pairs 轮 user/assistant 对话。
        """
        pairs = []
        for msg in self.session.messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                if len(content) > 2000:
                    content = content[:2000] + "..."
                pairs.append(f"{role}: {content}")

        # 去掉最后一条（当前 task，已在 planning_prompt 里了）
        if pairs:
            pairs = pairs[:-1]

        if not pairs:
            return ""

        recent = pairs[-(max_pairs * 2):]
        return "\n".join(recent)

    def _maybe_consolidate(self):
        """检查是否需要触发记忆整合"""
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
