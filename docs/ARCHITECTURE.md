# 🏗️ 记忆管理系统架构

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        SimpleAgent                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              use_memory_manager=True?                 │  │
│  └───────────────────────────────────────────────────────┘  │
│         │                                    │               │
│         ├─ Yes ──────────────┐               └─ No          │
│         ▼                     │               ▼              │
│  ┌─────────────────┐          │      ┌──────────────────┐   │
│  │ MemoryManager   │          │      │ MessageHistory   │   │
│  └─────────────────┘          │      │  (传统方式)      │   │
│         │                     │      └──────────────────┘   │
└─────────┼─────────────────────┼──────────────────────────────┘
          │                     │
          ▼                     │
┌─────────────────────────────┐ │
│    MemoryManager 内部结构   │ │
│                             │ │
│  ┌───────────────────────┐  │ │
│  │ System Memory         │  │ │
│  │ - 系统提示词          │  │ │
│  │ - 规则配置            │  │ │
│  │ [永久保留]            │  │ │
│  └───────────────────────┘  │ │
│           ↓                 │ │
│  ┌───────────────────────┐  │ │
│  │ Long-term Memory      │  │ │
│  │ - CompressedMemory[]  │  │ │
│  │ - 历史摘要            │  │ │
│  │ [占30%上下文]         │  │ │
│  └───────────────────────┘  │ │
│           ↓                 │ │
│  ┌───────────────────────┐  │ │
│  │ Working Memory        │  │ │
│  │ - deque<MemoryItem>   │  │ │
│  │ - 最近对话            │  │ │
│  │ [动态调整,占70%]      │  │ │
│  └───────────────────────┘  │ │
│                             │ │
│  ┌───────────────────────┐  │ │
│  │ 辅助组件              │  │ │
│  │ - TokenCounter        │◄─┘
│  │ - MemoryCompressor    │
│  └───────────────────────┘
└─────────────────────────────┘
```

## 数据流

### 1. 消息添加流程

```
User/Assistant/Tool Message
         │
         ▼
   add_message()
         │
         ├─ 创建MemoryItem
         │  - content
         │  - role
         │  - timestamp
         │  - importance ← 自动评估
         │  - tokens ← TokenCounter计算
         │
         ├─ 添加到Working Memory
         │  working_memory.append(item)
         │
         └─ 检查是否需要压缩
            _check_and_compress()
                 │
                 ├─ if working_tokens > threshold
                 │       │
                 │       ├─ 提取旧消息(前50%)
                 │       ├─ 调用MemoryCompressor
                 │       │   - 简单压缩(提取关键点)
                 │       │   - 或LLM压缩(生成摘要)
                 │       │
                 │       └─ 生成CompressedMemory
                 │           ├─ 删除原始消息
                 │           └─ 添加到Long-term Memory
                 │
                 └─ else: 不压缩
```

### 2. 上下文构建流程

```
get_context_messages(max_tokens)
         │
         ├─ 1. 添加System Messages (必须)
         │    current_tokens += system_tokens
         │
         ├─ 2. 添加Long-term Memory (最多30%)
         │    for compressed in long_term_memory:
         │        if current_tokens + tokens < max * 0.3:
         │            add_summary()
         │            current_tokens += tokens
         │
         └─ 3. 添加Working Memory (从新到旧)
              for item in reversed(working_memory):
                  if current_tokens + item.tokens <= max:
                      add_message()
                      current_tokens += item.tokens
                  elif item.importance >= 0.8:
                      # 高重要性消息强制包含(最多超10%)
                      if current_tokens + item.tokens <= max * 1.1:
                          add_message()
                          current_tokens += item.tokens
                  else:
                      break  # 停止添加

         return messages
```

## 核心组件详解

### MemoryItem

```python
@dataclass
class MemoryItem:
    content: str          # 消息内容
    role: str             # user/assistant/system/tool
    timestamp: float      # 时间戳
    importance: float     # 重要性(0-1)
    tokens: int           # token数量
    metadata: Dict        # 其他信息(tool_calls等)
```

**重要性评估算法**:
```python
def _evaluate_importance(role, content, metadata):
    base = 0.5

    # 规则评分
    if role == "user":           base = 0.8
    if "tool_calls" in metadata: base = max(base, 0.7)
    if "error" in content:       base = max(base, 0.9)
    if len(content) > 500:       base = max(base, 0.6)

    return base
```

### CompressedMemory

```python
@dataclass
class CompressedMemory:
    summary: str              # 压缩后的摘要
    original_messages: int    # 原始消息数
    original_tokens: int      # 原始token数
    compressed_tokens: int    # 压缩后token数
    timestamp: float          # 压缩时间
    metadata: Dict            # 压缩率等信息
```

### TokenCounter

```python
class TokenCounter:
    def __init__(self, model="gpt-4"):
        self.encoding = tiktoken.encoding_for_model(model)

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def count_messages_tokens(self, messages: List[Dict]) -> int:
        total = 0
        for msg in messages:
            total += 4  # 消息格式开销
            total += self.count_tokens(msg.get("content", ""))
        total += 2  # 对话固定开销
        return total
```

### MemoryCompressor

```python
class MemoryCompressor:
    def compress_messages(self, messages, target_ratio=0.3):
        # 方式1: 简单压缩(快速)
        def _simple_compress(messages):
            key_points = []
            for msg in messages:
                if msg["role"] == "user":
                    key_points.append(f"任务: {msg['content'][:200]}")
                elif "tool_calls" in msg:
                    tools = [tc["function"]["name"] for tc in msg["tool_calls"]]
                    key_points.append(f"工具: {', '.join(tools)}")
                elif msg["role"] == "tool":
                    key_points.append(f"结果: {msg['content'][:150]}")
            return "\n".join(key_points)

        # 方式2: LLM压缩(高质量)
        def _llm_compress(messages, ratio):
            prompt = f"""压缩以下对话,保留{int(ratio*100)}%:
{json.dumps(messages)}
输出简洁摘要:"""
            response = llm_client.chat([{"role": "user", "content": prompt}])
            return response["content"]

        # 选择压缩方式
        if self.llm_client:
            summary = _llm_compress(messages, target_ratio)
        else:
            summary = _simple_compress(messages)

        return CompressedMemory(...)
```

## 配置参数详解

| 参数 | 默认值 | 说明 | 调优建议 |
|-----|-------|------|---------|
| `max_working_memory_tokens` | 2000 | 短期记忆token上限 | 模型上下文的1/3 |
| `max_total_tokens` | 6000 | 总上下文token上限 | 模型上下文的80% |
| `compression_threshold` | 1500 | 触发压缩的阈值 | max_working的75% |
| `llm_client` | None | LLM客户端(压缩用) | 建议提供以获得高质量摘要 |

### 参数关系

```
max_total_tokens (总预算)
    │
    ├─ System Messages (固定)
    │      ~ 500 tokens
    │
    ├─ Long-term Memory (最多30%)
    │      = max_total * 0.3
    │      ≈ 1800 tokens
    │
    └─ Working Memory (动态,最多70%)
           = max_total * 0.7
           ≈ 4200 tokens

           当超过 compression_threshold 时压缩
           compression_threshold < max_working_memory_tokens
```

### 触发时机

```
添加消息
    │
    ├─ working_tokens < compression_threshold
    │      → 不压缩,继续添加
    │
    └─ working_tokens >= compression_threshold
           → 触发压缩
                │
                ├─ 保留最近50%消息
                ├─ 压缩最旧50%消息
                └─ 节省约 35-50% tokens
```

## 性能特性

### 时间复杂度

| 操作 | 复杂度 | 说明 |
|-----|-------|------|
| add_message() | O(1) | deque追加 |
| get_context_messages() | O(n) | n=working_memory大小 |
| _check_and_compress() | O(m) | m=压缩消息数(约n/2) |
| LLM压缩 | O(API) | 取决于API延迟 |

### 空间复杂度

```
总空间 = System + Long-term + Working

System: 固定,约500 tokens
Long-term: k个摘要,每个约300 tokens
Working: n条消息,总计约2000 tokens

总计: ~3000-4000 tokens (远小于不压缩的8000+)
```

### 压缩效率

```
输入: 20条消息, 2000 tokens
输出: 1个摘要, 600 tokens
压缩率: 70% ✓
节省: 1400 tokens ✓

100轮对话的成本节省:
传统: 800K tokens × $0.03/1K = $24
记忆: 390K tokens × $0.03/1K = $11.7
节省: $12.3 (51%) ✓
```

## 扩展性设计

### 未来可添加的功能

```
┌─────────────────────────────────────┐
│     MemoryManager (当前)            │
├─────────────────────────────────────┤
│ + 向量检索 (Semantic Search)        │
│   - 使用向量数据库(Qdrant/Pinecone) │
│   - 根据语义相似度检索历史           │
│                                     │
│ + 持久化存储                         │
│   - SQLite/Redis/PostgreSQL         │
│   - 跨会话记忆保留                   │
│                                     │
│ + 多模态记忆                         │
│   - 图片/文件/结构化数据             │
│   - 不同类型的压缩策略               │
│                                     │
│ + 自适应压缩                         │
│   - 基于使用模式学习                 │
│   - 强化学习优化参数                 │
└─────────────────────────────────────┘
```

## 调试与监控

### 查看统计信息

```python
stats = memory_manager.get_stats()
# {
#     'total_messages': 45,
#     'working_memory_messages': 12,
#     'working_memory_tokens': 1850,
#     'long_term_memory_summaries': 3,
#     'long_term_memory_tokens': 850,
#     'compressions': 3,
#     'total_tokens_saved': 4200,
#     'total_context_tokens': 2700
# }
```

### 可视化记忆状态

```
==================================================
📊 记忆管理统计
==================================================
总消息数: 45
短期记忆: 12条 (1850 tokens) [████████░░] 62%
长期记忆: 3个摘要 (850 tokens)   [███░░░░░░░] 28%
系统消息: 1条 (300 tokens)       [█░░░░░░░░░] 10%
--------------------------------------------------
压缩次数: 3
节省tokens: 4200
当前使用: 2700 / 6000 tokens (45%)
==================================================
```

## 最佳实践

1. **生产环境**: 始终启用记忆管理
2. **LLM压缩**: 提供llm_client以获得高质量摘要
3. **参数调优**: 根据模型和场景调整
4. **监控统计**: 定期检查memory_stats
5. **重要性标注**: 对关键消息手动设置importance

## 测试策略

```python
# 单元测试
def test_memory_compression():
    mm = MemoryManager(compression_threshold=100)
    for i in range(20):
        mm.add_message("user", f"Message {i}" * 10)
    assert mm.stats["compressions"] > 0
    assert mm.stats["total_tokens_saved"] > 0

# 集成测试
def test_agent_with_memory():
    agent = SimpleAgent(..., use_memory_manager=True)
    for task in tasks:
        result = agent.run(task)
    stats = agent.memory_manager.get_stats()
    assert stats["total_context_tokens"] < max_tokens

# 性能测试
def benchmark_memory_manager():
    # 测试100轮对话的性能和成本
    ...
```

---

**架构设计原则**: 简单、高效、可扩展 🚀
