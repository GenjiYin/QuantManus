# 动态规划功能演示

## 快速体验

创建一个简单的测试场景来体验动态规划：

### 1. 创建测试文件

创建文件 `task.txt`：
```
主任务：分析销售数据

步骤：
1. 生成模拟销售数据
2. 进行统计分析

重要：在分析之前，请先阅读 analysis_config.txt 了解分析要求！
```

创建文件 `analysis_config.txt`：
```
分析配置：
- 需要计算总销售额
- 需要计算平均值
- 需要找出最高和最低销售额
- 结果保存到 report.txt

注意：分析完成后，还需要读取 visualization_rules.txt 来生成图表！
```

创建文件 `visualization_rules.txt`：
```
可视化规则：
- 生成柱状图
- 使用蓝色配色
- 标题：销售数据分析
```

### 2. 运行测试

```python
from core import SimpleAgent, LLMClient
from tools import ReadFileTool, WriteFileTool, PythonExecuteTool
from config import GlobalConfig

# 创建Agent
config = GlobalConfig()
llm_config = config.get_llm_config()
llm_client = LLMClient(**llm_config)

agent = SimpleAgent(
    name="DemoAgent",
    llm_client=llm_client,
    tools=[ReadFileTool(), WriteFileTool(), PythonExecuteTool()],
    enable_planning=True  # 启用规划模式（含动态调整）
)

# 执行任务
result = agent.run("读取 task.txt 并完成其中的任务")
```

### 3. 观察输出

你会看到类似这样的执行过程：

```
🤔 正在分析任务并制定执行计划...

执行计划 (0/3):
──────────────────────────────────────
⏳ 步骤 1: 读取task.txt文件
   目标: 了解任务要求

⏳ 步骤 2: 生成模拟销售数据
   目标: 创建测试数据

⏳ 步骤 3: 进行统计分析
   目标: 完成数据分析

是否执行此计划？(y/n，直接回车表示确认):

============================================================
🔄 开始执行步骤 1: 读取task.txt文件
============================================================
✅ 步骤 1 执行成功
结果: 文件内容：主任务：分析销售数据...

🔄 正在反思步骤 1 的执行结果...
🔄 根据步骤 1 的结果，动态添加 1 个新步骤
   - 新步骤 4: 读取 analysis_config.txt 了解分析要求

============================================================
🔄 开始执行步骤 2: 生成模拟销售数据
============================================================
✅ 步骤 2 执行成功

============================================================
🔄 开始执行步骤 4: 读取 analysis_config.txt 了解分析要求
============================================================
✅ 步骤 4 执行成功
结果: 文件内容：分析配置...

🔄 正在反思步骤 4 的执行结果...
🔄 根据步骤 4 的结果，动态添加 1 个新步骤
   - 新步骤 5: 读取 visualization_rules.txt

============================================================
🔄 开始执行步骤 3: 进行统计分析
============================================================
✅ 步骤 3 执行成功

============================================================
🔄 开始执行步骤 5: 读取 visualization_rules.txt
============================================================
✅ 步骤 5 执行成功

============================================================
计划执行完成
============================================================
```

## 关键观察点

### ✅ 灵活性提升

**原系统（僵化）**：
- 读取 task.txt ✅
- 生成数据 ✅
- 分析数据 ✅
- **忽略了 analysis_config.txt 和 visualization_rules.txt！**

**新系统（灵活）**：
- 读取 task.txt ✅
- 🔄 **发现需要读 analysis_config.txt，动态插入步骤**
- 生成数据 ✅
- 读取 analysis_config.txt ✅
- 🔄 **发现需要读 visualization_rules.txt，再次动态插入**
- 分析数据 ✅
- 读取 visualization_rules.txt ✅

### ✅ 智能识别

系统能识别这些模式：
- "请先阅读 xxx 文件"
- "需要先处理 xxx"
- "在...之前，请读取 xxx"
- "注意：还需要读取 xxx"

### ✅ 依赖管理

新插入的步骤会自动：
- 依赖触发它的步骤
- 在合适的位置执行
- 不影响其他步骤

## 与原系统对比

| 特性 | 原系统 | 新系统（动态规划） |
|------|--------|-------------------|
| 执行方式 | 严格按初始计划 | 根据结果动态调整 |
| 文件引用识别 | ❌ 无法识别 | ✅ 自动识别 |
| 多层依赖 | ❌ 容易遗漏 | ✅ 逐层处理 |
| 灵活性 | 低 | 高 |
| 额外开销 | 无 | 每步约1秒 |

## 实际应用场景

### 场景1：项目初始化
```
用户: "根据 project_spec.md 初始化项目"

project_spec.md 内容:
"先阅读 tech_stack.json 了解技术栈..."

系统行为:
1. 读 project_spec.md
2. 🔄 动态插入: 读 tech_stack.json
3. 创建项目结构
```

### 场景2：数据处理流程
```
用户: "处理 config.yaml 中定义的数据流程"

config.yaml 内容:
"预处理规则见 preprocessing.json..."

系统行为:
1. 读 config.yaml
2. 🔄 动态插入: 读 preprocessing.json
3. 应用规则处理数据
```

### 场景3：代码审查
```
用户: "审查 review_checklist.md"

review_checklist.md 内容:
"1. 检查风格规范（见 style_guide.md）
 2. 检查测试覆盖率..."

系统行为:
1. 读 review_checklist.md
2. 🔄 动态插入: 读 style_guide.md
3. 执行审查
```

## 调试技巧

### 查看反思日志

在代码中启用详细日志：
```python
from core import setup_logger
setup_logger(level="DEBUG")
```

查找关键词：
- "正在反思步骤"
- "动态添加"
- "need_adjustment"

### 手动干预

如果想在每次调整时确认：
```python
# 在 plan_executor.py 的反思代码后添加：
if new_steps:
    print(f"\n发现需要添加 {len(new_steps)} 个新步骤:")
    for step in new_steps:
        print(f"  - {step.description}")
    confirm = input("是否添加？(y/n): ")
    if confirm.lower() != 'y':
        new_steps = []
```

## 总结

动态规划功能让系统从**"机械执行者"**变成**"智能协作者"**，能够：

✅ 理解文件间的引用关系
✅ 自动发现隐含的依赖
✅ 灵活调整执行计划
✅ 更接近人类的工作方式

试试吧！创建上面的测试文件，体验一下动态规划的威力！
