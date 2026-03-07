"""
计划执行器模块 - 负责按步骤执行计划
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from .planner import Plan, Step, StepStatus

# 终局反思最多追加的轮数，防止无限循环
_MAX_FINAL_RECOVERY_ROUNDS = 2


class PlanExecutor:
    """计划执行器 - 按步骤执行计划"""

    def __init__(self, agent, logger=None, enable_dynamic_planning=True):
        """
        初始化计划执行器

        Args:
            agent: SimpleAgent实例
            logger: 日志记录器
            enable_dynamic_planning: 是否启用动态规划（反思机制）
        """
        self.agent = agent
        self.logger = logger
        self.enable_dynamic_planning = enable_dynamic_planning

    def execute_plan(self, plan: Plan, max_retries: int = 2) -> Dict[str, Any]:
        """
        执行计划

        Args:
            plan: 要执行的计划
            max_retries: 单个步骤的最大重试次数

        Returns:
            Dict: 执行结果
        """
        if self.logger:
            self.logger.info(f"开始执行计划: {plan.task}")

        results = {
            "success": False,
            "completed_steps": 0,
            "failed_steps": 0,
            "final_result": None,
            "error": None
        }

        try:
            while not plan.is_completed():
                # 获取下一批可执行的步骤
                next_steps = plan.get_next_steps()

                if not next_steps:
                    if plan.has_failed():
                        results["error"] = "存在失败的步骤，无法继续执行"
                        break
                    else:
                        # 可能是所有步骤都完成了
                        break

                # 执行这批步骤
                for step in next_steps:
                    self._execute_step(step, plan, max_retries)

                    if step.status == StepStatus.COMPLETED:
                        results["completed_steps"] += 1
                    elif step.status == StepStatus.FAILED:
                        results["failed_steps"] += 1

                # 打印进度
                if self.logger:
                    progress = plan.get_progress()
                    self.logger.info(f"执行进度: {progress['progress']}")

            # 终局反思：检查原始任务是否已通过已执行步骤完成
            # 无论步骤全部成功还是部分失败都需要检查，
            # 因为"准备工作全部成功但核心操作尚未执行"也需要追加步骤
            if self.enable_dynamic_planning and hasattr(self.agent, 'planner'):
                recovery_round = 0
                while recovery_round < _MAX_FINAL_RECOVERY_ROUNDS:
                    recovery_round += 1
                    if self.logger:
                        self.logger.info(f"🔄 终局反思第 {recovery_round} 轮：检查任务是否已完成...")

                    recovery_steps = self._final_recovery(plan)
                    if not recovery_steps:
                        break

                    for new_step in recovery_steps:
                        plan.add_step(new_step)
                        if self.logger:
                            self.logger.info(f"📌 追加步骤: {new_step.id} - {new_step.description}")

                    # 执行追加步骤
                    while True:
                        next_steps = plan.get_next_steps()
                        if not next_steps:
                            break
                        for step in next_steps:
                            self._execute_step(step, plan, max_retries)
                            if step.status == StepStatus.COMPLETED:
                                results["completed_steps"] += 1
                            elif step.status == StepStatus.FAILED:
                                results["failed_steps"] += 1

            # 检查最终状态
            if not plan.has_failed():
                results["success"] = True
                results["final_result"] = self._get_plan_summary(plan)
            else:
                results["error"] = "计划执行未完全成功"
                results["final_result"] = self._get_plan_summary(plan)

            # 打印最终状态
            if self.logger:
                print("\n" + "=" * 60)
                print("计划执行完成")
                print("=" * 60)

        except Exception as e:
            results["error"] = f"执行计划时出错: {str(e)}"
            if self.logger:
                self.logger.error(results["error"])

        return results

    def _execute_step(self, step: Step, plan: Plan, max_retries: int):
        """
        执行单个步骤

        Args:
            step: 要执行的步骤
            plan: 所属计划
            max_retries: 最大重试次数
        """
        if self.logger:
            print(f"\n{'='*60}")
            print(f"🔄 开始执行步骤 {step.id}: {step.description}")
            print(f"{'='*60}")

        step.status = StepStatus.RUNNING
        step.start_time = datetime.now()

        retry_count = 0
        while retry_count <= max_retries:
            try:
                # 构造执行提示
                execution_prompt = self._build_execution_prompt(step, plan)

                # 使用agent执行（不限制工具，让 LLM 自主选择最合适的工具）
                result = self.agent.execute_subtask(
                    task=execution_prompt,
                    max_steps=5,
                    allowed_tools=None
                )

                # 记录结果，根据工具执行情况判断步骤是否真正成功
                step.result = result
                step.end_time = datetime.now()
                tool_had_error = getattr(self.agent, '_last_tool_had_error', False)

                if tool_had_error:
                    step.status = StepStatus.FAILED
                    step.error = "工具执行报错"
                    if self.logger:
                        print(f"⚠️ 步骤 {step.id} 工具执行遇到错误")
                else:
                    step.status = StepStatus.COMPLETED
                    if self.logger:
                        print(f"✅ 步骤 {step.id} 执行成功")

                # 反思机制：工具报错时触发，尝试动态补救
                if tool_had_error and self.enable_dynamic_planning and hasattr(self.agent, 'planner'):
                    new_steps = self.agent.planner.reflect_and_adjust_plan(plan, step)
                    if new_steps:
                        for new_step in new_steps:
                            plan.add_step(new_step)
                            if self.logger:
                                self.logger.info(f"📌 已添加新步骤: {new_step.id} - {new_step.description}")

                break  # 成功则退出重试循环

            except Exception as e:
                retry_count += 1
                error_msg = str(e)

                if retry_count > max_retries:
                    step.status = StepStatus.FAILED
                    step.error = f"执行失败（重试{max_retries}次后）: {error_msg}"
                    step.end_time = datetime.now()

                    if self.logger:
                        self.logger.error(f"❌ 步骤 {step.id} 执行失败: {step.error}")

                    # 询问用户是否继续
                    if self.logger:
                        print(f"\n步骤 {step.id} 执行失败，是否继续？(y/n)")
                        # 注：在实际应用中，这里可以实现更复杂的错误处理策略
                else:
                    if self.logger:
                        self.logger.warning(f"⚠️ 步骤 {step.id} 执行失败，重试 {retry_count}/{max_retries}")

    def _build_execution_prompt(self, step: Step, plan: Plan) -> str:
        """构建步骤执行提示"""
        prompt_parts = [
            f"你现在只需要执行下面这一个步骤，完成后立即汇报结果并停止。",
            f"",
            f"步骤描述: {step.description}",
            f"目标: {step.goal}",
        ]

        # 添加依赖步骤的结果作为上下文
        if step.dependencies:
            prompt_parts.append("\n依赖步骤的结果：")
            for dep_id in step.dependencies:
                dep_step = plan.get_step(dep_id)
                if dep_step and dep_step.result:
                    prompt_parts.append(f"- 步骤{dep_id}的结果: {dep_step.result[:2000]}")

        # 如果指定了工具，添加提示
        if step.tool_name:
            prompt_parts.append(f"\n建议使用工具: {step.tool_name}")
            if step.tool_args:
                prompt_parts.append(f"工具参数参考: {step.tool_args}")

        # 严格边界约束
        prompt_parts.append(
            f"\n严格约束："
            f"\n- 只做上述步骤描述的操作，不要超出范围"
            f"\n- 不要提前执行后续步骤的工作（后续步骤会由系统自动调度）"
            f"\n- 汇报结果时，必须包含工具返回的实际数据/输出内容，不要只写摘要或概述"
            f"\n- 完成当前步骤后直接输出结果即可"
        )

        return "\n".join(prompt_parts)

    def _get_plan_summary(self, plan: Plan) -> str:
        """获取计划执行总结

        注意：此结果会存入 session 供后续对话引用，不做截断以保留完整数据。
        显示层（main.py）如有需要可自行截断。
        """
        # 如果只有一个步骤且成功，直接返回该步骤的结果（避免冗余包装）
        completed = [s for s in plan.steps if s.status == StepStatus.COMPLETED and s.result]
        if len(plan.steps) == 1 and len(completed) == 1:
            return completed[0].result

        summary_parts = [
            f"任务: {plan.task}",
            f"\n执行结果:",
        ]

        for step in plan.steps:
            status_symbol = "✅" if step.status == StepStatus.COMPLETED else "❌"
            summary_parts.append(f"\n{status_symbol} 步骤{step.id}: {step.description}")
            if step.result:
                summary_parts.append(f"   {step.result}")

        return "\n".join(summary_parts)

    def _final_recovery(self, plan: Plan) -> List[Step]:
        """
        终局反思：评估原始任务是否已完成，若未完成则生成补救步骤

        与步骤级反思不同，这里关注的是整体任务目标。
        例如: pip install 成功了，但还没有回去用安装好的库读 PDF。

        Returns:
            List[Step]: 需要追加的补救步骤，无需补救则返回空列表
        """
        planner = self.agent.planner

        # 收集所有步骤的执行摘要
        steps_summary = []
        for s in plan.steps:
            status = "成功" if s.status == StepStatus.COMPLETED else "失败"
            result_preview = (s.result[:2000] + "...") if s.result and len(s.result) > 2000 else (s.result or "无")
            steps_summary.append(
                f"- 步骤{s.id} [{status}]: {s.description}\n  结果: {result_preview}"
            )

        tools_info = planner._get_tools_info()
        next_step_id = max(s.id for s in plan.steps) + 1

        prompt = f"""请判断原始任务是否已通过已执行的步骤完成。

原始任务：
{plan.task}

已执行步骤及结果：
{chr(10).join(steps_summary)}

可用工具：
{tools_info}

判断规则：
- 如果原始任务的最终目标已经达成（如用户要求的总结、数据、文件等已经产出），返回空步骤。
- 如果最终目标未达成（如只完成了准备工作但没有执行核心操作），请生成必要的补救步骤来完成任务。
- 补救步骤应直接针对未完成的核心操作，不要重复已成功的步骤。

请按以下JSON格式输出（只输出JSON，不要其他内容）：

```json
{{
  "task_completed": false,
  "reason": "原因说明",
  "new_steps": [
    {{
      "description": "补救步骤描述",
      "goal": "步骤目标",
      "tool_name": "工具名称（可选）",
      "dependencies": []
    }}
  ]
}}
```

如果任务已完成：
```json
{{
  "task_completed": true,
  "reason": "任务已完成的说明",
  "new_steps": []
}}
```"""

        try:
            messages = [
                {"role": "system", "content": "你是一个专业的任务规划助手，擅长评估任务完成度并制定补救方案。"},
                {"role": "user", "content": prompt}
            ]
            response = planner.llm_client.chat(messages=messages)
            result = planner._parse_reflection_response(response.get("content", ""))

            if result.get("task_completed", True):
                return []

            new_steps = []
            for i, step_data in enumerate(result.get("new_steps", [])):
                step = Step(
                    id=next_step_id + i,
                    description=step_data["description"],
                    goal=step_data.get("goal", step_data["description"]),
                    tool_name=step_data.get("tool_name"),
                    tool_args=step_data.get("tool_args"),
                    dependencies=step_data.get("dependencies", [])
                )
                new_steps.append(step)

            return new_steps

        except Exception as e:
            if self.logger:
                self.logger.warning(f"终局反思出错: {e}")
            return []
