"""
规划器模块 - 负责任务分析和步骤规划
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json
from datetime import datetime


class StepStatus(Enum):
    """步骤状态枚举"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    SKIPPED = "skipped"      # 已跳过


@dataclass
class Step:
    """单个执行步骤"""
    id: int
    description: str  # 步骤描述
    goal: str  # 预期目标
    tool_name: Optional[str] = None  # 需要使用的工具
    tool_args: Optional[Dict[str, Any]] = None  # 工具参数
    dependencies: List[int] = field(default_factory=list)  # 依赖的步骤ID
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None  # 执行结果
    error: Optional[str] = None  # 错误信息
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "description": self.description,
            "goal": self.goal,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Step':
        """从字典创建步骤"""
        step = cls(
            id=data["id"],
            description=data["description"],
            goal=data["goal"],
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args"),
            dependencies=data.get("dependencies", []),
            status=StepStatus(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error")
        )
        if data.get("start_time"):
            step.start_time = datetime.fromisoformat(data["start_time"])
        if data.get("end_time"):
            step.end_time = datetime.fromisoformat(data["end_time"])
        return step


@dataclass
class Plan:
    """执行计划"""
    task: str  # 原始任务描述
    thinking: str  # 思考过程
    steps: List[Step] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def add_step(self, step: Step):
        """添加步骤"""
        self.steps.append(step)

    def get_next_steps(self) -> List[Step]:
        """获取下一批可执行的步骤（依赖已满足且状态为PENDING）"""
        next_steps = []
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue

            # 检查依赖是否都已完成
            dependencies_met = all(
                self.get_step(dep_id).status == StepStatus.COMPLETED
                for dep_id in step.dependencies
            )

            if dependencies_met:
                next_steps.append(step)

        return next_steps

    def get_step(self, step_id: int) -> Optional[Step]:
        """根据ID获取步骤"""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def is_completed(self) -> bool:
        """检查计划是否已完成"""
        return all(
            step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED]
            for step in self.steps
        )

    def has_failed(self) -> bool:
        """检查是否有失败的步骤"""
        return any(step.status == StepStatus.FAILED for step in self.steps)

    def get_progress(self) -> Dict[str, Any]:
        """获取执行进度"""
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        pending = sum(1 for s in self.steps if s.status == StepStatus.PENDING)
        running = sum(1 for s in self.steps if s.status == StepStatus.RUNNING)

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "running": running,
            "progress": f"{completed}/{total}"
        }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "task": self.task,
            "thinking": self.thinking,
            "steps": [step.to_dict() for step in self.steps],
            "created_at": self.created_at.isoformat(),
            "progress": self.get_progress()
        }

    def __str__(self) -> str:
        """格式化输出"""
        lines = [
            "=" * 60,
            f"任务: {self.task}",
            "=" * 60,
            f"\n思考过程:\n{self.thinking}\n",
            f"执行计划 ({self.get_progress()['progress']}):",
            "-" * 60
        ]

        for step in self.steps:
            status_symbol = {
                StepStatus.PENDING: "⏳",
                StepStatus.RUNNING: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️"
            }[step.status]

            lines.append(f"\n{status_symbol} 步骤 {step.id}: {step.description}")
            lines.append(f"   目标: {step.goal}")

            if step.dependencies:
                lines.append(f"   依赖: {', '.join(f'步骤{d}' for d in step.dependencies)}")

            if step.tool_name:
                lines.append(f"   工具: {step.tool_name}")

            if step.result:
                result_preview = step.result[:100] + "..." if len(step.result) > 100 else step.result
                lines.append(f"   结果: {result_preview}")

            if step.error:
                lines.append(f"   错误: {step.error}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)


class Planner:
    """规划器 - 负责分析任务并生成执行计划"""

    def __init__(self, llm_client, tools: List, logger=None):
        """
        初始化规划器

        Args:
            llm_client: LLM客户端
            tools: 可用工具列表
            logger: 日志记录器
        """
        self.llm_client = llm_client
        self.tools = tools
        self.logger = logger

    def create_plan(self, task: str, context: str = ""):
        """
        为任务创建执行计划，或直接回答简单问题

        Args:
            task: 任务描述
            context: 近期对话历史摘要，让 planner 了解上下文

        Returns:
            Plan 对象（需要工具执行时）或 str（可直接回答时）
        """
        if self.logger:
            self.logger.info(f"开始为任务创建计划: {task}")

        # 准备工具信息
        tools_info = self._get_tools_info()

        # 构造规划提示词
        planning_prompt = self._build_planning_prompt(task, tools_info, context)

        # 调用LLM生成计划
        messages = [
            {"role": "system", "content": "你是一个专业的任务规划助手，擅长将复杂任务分解为清晰的执行步骤。"},
            {"role": "user", "content": planning_prompt}
        ]

        try:
            response = self.llm_client.chat(messages=messages)
            plan_json = self._parse_plan_response(response.get("content", ""))

            # 如果 planner 判断可以直接回答（无需工具）
            direct_answer = plan_json.get("direct_answer")
            if direct_answer and not plan_json.get("steps"):
                if self.logger:
                    self.logger.info("Planner 判断无需工具，直接回答")
                return direct_answer

            # 创建Plan对象
            plan = Plan(
                task=task,
                thinking=plan_json.get("thinking", ""),
            )

            # 添加步骤
            for step_data in plan_json.get("steps", []):
                step = Step(
                    id=step_data["id"],
                    description=step_data["description"],
                    goal=step_data["goal"],
                    tool_name=step_data.get("tool_name"),
                    tool_args=step_data.get("tool_args"),
                    dependencies=step_data.get("dependencies", [])
                )
                plan.add_step(step)

            if self.logger:
                self.logger.info(f"计划创建完成，共 {len(plan.steps)} 个步骤")

            return plan

        except Exception as e:
            if self.logger:
                self.logger.error(f"创建计划时出错: {str(e)}")

            # 返回一个简单的单步骤计划作为后备
            plan = Plan(task=task, thinking=f"规划失败，将直接执行任务。错误: {str(e)}")
            plan.add_step(Step(
                id=1,
                description="直接执行任务",
                goal=task,
            ))
            return plan

    def _get_tools_info(self) -> str:
        """获取工具信息"""
        tools_list = []
        for tool in self.tools:
            schema = tool.get_schema()
            tools_list.append(f"- {schema['function']['name']}: {schema['function']['description']}")
        return "\n".join(tools_list)

    def _build_planning_prompt(self, task: str, tools_info: str, context: str = "") -> str:
        """构建规划提示词"""
        context_section = ""
        if context:
            context_section = f"""
近期对话历史（用于理解上下文，如果用户的问题涉及之前的对话，请参考这些内容来规划）：
{context}

"""

        return f"""{context_section}请为以下任务制定执行计划：

任务描述：
{task}

可用工具：
{tools_info}

重要：首先判断这个任务是否需要使用工具。
- 如果任务可以直接从对话历史中回答（如用户问之前的结果、要求回忆/总结之前的内容、闲聊等），不需要使用任何工具，请返回 direct_answer：

```json
{{
  "thinking": "判断理由",
  "direct_answer": "直接回答内容（完整、详细，不要省略）",
  "steps": []
}}
```

- 如果任务确实需要使用工具（如读写文件、执行代码、列出目录等），则制定执行计划：

```json
{{
  "thinking": "对任务的分析和思考过程",
  "steps": [
    {{
      "id": 1,
      "description": "步骤描述",
      "goal": "该步骤要达成的目标",
      "tool_name": "需要使用的工具名称（可选）",
      "tool_args": {{"arg1": "value1"}},
      "dependencies": []
    }}
  ]
}}
```

只输出JSON，不要其他内容。

规划原则（仅当需要工具时适用）：
1. 将复杂任务分解为简单、可执行的步骤
2. 每个步骤应该有明确的目标和预期结果
3. 合理设置步骤之间的依赖关系
4. 如果某个步骤需要使用特定工具，请指定tool_name
5. 步骤数量适中（通常1-5个步骤）
6. 步骤应该按逻辑顺序排列

严格约束（必须遵守）：
- 每个操作只能出现一次，禁止重复步骤（例如不能有两个"执行代码"步骤）
- 只规划用户明确要求的内容，不要添加用户未要求的额外步骤（如"优化"、"重构"、"改进"、"清理"等）
- 不要添加"验证"或"测试"步骤，除非用户明确要求测试
- 保持计划精简，完成用户的请求即可，不要画蛇添足"""

    def _parse_plan_response(self, response: str) -> Dict[str, Any]:
        """解析LLM返回的计划"""
        try:
            # 尝试提取JSON代码块
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            plan_data = json.loads(json_str)
            return plan_data

        except Exception as e:
            if self.logger:
                self.logger.error(f"解析计划JSON失败: {str(e)}")

            # 返回空计划
            return {
                "thinking": "解析失败，使用默认计划",
                "steps": [
                    {
                        "id": 1,
                        "description": "执行任务",
                        "goal": "完成用户请求",
                        "dependencies": []
                    }
                ]
            }

    def reflect_and_adjust_plan(self, plan: Plan, executed_step: Step) -> List[Step]:
        """
        反思步骤执行结果，并决定是否需要动态调整计划

        Args:
            plan: 当前执行计划
            executed_step: 刚执行完的步骤

        Returns:
            List[Step]: 需要插入的新步骤列表（如果不需要调整则返回空列表）
        """
        if self.logger:
            self.logger.info(f"正在反思步骤 {executed_step.id} 的执行结果...")

        # 如果步骤执行失败，不进行调整
        if executed_step.status == StepStatus.FAILED:
            return []

        # 构建反思提示
        reflection_prompt = self._build_reflection_prompt(plan, executed_step)

        messages = [
            {"role": "system", "content": "你是一个专业的任务规划助手，擅长根据执行结果动态调整计划。"},
            {"role": "user", "content": reflection_prompt}
        ]

        try:
            response = self.llm_client.chat(messages=messages)
            reflection_result = self._parse_reflection_response(response.get("content", ""))

            # 如果需要调整计划
            if reflection_result.get("need_adjustment", False):
                new_steps = []
                next_step_id = max(step.id for step in plan.steps) + 1

                for i, step_data in enumerate(reflection_result.get("new_steps", [])):
                    step = Step(
                        id=next_step_id + i,
                        description=step_data["description"],
                        goal=step_data["goal"],
                        tool_name=step_data.get("tool_name"),
                        tool_args=step_data.get("tool_args"),
                        dependencies=step_data.get("dependencies", [executed_step.id])
                    )
                    new_steps.append(step)

                if new_steps and self.logger:
                    self.logger.info(f"🔄 根据步骤 {executed_step.id} 的结果，动态添加 {len(new_steps)} 个新步骤")
                    for step in new_steps:
                        self.logger.info(f"   - 新步骤 {step.id}: {step.description}")

                return new_steps

        except Exception as e:
            if self.logger:
                self.logger.warning(f"反思过程出错: {str(e)}")

        return []

    def _build_reflection_prompt(self, plan: Plan, executed_step: Step) -> str:
        """构建反思提示词"""
        # 获取后续待执行的步骤
        pending_steps = [s for s in plan.steps if s.status == StepStatus.PENDING]
        pending_steps_desc = "\n".join([
            f"- 步骤{s.id}: {s.description}"
            for s in pending_steps
        ])

        tools_info = self._get_tools_info()

        return f"""请分析刚执行完的步骤结果，判断是否需要动态调整后续计划。

原始任务：
{plan.task}

刚执行完的步骤：
- 步骤ID: {executed_step.id}
- 描述: {executed_step.description}
- 目标: {executed_step.goal}
- 执行结果: {executed_step.result[:500] if executed_step.result else "无"}

后续待执行的步骤：
{pending_steps_desc if pending_steps_desc else "（无待执行步骤）"}

可用工具：
{tools_info}

请分析执行结果是否包含阻断性问题（hard blocker），即后续步骤无法继续执行的情况。

严格判断规则（默认应该返回 need_adjustment: false）：
- 只有当执行结果中出现明确的阻断性错误（如文件不存在、权限不足、依赖缺失）导致后续步骤无法执行时，才设置 need_adjustment: true
- 如果执行结果是正常的数据、确认信息或成功信息，必须返回 need_adjustment: false
- 绝对不要添加与现有待执行步骤重复的步骤
- 绝对不要添加超出原始任务范围的步骤（如"优化"、"重构"、"改进"、"测试"、"清理"等）
- 绝对不要因为"可以做得更好"而添加步骤，只在"无法继续"时才添加

请按以下JSON格式输出（只输出JSON，不要其他内容）：

```json
{{
  "need_adjustment": false,
  "reason": "不需要调整的原因",
  "new_steps": []
}}
```

只有在确实存在阻断性问题时才使用以下格式：
```json
{{
  "need_adjustment": true,
  "reason": "阻断性问题描述",
  "new_steps": [
    {{
      "description": "解决阻断性问题的步骤描述",
      "goal": "步骤目标",
      "tool_name": "工具名称（可选）",
      "tool_args": {{"arg": "value"}},
      "dependencies": [{executed_step.id}]
    }}
  ]
}}
```"""

    def _parse_reflection_response(self, response: str) -> Dict[str, Any]:
        """解析反思响应"""
        try:
            # 提取JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            result = json.loads(json_str)
            return result

        except Exception as e:
            if self.logger:
                self.logger.error(f"解析反思结果失败: {str(e)}")

            return {
                "need_adjustment": False,
                "reason": "解析失败",
                "new_steps": []
            }
