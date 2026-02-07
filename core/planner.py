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

    def create_plan(self, task: str) -> Plan:
        """
        为任务创建执行计划

        Args:
            task: 任务描述

        Returns:
            Plan: 生成的执行计划
        """
        if self.logger:
            self.logger.info(f"开始为任务创建计划: {task}")

        # 准备工具信息
        tools_info = self._get_tools_info()

        # 构造规划提示词
        planning_prompt = self._build_planning_prompt(task, tools_info)

        # 调用LLM生成计划
        messages = [
            {"role": "system", "content": "你是一个专业的任务规划助手，擅长将复杂任务分解为清晰的执行步骤。"},
            {"role": "user", "content": planning_prompt}
        ]

        try:
            response = self.llm_client.chat(messages=messages)
            plan_json = self._parse_plan_response(response.get("content", ""))

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

    def _build_planning_prompt(self, task: str, tools_info: str) -> str:
        """构建规划提示词"""
        return f"""请为以下任务制定详细的执行计划：

任务描述：
{task}

可用工具：
{tools_info}

请按以下JSON格式输出计划（只输出JSON，不要其他内容）：

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
    }},
    {{
      "id": 2,
      "description": "步骤描述",
      "goal": "该步骤要达成的目标",
      "dependencies": [1]
    }}
  ]
}}
```

规划原则：
1. 将复杂任务分解为简单、可执行的步骤
2. 每个步骤应该有明确的目标和预期结果
3. 合理设置步骤之间的依赖关系
4. 如果某个步骤需要使用特定工具，请指定tool_name
5. 步骤数量适中（通常3-8个步骤）
6. 步骤应该按逻辑顺序排列"""

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
