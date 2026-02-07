"""
AI Agent核心类
这是整个系统的核心,负责协调LLM、工具和任务执行
"""
from typing import List, Dict, Any, Optional
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
        message_history: 消息历史
        max_steps: 最大执行步数
    """

    def __init__(
        self,
        name: str,
        llm_client: LLMClient,
        tools: List[Any],
        system_prompt: Optional[str] = None,
        max_steps: int = 20,
        use_memory_manager: bool = True,
        max_context_tokens: int = 6000,
        enable_planning: bool = False
    ):
        """
        初始化Agent

        参数:
            name: Agent名称
            llm_client: LLM客户端实例
            tools: 工具列表
            system_prompt: 系统提示词
            max_steps: 最大执行步数
            use_memory_manager: 是否使用智能记忆管理(推荐开启)
            max_context_tokens: 最大上下文token数
            enable_planning: 是否启用任务规划模式
        """
        self.name = name
        self.llm_client = llm_client
        self.tools = tools
        self.max_steps = max_steps
        self.use_memory_manager = use_memory_manager
        self.enable_planning = enable_planning

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
        if use_memory_manager:
            # 使用智能记忆管理器
            self.memory_manager = MemoryManager(
                max_working_memory_tokens=max_context_tokens // 3,
                max_total_tokens=max_context_tokens,
                compression_threshold=max_context_tokens // 2,
                llm_client=llm_client,
                model=llm_client.model
            )
            self.message_history = None  # 不使用旧的历史管理

            # 添加系统提示词到记忆管理器
            if system_prompt:
                self.memory_manager.add_system_message(system_prompt)
        else:
            # 使用传统的消息历史
            self.message_history = MessageHistory()
            self.memory_manager = None

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
            self.logger.info("\n🤔 正在分析任务并制定执行计划...")
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
        不使用规划模式执行任务（原始执行逻辑）

        参数:
            task: 用户任务描述

        返回:
            任务执行结果
        """
        # 添加用户消息
        if self.use_memory_manager:
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
            # 获取消息历史
            if self.use_memory_manager:
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

                # 添加包含工具调用的助手消息(可能包含content)
                if self.use_memory_manager:
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

                # 添加助手消息到历史
                if self.use_memory_manager:
                    self.memory_manager.add_message(
                        "assistant",
                        response["content"],
                        importance=0.8  # 最终回复通常很重要
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
                    self.message_history.add_message(
                        Message.tool_message(tool_id, tool_name, error_msg)
                    )
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

                # 评估工具结果的重要性
                tool_importance = 0.6
                if "error" in result_str.lower() or "错误" in result_str.lower():
                    tool_importance = 0.8
                elif len(result_str) > 1000:  # 大量数据
                    tool_importance = 0.7

                # 添加工具返回消息
                if self.use_memory_manager:
                    self.memory_manager.add_message(
                        "tool",
                        result_str,
                        importance=tool_importance,
                        tool_call_id=tool_id,
                        name=tool_name
                    )
                else:
                    self.message_history.add_message(
                        Message.tool_message(
                            tool_id,
                            tool_name,
                            result_str
                        )
                    )

            except Exception as e:
                error_msg = f"工具执行失败: {str(e)}"
                self.logger.error(f"错误: {error_msg}")

                if self.use_memory_manager:
                    self.memory_manager.add_message(
                        "tool",
                        error_msg,
                        importance=0.9,  # 错误信息很重要
                        tool_call_id=tool_id,
                        name=tool_name
                    )
                else:
                    self.message_history.add_message(
                        Message.tool_message(tool_id, tool_name, error_msg)
                    )

    def _get_final_result(self) -> str:
        """
        获取最终结果

        返回:
            任务执行结果摘要
        """
        if self.use_memory_manager:
            # 从记忆管理器获取最近消息
            recent_messages = list(self.memory_manager.working_memory)[-5:]

            # 找到最后一条助手消息
            for item in reversed(recent_messages):
                if item.role == "assistant" and item.content:
                    return item.content

            return "任务已完成"
        else:
            # 获取最后几条消息
            recent_messages = self.message_history.get_last_n_messages(5)

            # 找到最后一条助手消息
            for msg in reversed(recent_messages):
                if msg.role == "assistant" and msg.content:
                    return msg.content

            return "任务已完成"

    def print_memory_stats(self):
        """打印记忆管理统计信息"""
        if self.use_memory_manager:
            self.memory_manager.print_stats()
        else:
            self.logger.info("未启用智能记忆管理")
