# QuantManus

<div align="center">

**一个轻量级、可扩展的 AI Agent 框架**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenAI Compatible](https://img.shields.io/badge/OpenAI-Compatible-green.svg)](https://openai.com/)

作者: **徐啸寅**

</div>

---

## 简介

QuantManus 是一个基于大语言模型（LLM）的智能 Agent 框架，专注于**任务规划与执行**、**持久化记忆**和**技能扩展**。

通过规划-执行-反思闭环和可插拔的技能系统，QuantManus 能够自动分解复杂任务、调用工具完成操作，并在跨会话间保持上下文连续性。

### 核心特性

- **智能任务规划** — 自动分解复杂任务为可执行步骤，简单问题直接回答（无需规划）
- **持久化记忆系统** — 两层持久化架构（MEMORY.md + HISTORY.md），会话跨轮次保持连续性
- **技能扩展系统** — 通过 `~/.quantmanus/skills/` 目录加载技能，支持依赖检查与按需注入
- **动态反思机制** — 基于工具执行结果精确触发反思，仅在实际报错时调整计划
- **工具调用系统** — 支持 OpenAI Function Calling 协议，内置文件读写、目录列出、Python 执行等工具
- **Bootstrap 自定义** — 通过工作空间下的 `bootstrap/` 目录自定义 Agent 身份与行为

---

## 技能生态

QuantManus 通过**技能（Skills）**扩展 Agent 的能力。技能是独立的 Markdown 文件，为 Agent 提供特定领域的专业知识和行为指导。

**官方技能仓库**：[**Awsome-QuantManus-SKILLS**](https://github.com/GenjiYin/Awsome-QuantManus-SKILLS)

技能安装到全局目录 `~/.quantmanus/skills/` 下，目录结构如下：

```
~/.quantmanus/skills/
├── skill-name-a/
│   └── SKILL.md
├── skill-name-b/
│   └── SKILL.md
└── ...
```

每个 `SKILL.md` 文件使用 YAML frontmatter 声明元信息：

```markdown
---
description: "技能描述"
requires: '{"bins": ["pytest"], "env": ["API_KEY"]}'
always: false
---

# 技能正文内容...
```

| 字段 | 说明 |
|------|------|
| `description` | 技能描述，用于 System Prompt 中的技能摘要 |
| `requires` | 依赖声明（可执行文件 `bins` 和环境变量 `env`），不满足时技能不可用 |
| `always` | 设为 `true` 时技能全文始终注入 System Prompt，否则由 LLM 按需读取 |

更多技能和编写指南请参阅 [Awsome-QuantManus-SKILLS](https://github.com/GenjiYin/Awsome-QuantManus-SKILLS)。

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

请输入 API Key: sk-xxxxxxxx
请输入 Base URL (回车使用默认):
请输入模型名称 (回车使用默认):

配置已保存！
```

配置保存在 `~/.quantmanus/config.json`，之后运行不会再询问。

### 工作空间

QuantManus 以**当前目录**作为工作空间。不同目录下的会话数据和记忆互相独立：

```bash
cd ~/my-project
quantmanus              # 工作空间 = ~/my-project

cd ~/another-project
quantmanus              # 工作空间 = ~/another-project，独立的会话
```

### 使用方式

```bash
# 交互式对话模式
quantmanus

# 单次任务模式
quantmanus "创建一个hello.txt文件"
```

交互模式下可用命令：

| 命令 | 说明 |
|------|------|
| `exit` / `quit` | 保存会话并退出 |
| `clear` | 清空对话历史（归档到长期记忆） |
| `new` | 开始新会话 |
| `sessions` | 查看所有保存的会话 |
| `memory` | 查看长期记忆内容 |
| `stats` | 查看记忆统计 |
| `debug` | 切换调试模式 |

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
│  │ 记忆与上下文                                     │ │
│  │  Session (会话历史) ←→ ContextBuilder (上下文)    │ │
│  │  MemoryStore (MEMORY.md + HISTORY.md)           │ │
│  │  SkillsLoader (技能摘要 + 按需注入)              │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
               ↓
┌──────────────────────────────────────────────────────┐
│  工具层                                               │
│  ReadFile │ WriteFile │ ListDir │ Python │ ...       │
└──────────────────────────────────────────────────────┘
```

---

## 记忆系统

### 持久化记忆（默认）

采用两层持久化架构：

| 层级 | 文件 | 作用 |
|------|------|------|
| **会话历史** | `sessions/*.jsonl` | 完整对话记录，JSONL 格式，支持增量写入 |
| **长期记忆** | `memory/MEMORY.md` | LLM 整合的关键事实摘要，覆盖式更新 |
| **时间线日志** | `memory/HISTORY.md` | grep 可搜索的历史日志，追加式写入 |

**工作原理**：

1. `Session` 在内存中管理对话消息，任务结束时持久化到磁盘
2. `ContextBuilder` 每次 LLM 调用前动态构建消息列表（System Prompt + 长期记忆 + 技能 + 会话历史）
3. 当未整合消息数超过阈值时，`MemoryStore` 通过 LLM 将旧消息整合到 MEMORY.md 和 HISTORY.md

### Bootstrap 自定义

在工作空间的 `bootstrap/` 目录下放置 Markdown 文件，可自定义 Agent 的身份和行为：

| 文件 | 用途 |
|------|------|
| `IDENTITY.md` | Agent 身份定义 |
| `SOUL.md` | Agent 性格与行为风格 |
| `USER.md` | 用户偏好信息 |
| `AGENTS.md` | 多 Agent 协作配置 |
| `TOOLS.md` | 工具使用说明 |

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
│   ├── context_builder.py  # 上下文构建（System Prompt + Bootstrap + 技能）
│   ├── skills_loader.py    # 技能加载器（扫描、依赖检查、摘要构建）
│   ├── memory_manager.py   # 旧版内存记忆管理
│   ├── message.py          # 消息类
│   └── logger.py           # 日志工具
├── tools/                   # 工具模块
│   ├── base_tool.py        # 工具基类 & ToolResult
│   ├── file_tool.py        # 文件操作（读取、写入、删除、目录列出）
│   ├── python_tool.py      # Python 代码执行
│   └── system_tool.py      # 系统工具
├── config/                  # 配置模块
│   └── config.py           # 全局配置管理（~/.quantmanus/）
├── examples/                # 示例代码
├── main.py                  # 主入口 & CLI 命令入口
├── pyproject.toml           # 打包配置（pip install -e .）
├── requirements.txt         # 依赖列表
└── README.md
```

**运行时目录**：

| 位置 | 内容 |
|------|------|
| `~/.quantmanus/config.json` | 全局配置（API Key、模型等） |
| `~/.quantmanus/skills/` | 全局技能目录 |
| `当前目录/sessions/` | 当前工作空间的会话数据 |
| `当前目录/memory/MEMORY.md` | 长期事实记忆 |
| `当前目录/memory/HISTORY.md` | 时间线日志 |
| `当前目录/bootstrap/` | 自定义 Bootstrap 文件 |

---

## 开发者用法

```python
from core import SimpleAgent, LLMClient
from tools import ReadFileTool, WriteFileTool, ListDirectoryTool, PythonExecuteTool

# 1. 创建 LLM 客户端
llm_client = LLMClient(
    model="gpt-4o",
    api_key="your-api-key",
    base_url="https://api.openai.com/v1"
)

# 2. 创建工具列表
tools = [
    ReadFileTool(),
    WriteFileTool(),
    ListDirectoryTool(),
    PythonExecuteTool(),
]

# 3. 创建 Agent
agent = SimpleAgent(
    name="QuantManus",
    llm_client=llm_client,
    tools=tools,
    system_prompt="你是一个智能助手",
    enable_planning=True,
    use_persistence=True,
)

# 4. 运行任务
result = agent.run("帮我执行 data_analysis.py")
print(result)

result = agent.run("上一步的输出结果是什么？")  # 能正确回忆
print(result)
```

### 自定义工具

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
