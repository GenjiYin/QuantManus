# QuantManus

<div align="center">

**一个轻量级、智能的 AI Agent 框架**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenAI](https://img.shields.io/badge/OpenAI-Compatible-green.svg)](https://openai.com/)

作者: **徐啸寅**

</div>

---

## 简介

QuantManus 是一个基于大语言模型（LLM）的智能 Agent 框架，专注于解决长对话场景中的上下文管理问题。

麻雀虽小但五脏俱全，通过**持久化记忆系统**和**智能任务规划**，有效防止模型幻觉，降低 API 成本，具备完整的规划-执行-反思能力。

### 核心特性

- **持久化记忆系统** - 两层持久化架构（MEMORY.md + HISTORY.md），会话跨轮次保持连续性
- **智能任务规划** - 自动分解复杂任务为可执行步骤，支持直接回答简单问题（无需规划）
- **动态反思机制** - 基于工具执行结果精确触发反思，仅在实际报错时调整计划
- **工具调用系统** - 支持 OpenAI Function Calling，内置文件读写、删除、目录列出、Python 执行等工具
- **文件操作安全确认** - 覆盖写入和删除文件前必须用户确认（y/n）
- **LLM 实时计时** - 等待大模型响应时动态显示耗时，响应后显示内容预览
- **简洁易用** - 清晰的 API 设计，`pip install -e .` 一键安装，任意目录可用

---

## 架构概览

```
┌──────────────────────────────────────────────────────┐
│                      用户输入                         │
└──────────────┬───────────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────────┐
│  SimpleAgent                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐ │
│  │  Planner   │→ │PlanExecutor│→ │ _think_and_act │ │
│  │ 智能路由:  │  │  步骤执行   │  │   LLM循环      │ │
│  │ 直接回答 / │  │  边界约束   │  │   工具调用      │ │
│  │ 制定计划   │  │  反思机制   │  │                │ │
│  └────────────┘  └────────────┘  └────────────────┘ │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │ 记忆系统                                        │ │
│  │  Session (会话历史) ←→ ContextBuilder (上下文)   │ │
│  │  MemoryStore (MEMORY.md + HISTORY.md)           │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────────┐
│  工具层                                               │
│  ReadFile │ WriteFile │ DeleteFile │ ListDir │ Python │
└──────────────────────────────────────────────────────┘
```

---

## 快速开始

### 安装

```bash
cd quantmanus
pip install -e .
```

安装完成后，可以在**任意目录**下直接运行 `quantmanus` 命令。

### 首次运行

```bash
quantmanus
```

首次运行会自动进入配置引导：

```
首次运行，需要配置 API 信息。

请输入 API Key: sk-xxxxxxxx          ← 粘贴你的密钥，必填
请输入 Base URL (回车使用默认):        ← 不确定就直接回车
请输入模型名称 (回车使用默认):          ← 不确定就直接回车

配置已保存！
```

配置保存在 `~/.quantmanus/config.json`，之后运行不会再询问。

### 工作空间

QuantManus 以**当前目录**作为工作空间。不同目录下的会话数据和记忆互相独立：

```bash
cd D:\my-project
quantmanus              # 工作空间 = D:\my-project

cd D:\another-project
quantmanus              # 工作空间 = D:\another-project，独立的会话
```

### 使用方式

```bash
# 交互式对话模式
quantmanus

# 单次任务模式
quantmanus "创建一个hello.txt文件"
```

---

## 任务规划系统

QuantManus 的规划系统会智能判断任务类型：

### 简单问题 — 直接回答

对于回忆历史、闲聊、总结等不需要工具的任务，Planner 直接从对话上下文中回答，跳过整个规划流程：

```
你 > 上一步脚本的输出结果是什么？
⏱️  等待 LLM 响应: 1.2s ...
⏱️  LLM 响应完成，耗时: 2.1s | 上次执行 1.py 的输出结果...

上次执行 1.py 的输出结果如下：
low : 最低价（后复权）
date: 日期
...
```

### 复杂任务 — 规划后执行

对于需要工具的任务，自动分解为步骤，展示计划给用户确认后执行：

```
你 > 请执行1.py脚本
⏱️  LLM 响应完成，耗时: 5.2s | ...

============================================================
任务: 请执行1.py脚本
============================================================

执行计划 (0/1):
------------------------------------------------------------
⏳ 步骤 1: 执行1.py脚本并返回输出结果
   目标: 运行脚本并展示输出
   工具: execute_python
============================================================

是否执行此计划？(y/n，直接回车表示确认):
```

### 规划系统特性

- **智能路由**: Planner 自动判断是否需要工具，简单问题直接回答
- **步骤边界约束**: 每个步骤只做自己该做的事，不越权执行后续步骤
- **精确反思触发**: 仅在工具执行实际失败（`ToolResult.success=False`）时触发反思，不再基于关键词误判
- **对话连续性**: 用户的原始问题和最终结果都会记录到会话中，确保跨轮次上下文完整

---

## 记忆系统

### 持久化模式（默认）

采用两层持久化记忆：

| 层级 | 文件 | 作用 |
|------|------|------|
| **会话历史** | `sessions/*.jsonl` | 完整对话记录，JSONL 格式，支持增量写入 |
| **长期记忆** | `memory/MEMORY.md` | LLM 整合的关键事实摘要，覆盖式更新 |
| **时间线日志** | `memory/HISTORY.md` | grep 可搜索的历史日志，追加式写入 |

**工作原理**：

1. `Session` 对象在内存中管理对话消息，任务结束时持久化到磁盘
2. `ContextBuilder` 每次 LLM 调用前动态构建消息列表（System Prompt + 长期记忆 + 会话历史 + 运行时上下文）
3. 当未整合消息数超过阈值时，`MemoryStore` 通过 LLM 将旧消息整合到 MEMORY.md 和 HISTORY.md

### 旧版内存记忆模式

通过 `use_memory_manager=True` 启用（非持久化），采用三层内存架构：

- **系统记忆** — 固定的系统提示词，永久保留
- **长期记忆** — 压缩后的历史摘要，保留关键信息
- **短期记忆** — 最近的原始对话，动态管理

---

## 开发者用法

```python
from core import SimpleAgent, LLMClient
from tools import ReadFileTool, WriteFileTool, DeleteFileTool, PythonExecuteTool, ListDirectoryTool

# 1. 创建 LLM 客户端
llm_client = LLMClient(
    model="gpt-4o",
    api_key="your-api-key",
    base_url="https://api.openai.com/v1"
)

# 2. 创建工具列表
tools = [
    ReadFileTool(),          # 文件读取
    WriteFileTool(),         # 文件写入（覆盖时需用户确认）
    DeleteFileTool(),        # 文件删除（需用户确认）
    ListDirectoryTool(),     # 目录列出
    PythonExecuteTool(),     # Python 代码执行
]

# 3. 创建 Agent
agent = SimpleAgent(
    name="QuantManus",
    llm_client=llm_client,
    tools=tools,
    system_prompt="你是一个智能助手",
    enable_planning=True,    # 启用任务规划
    use_persistence=True,    # 启用持久化记忆（默认）
)

# 4. 运行任务（同一 agent 实例多次调用 run()，对话上下文自动保持）
result = agent.run("帮我执行 data_analysis.py")
print(result)

result = agent.run("上一步的输出结果是什么？")  # 能正确回忆
print(result)
```

---

## 文件操作安全

涉及文件覆盖和删除的操作，必须用户在命令行确认：

```
⚠️  文件已存在: output.txt
是否覆盖该文件？(y/n): y

⚠️  即将删除文件: temp.py
确认删除？(y/n): n
```

用户输入 `n` 时操作取消，工具返回 `ToolResult(success=False)`。

---

## LLM 实时计时

等待大模型响应时，终端实时显示计时：

```
⏱️  等待 LLM 响应: 3.2s ...          ← 每 0.1 秒刷新
⏱️  LLM 响应完成，耗时: 3.42s | 脚本已成功执行，输出结果为...  ← 完成后显示耗时 + 内容预览
```

所有经过 `LLMClient.chat()` 的调用都会自动计时，包括：Agent 思考、计划生成、反思调整、记忆整合。

---

## 项目结构

```
quantmanus/
├── core/                    # 核心模块
│   ├── agent.py            # Agent 核心类（任务路由、执行循环、会话管理）
│   ├── llm_client.py       # LLM 客户端（实时计时）
│   ├── planner.py          # 规划器（智能路由：直接回答 / 制定计划）
│   ├── plan_executor.py    # 计划执行器（步骤边界约束、精确反思触发）
│   ├── session.py          # 会话持久化（JSONL 格式）
│   ├── memory_store.py     # 持久化记忆（MEMORY.md + HISTORY.md）
│   ├── context_builder.py  # 上下文构建（动态 System Prompt + Bootstrap）
│   ├── memory_manager.py   # 旧版内存记忆管理
│   ├── message.py          # 消息类
│   └── logger.py           # 日志工具
├── tools/                   # 工具模块
│   ├── base_tool.py        # 工具基类 & ToolResult
│   ├── file_tool.py        # 文件操作（读取、写入、删除、目录列出）
│   ├── python_tool.py      # Python 代码执行
│   ├── system_tool.py      # 系统工具
│   └── dai_engine.py       # DAI 引擎工具
├── config/                  # 配置模块
│   └── config.py           # 全局配置管理（~/.quantmanus/）
├── examples/                # 示例代码
│   ├── example_basic.py    # 基本用法示例
│   └── example_planning.py # 规划模式示例
├── main.py                  # 主入口 & CLI 命令入口
├── pyproject.toml           # 打包配置（pip install -e .）
├── requirements.txt         # 依赖列表
└── README.md
```

**运行时目录**：

| 位置 | 内容 |
|------|------|
| `~/.quantmanus/config.json` | 全局配置（API Key、模型等） |
| `当前目录/sessions/` | 当前工作空间的会话数据 |
| `当前目录/memory/MEMORY.md` | 长期事实记忆 |
| `当前目录/memory/HISTORY.md` | 时间线日志 |
| `当前目录/bootstrap/` | 自定义 Bootstrap 文件（SOUL.md、USER.md 等） |

---

## 自定义工具

```python
from tools import BaseTool, ToolResult

class MyCustomTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="这是一个自定义工具"
        )

    def get_parameters(self):
        return {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "参数1描述"
                }
            },
            "required": ["param1"]
        }

    def execute(self, param1: str):
        result = f"处理: {param1}"
        return ToolResult(success=True, output=result)

# 使用
tools = [MyCustomTool(), ReadFileTool()]
agent = SimpleAgent(..., tools=tools)
```

---

## 配置参数

```python
SimpleAgent(
    name="agent_name",             # Agent 名称
    llm_client=llm_client,         # LLM 客户端
    tools=tools,                   # 工具列表
    system_prompt="提示词",        # 系统提示词
    max_steps=20,                  # 最大执行步数
    enable_planning=True,          # 启用任务规划模式
    use_persistence=True,          # 持久化模式（默认，推荐）
    use_memory_manager=False,      # 旧版内存记忆模式
    consolidation_threshold=50,    # 触发记忆整合的消息数阈值
)
```

---

## 效果

![](./figure/fig1.png)
![](./figure/fig2.png)

---

## 许可证

本项目采用 MIT 许可证。

---

## 作者

**徐啸寅**

---

<div align="center">

Made with ❤️ by 徐啸寅

</div>
