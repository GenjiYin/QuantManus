"""
记忆管理示例
展示如何使用智能记忆管理系统来防止大模型幻觉
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import SimpleAgent, LLMClient, setup_logger
from tools import ReadFileTool, WriteFileTool, ListDirectoryTool, PythonExecuteTool
from config.config import global_config


def example_without_memory_management():
    """
    示例1: 不使用记忆管理(传统方式)

    问题: 随着对话增长,上下文会越来越大,最终导致:
    1. Token超限
    2. 模型性能下降
    3. 出现幻觉
    """
    print("\n" + "="*70)
    print("示例1: 传统方式(无记忆管理)")
    print("="*70)

    llm_config = global_config.get_llm_config()
    llm_client = LLMClient(
        model=llm_config.get("model", "gpt-4o"),
        api_key=llm_config.get("api_key", ""),
        base_url=llm_config.get("base_url", "https://api.openai.com/v1")
    )

    tools = [
        ReadFileTool(),
        WriteFileTool(),
        ListDirectoryTool(),
        PythonExecuteTool()
    ]

    # 创建Agent - 不使用记忆管理
    agent = SimpleAgent(
        name="TraditionalAgent",
        llm_client=llm_client,
        tools=tools,
        system_prompt="你是一个智能助手",
        use_memory_manager=False  # 关闭记忆管理
    )

    # 模拟多轮对话
    tasks = [
        "列出当前目录的文件",
        "读取README.md文件",
        "用Python计算1到100的和",
        "创建一个新文件test.txt",
        # ... 随着任务增多,上下文会越来越大
    ]

    for task in tasks:
        print(f"\n任务: {task}")
        result = agent.run(task)
        print(f"结果: {result}\n")

    print("\n⚠️ 问题: 随着对话增长,message_history会不断积累,")
    print("   可能导致token超限或模型性能下降\n")


def example_with_memory_management():
    """
    示例2: 使用智能记忆管理

    优势:
    1. 自动压缩旧对话
    2. 保留重要信息
    3. 控制上下文大小
    4. 防止幻觉
    """
    print("\n" + "="*70)
    print("示例2: 智能记忆管理(推荐)")
    print("="*70)

    llm_config = global_config.get_llm_config()
    llm_client = LLMClient(
        model=llm_config.get("model", "gpt-4o"),
        api_key=llm_config.get("api_key", ""),
        base_url=llm_config.get("base_url", "https://api.openai.com/v1")
    )

    tools = [
        ReadFileTool(),
        WriteFileTool(),
        ListDirectoryTool(),
        PythonExecuteTool()
    ]

    system_prompt = """你是一个智能助手,能够帮助用户完成各种任务。

你可以使用以下工具:
1. read_file - 读取文件内容
2. write_file - 写入文件
3. list_directory - 列出目录内容
4. execute_python - 执行Python代码

工作流程:
1. 理解用户的任务需求
2. 制定解决方案
3. 使用合适的工具执行操作
4. 根据结果调整策略
5. 完成任务后给出清晰的总结
"""

    # 创建Agent - 启用智能记忆管理
    agent = SimpleAgent(
        name="SmartAgent",
        llm_client=llm_client,
        tools=tools,
        system_prompt=system_prompt,
        use_memory_manager=True,  # 启用记忆管理
        max_context_tokens=6000    # 设置最大上下文tokens
    )

    print("\n✓ 已启用智能记忆管理")
    print("  - 自动压缩旧对话")
    print("  - 保留重要信息")
    print("  - 控制上下文大小\n")

    # 模拟多轮对话
    tasks = [
        "列出当前目录的文件",
        "读取main.py文件",
        "用Python计算1到100的和",
        "创建一个新文件test_memory.txt,写入'Memory test'",
        "总结一下我们都做了什么",
    ]

    for i, task in enumerate(tasks, 1):
        print(f"\n{'='*70}")
        print(f"任务 {i}/{len(tasks)}: {task}")
        print('='*70)

        result = agent.run(task)

        print(f"\n结果: {result}")

        # 显示记忆统计
        agent.print_memory_stats()

    print("\n✓ 优势: 即使对话很长,上下文大小也保持可控")
    print("  - 旧对话自动压缩成摘要")
    print("  - 重要信息优先保留")
    print("  - 防止token超限和模型幻觉\n")


def example_memory_compression():
    """
    示例3: 演示记忆压缩机制
    """
    print("\n" + "="*70)
    print("示例3: 记忆压缩机制演示")
    print("="*70)

    from core import MemoryManager, LLMClient

    llm_config = global_config.get_llm_config()
    llm_client = LLMClient(
        model=llm_config.get("model", "gpt-4o"),
        api_key=llm_config.get("api_key", ""),
        base_url=llm_config.get("base_url", "https://api.openai.com/v1")
    )

    # 创建记忆管理器(设置较小的阈值以快速触发压缩)
    memory_manager = MemoryManager(
        max_working_memory_tokens=500,   # 短期记忆最大500 tokens
        max_total_tokens=2000,            # 总上下文最大2000 tokens
        compression_threshold=400,        # 超过400 tokens触发压缩
        llm_client=llm_client
    )

    # 添加系统消息
    memory_manager.add_system_message("你是一个智能助手")

    print("\n配置:")
    print(f"  - 短期记忆上限: 500 tokens")
    print(f"  - 压缩阈值: 400 tokens")
    print(f"  - 总上下文上限: 2000 tokens\n")

    # 模拟大量对话
    print("模拟大量对话...")
    for i in range(10):
        memory_manager.add_message(
            "user",
            f"这是第{i+1}个问题,请帮我做一些数据分析和计算" * 5  # 故意增加长度
        )
        memory_manager.add_message(
            "assistant",
            f"好的,我已经完成了第{i+1}个任务的分析和计算,结果如下..." * 5
        )

        if (i + 1) % 3 == 0:
            print(f"\n--- 添加了 {i+1} 轮对话 ---")
            memory_manager.print_stats()

    print("\n\n✓ 观察: 随着对话增多,旧消息被自动压缩")
    print("  - 短期记忆保持较小")
    print("  - 长期记忆存储摘要")
    print("  - 总token数被控制在合理范围内\n")

    # 显示最终上下文
    print("\n最终上下文消息:")
    final_messages = memory_manager.get_context_messages()
    for i, msg in enumerate(final_messages, 1):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        content_preview = content[:80] + "..." if len(content) > 80 else content
        print(f"{i}. [{role}] {content_preview}")


def example_importance_based_retention():
    """
    示例4: 基于重要性的记忆保留
    """
    print("\n" + "="*70)
    print("示例4: 基于重要性的记忆保留")
    print("="*70)

    from core import MemoryManager

    memory_manager = MemoryManager(
        max_working_memory_tokens=1000,
        max_total_tokens=3000,
        compression_threshold=800,
        llm_client=None  # 简单压缩,不用LLM
    )

    # 添加不同重要性的消息
    print("\n添加不同重要性的消息:\n")

    messages = [
        ("user", "你好", 0.3, "普通打招呼"),
        ("assistant", "你好!有什么可以帮你的?", 0.3, "普通回复"),
        ("user", "请帮我分析一下销售数据", 0.9, "重要任务"),
        ("assistant", "好的,我会调用数据分析工具", 0.7, "工具调用决策"),
        ("tool", "分析结果: 销售额增长15%...(大量数据)", 0.8, "重要结果"),
        ("user", "天气怎么样?", 0.2, "闲聊"),
        ("assistant", "我不知道天气,需要调用API", 0.2, "次要信息"),
        ("user", "那继续刚才的分析", 0.9, "关键任务"),
    ]

    for role, content, importance, desc in messages:
        memory_manager.add_message(role, content, importance=importance)
        print(f"  [{role:10}] 重要性={importance:.1f} - {desc}")

    print("\n\n获取上下文(token限制=200):")
    context = memory_manager.get_context_messages(max_tokens=200)

    print(f"\n最终包含的消息数: {len(context)}")
    print("\n✓ 观察: 低重要性消息(如闲聊)被优先丢弃")
    print("  - 高重要性消息(任务、结果)被保留")
    print("  - 即使token有限,关键信息也不会丢失\n")

    for msg in context:
        print(f"  - [{msg['role']}] {msg['content'][:50]}")


def main():
    """主函数 - 运行所有示例"""

    logger = setup_logger("MemoryExample", level="INFO")

    print("\n" + "="*70)
    print("智能记忆管理系统 - 完整示例")
    print("="*70)
    print("\n本示例将展示:")
    print("1. 传统方式的问题")
    print("2. 智能记忆管理的优势")
    print("3. 记忆压缩机制")
    print("4. 基于重要性的保留策略")

    input("\n按回车开始运行示例...")

    # 运行示例
    try:
        # 示例3: 记忆压缩(不需要实际执行任务)
        example_memory_compression()

        input("\n按回车继续下一个示例...")

        # 示例4: 重要性保留
        example_importance_based_retention()

        print("\n" + "="*70)
        print("示例运行完成!")
        print("="*70)

        print("\n📝 总结:")
        print("✓ 智能记忆管理可以有效防止大模型幻觉")
        print("✓ 通过压缩和重要性评分,保持上下文精简且有用")
        print("✓ 适合长对话场景,如复杂任务、多轮交互等")
        print("\n💡 建议:")
        print("- 在生产环境中,始终开启 use_memory_manager=True")
        print("- 根据模型上下文窗口调整 max_context_tokens")
        print("- 定期查看 memory_stats 了解记忆使用情况")

    except Exception as e:
        logger.error(f"示例运行出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
