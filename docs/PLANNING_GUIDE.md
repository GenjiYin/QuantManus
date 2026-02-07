# 任务规划系统使用指南

## 概述

QuantManus 的任务规划系统允许 AI Agent 在执行复杂任务前先制定详细的执行计划，然后按步骤有序执行。这种方式提高了任务执行的可控性、可追踪性和成功率。

## 核心概念

### 1. Planner (规划器)
- 负责分析用户任务
- 调用 LLM 生成结构化的执行计划
- 自动将复杂任务分解为多个可执行的步骤

### 2. Plan (计划)
- 包含任务的整体思考过程
- 多个有序的执行步骤
- 步骤之间的依赖关系
- 执行进度跟踪

### 3. Step (步骤)
每个步骤包含：
- **ID**: 唯一标识符
- **描述**: 步骤的简要说明
- **目标**: 该步骤要达成的目标
- **工具**: 需要使用的工具 (可选)
- **依赖**: 依赖的其他步骤 (可选)
- **状态**: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED

### 4. PlanExecutor (计划执行器)
- 按照依赖关系执行步骤
- 处理步骤失败和重试
- 跟踪执行进度
- 生成执行摘要

## 使用方法

### 基本使用

```python
from core import SimpleAgent, LLMClient
from tools import ReadFileTool, WriteFileTool, PythonExecuteTool

# 创建 LLM 客户端
llm_client = LLMClient(
    model="your-model",
    api_key="your-api-key"
)

# 创建工具列表
tools = [
    ReadFileTool(),
    WriteFileTool(),
    PythonExecuteTool()
]

# 创建 Agent 并启用规划模式
agent = SimpleAgent(
    name="MyAgent",
    llm_client=llm_client,
    tools=tools,
    enable_planning=True  # 关键：启用规划模式
)

# 执行任务
task = "分析数据并生成报告"
result = agent.run(task)
```

### 规划过程

当启用规划模式后，任务执行流程如下：

1. **任务分析**: Planner 分析任务需求
2. **生成计划**: LLM 生成结构化的执行计划
3. **展示计划**: 向用户展示完整计划
4. **用户确认**: 用户确认是否执行
5. **按步执行**: PlanExecutor 按顺序执行各步骤
6. **返回结果**: 汇总执行结果

### 计划格式示例

```
============================================================
任务: 分析销售数据并生成报告
============================================================

思考过程:
这个任务需要数据生成、保存、分析和报告生成四个步骤。
首先生成模拟数据，然后保存到文件，接着读取分析，最后生成报告。

执行计划 (0/4):
------------------------------------------------------------

⏳ 步骤 1: 生成模拟销售数据
   目标: 创建100条包含日期、产品、销售额的销售记录
   工具: python_execute

⏳ 步骤 2: 保存数据到CSV文件
   目标: 将生成的数据保存为sales_data.csv
   依赖: 步骤1
   工具: write_file

⏳ 步骤 3: 分析数据
   目标: 统计总销售额、平均值、最高和最低销售额
   依赖: 步骤2
   工具: python_execute

⏳ 步骤 4: 生成分析报告
   目标: 创建包含分析结果的报告文件
   依赖: 步骤3
   工具: write_file

============================================================
```

## 配置选项

### Agent 配置

```python
agent = SimpleAgent(
    name="PlanningAgent",
    llm_client=llm_client,
    tools=tools,
    enable_planning=True,        # 启用规划模式
    max_steps=20,                # 单个步骤最大执行次数
    use_memory_manager=True,     # 使用智能记忆管理
    max_context_tokens=6000      # 最大上下文token数
)
```

### 执行配置

```python
# 在 plan_executor.py 中可配置
result = plan_executor.execute_plan(
    plan=plan,
    max_retries=2  # 单个步骤失败后的最大重试次数
)
```

## 适用场景

### 推荐使用规划模式的场景

1. **多步骤任务**: 任务需要3个以上明确的步骤
2. **复杂数据处理**: 数据生成、转换、分析、可视化等
3. **文件批处理**: 批量读取、处理、保存文件
4. **依赖关系明确**: 某些步骤必须在其他步骤之后执行
5. **需要可追踪性**: 希望清楚看到每个步骤的执行状态

### 不推荐使用规划模式的场景

1. **简单单步任务**: 只需要一两个操作即可完成
2. **探索性任务**: 需要根据中间结果灵活调整方向
3. **实时交互**: 需要频繁的用户交互和反馈
4. **快速响应**: 对响应速度要求很高的场景

## 步骤状态管理

### 状态流转

```
PENDING (待执行)
    ↓
RUNNING (执行中)
    ↓
COMPLETED (已完成) / FAILED (失败) / SKIPPED (跳过)
```

### 依赖关系处理

- 步骤只有在所有依赖步骤都完成后才会执行
- 如果依赖的步骤失败，后续步骤会被阻塞
- 支持并行执行没有依赖关系的步骤

## 错误处理

### 步骤失败处理

```python
# 步骤执行失败时
- 记录错误信息
- 根据 max_retries 决定是否重试
- 询问用户是否继续执行后续步骤
```

### 计划失败回退

```python
try:
    # 尝试使用规划模式
    result = agent._run_with_planning(task)
except Exception as e:
    # 失败时回退到普通模式
    logger.info("规划模式失败，回退到普通模式")
    result = agent._run_without_planning(task)
```

## 监控和调试

### 打印执行进度

```python
# 执行过程中会自动打印：
🔄 开始执行步骤 1: 生成模拟数据
✅ 步骤 1 执行成功
执行进度: 1/4
```

### 查看最终状态

```python
# 执行完成后会显示完整的计划状态
print(plan)  # 显示所有步骤及其状态
```

### 获取执行统计

```python
progress = plan.get_progress()
print(progress)
# {
#     "total": 4,
#     "completed": 3,
#     "failed": 1,
#     "pending": 0,
#     "running": 0,
#     "progress": "3/4"
# }
```

## 高级用法

### 自定义规划提示词

修改 `planner.py` 中的 `_build_planning_prompt` 方法来自定义规划逻辑。

### 动态调整计划

```python
# 执行过程中可以动态修改步骤
step = plan.get_step(step_id)
step.status = StepStatus.SKIPPED  # 跳过某个步骤
```

### 保存和恢复计划

```python
# 保存计划到JSON
plan_dict = plan.to_dict()
import json
with open("plan.json", "w") as f:
    json.dump(plan_dict, f, indent=2, ensure_ascii=False)

# 从JSON恢复计划 (需要实现 from_dict 方法)
```

## 性能优化建议

1. **合理设置步骤数量**: 3-8个步骤最佳
2. **避免过细粒度**: 不要将简单操作拆分成过多步骤
3. **使用步骤依赖**: 减少不必要的串行执行
4. **限制重试次数**: 避免在失败步骤上浪费时间
5. **适当的token限制**: 平衡上下文信息和性能

## 示例代码

查看完整示例：
- `examples/example_planning.py` - 规划模式的详细示例
- `examples/example_basic.py` - 对比普通模式和规划模式

## 常见问题

### Q: 如何禁用规划模式？

A: 创建 Agent 时设置 `enable_planning=False` 或不传该参数（默认为 False）。

### Q: 计划生成失败怎么办？

A: 系统会自动回退到普通执行模式，不会影响任务执行。

### Q: 能否修改已生成的计划？

A: 目前在用户确认阶段可以选择不执行。未来可以添加计划编辑功能。

### Q: 规划模式会增加多少执行时间？

A: 规划阶段需要额外的 LLM 调用，通常增加 2-5 秒。但对于复杂任务，整体执行可能更快更准确。

## 总结

任务规划系统为 QuantManus 提供了更强大的任务执行能力：

✅ **更清晰**: 任务分解为明确的步骤
✅ **更可控**: 用户可以查看和确认计划
✅ **更可靠**: 步骤失败处理和重试机制
✅ **更易追踪**: 实时查看执行进度和状态
✅ **更智能**: LLM 自动分析任务并优化执行顺序

推荐在处理复杂任务时启用规划模式，享受更好的执行体验！
