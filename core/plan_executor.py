"""
计划执行器模块 - 负责按步骤执行计划
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from .planner import Plan, Step, StepStatus


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
            print(plan)  # 打印完整计划

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

            # 检查最终状态
            if plan.is_completed() and not plan.has_failed():
                results["success"] = True
                results["final_result"] = self._get_plan_summary(plan)
            else:
                results["error"] = "计划执行未完全成功"

            # 打印最终状态
            if self.logger:
                print("\n" + "=" * 60)
                print("计划执行完成")
                print("=" * 60)
                print(plan)

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

                # 使用agent执行
                result = self.agent.execute_subtask(
                    task=execution_prompt,
                    max_steps=15  # 子任务的最大步骤数（从5增加到15，避免复杂任务被过早终止）
                )

                # 记录结果
                step.result = result
                step.status = StepStatus.COMPLETED
                step.end_time = datetime.now()

                if self.logger:
                    print(f"✅ 步骤 {step.id} 执行成功")
                    result_preview = result[:200] + "..." if len(result) > 200 else result
                    print(f"结果: {result_preview}")

                # 反思机制：根据执行结果动态调整计划
                if self.enable_dynamic_planning and hasattr(self.agent, 'planner'):
                    new_steps = self.agent.planner.reflect_and_adjust_plan(plan, step)
                    if new_steps:
                        # 将新步骤插入到计划中
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
            f"执行以下步骤：",
            f"步骤描述: {step.description}",
            f"目标: {step.goal}",
        ]

        # 添加依赖步骤的结果作为上下文
        if step.dependencies:
            prompt_parts.append("\n依赖步骤的结果：")
            for dep_id in step.dependencies:
                dep_step = plan.get_step(dep_id)
                if dep_step and dep_step.result:
                    prompt_parts.append(f"- 步骤{dep_id}的结果: {dep_step.result[:200]}")

        # 如果指定了工具，添加提示
        if step.tool_name:
            prompt_parts.append(f"\n建议使用工具: {step.tool_name}")
            if step.tool_args:
                prompt_parts.append(f"工具参数参考: {step.tool_args}")

        return "\n".join(prompt_parts)

    def _get_plan_summary(self, plan: Plan) -> str:
        """获取计划执行总结"""
        summary_parts = [
            f"任务: {plan.task}",
            f"\n执行结果:",
        ]

        for step in plan.steps:
            status_symbol = "✅" if step.status == StepStatus.COMPLETED else "❌"
            summary_parts.append(f"\n{status_symbol} 步骤{step.id}: {step.description}")
            if step.result:
                result_preview = step.result[:150] + "..." if len(step.result) > 150 else step.result
                summary_parts.append(f"   {result_preview}")

        return "\n".join(summary_parts)
