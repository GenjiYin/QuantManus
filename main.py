"""
主入口文件
展示如何使用重构后的QuantManus系统
"""
import sys
import logging
from pathlib import Path

from core import SimpleAgent, LLMClient, setup_logger
from tools import ReadFileTool, WriteFileTool, ListDirectoryTool, PythonExecuteTool
from config.config import global_config


def create_agent() -> SimpleAgent:
    """
    创建并配置Agent

    返回:
        配置好的Agent实例
    """
    # 获取LLM配置
    llm_config = global_config.get_llm_config()

    # 创建LLM客户端
    llm_client = LLMClient(
        model=llm_config.get("model", "gpt-4o"),
        api_key=llm_config.get("api_key", ""),
        base_url=llm_config.get("base_url", "https://api.openai.com/v1"),
        temperature=llm_config.get("temperature", 0.7),
        max_tokens=llm_config.get("max_tokens")
    )

    # 创建工具列表
    tools = [
        ReadFileTool(),
        WriteFileTool(),
        ListDirectoryTool(),
        PythonExecuteTool()
    ]

    # 创建系统提示词
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

注意事项:
- 在执行操作前,先思考是否需要检查文件或目录是否存在
- 执行Python代码时要注意安全性
- 给出的回复要清晰、专业、有条理
"""

    # 获取持久化配置
    persistence_config = global_config.get("persistence", {})
    workspace = global_config.get_workspace_dir()

    # 创建Agent
    agent = SimpleAgent(
        name="QuantManus",
        llm_client=llm_client,
        tools=tools,
        system_prompt=system_prompt,
        max_steps=global_config.get_max_steps(),
        workspace=workspace,
        session_key=persistence_config.get("session_key", "cli:direct"),
        consolidation_threshold=persistence_config.get("consolidation_threshold", 50),
        enable_planning=True,
    )

    return agent


def first_run_setup():
    """首次运行交互式引导，让用户输入 API 配置"""
    print("首次运行，需要配置 API 信息。\n")

    api_key = input("请输入 API Key: ").strip()
    if not api_key:
        print("API Key 不能为空，退出。")
        sys.exit(1)

    base_url = input("请输入 Base URL (回车使用默认 https://api.openai.com/v1): ").strip()
    model = input("请输入模型名称 (回车使用默认 gpt-4o): ").strip()

    global_config.config_data["llm"]["api_key"] = api_key
    if base_url:
        global_config.config_data["llm"]["base_url"] = base_url
    if model:
        global_config.config_data["llm"]["model"] = model

    global_config.save()
    print(f"\n配置已保存到 {global_config.config_path}\n")


def main():
    """
    主函数
    """
    # 首次运行或未配置时，交互式引导
    if not global_config.is_configured:
        first_run_setup()

    # 设置日志
    logger = setup_logger("QuantManus", level="INFO")

    logger.info("=" * 60)
    logger.info("欢迎使用 quantmanus")
    logger.info("=" * 60)

    try:
        # 创建Agent
        logger.info("\n正在初始化Agent...")
        agent = create_agent()
        logger.info("Agent初始化成功!\n")

        # 如果有命令行参数,执行单次任务
        if len(sys.argv) > 1:
            # 从命令行参数获取任务
            task = " ".join(sys.argv[1:])

            # 执行任务
            result = agent.run(task)

            # 打印结果
            logger.info("\n" + "=" * 60)
            logger.info("最终结果:")
            logger.info("=" * 60)
            print(result)

        else:
            # 交互式多轮对话模式
            print("\n交互式对话模式")
            print("输入你的任务,Agent会帮你完成")
            print("输入 'exit' 或 'quit' 退出程序")
            print("输入 'clear' 清空对话历史（归档到长期记忆）")
            print("输入 'new' 开始新会话")
            print("输入 'sessions' 查看所有保存的会话")
            print("输入 'memory' 查看长期记忆内容")
            print("输入 'stats' 查看记忆统计")
            print("输入 'debug' 切换调试模式")
            print("=" * 60 + "\n")

            # 显示已恢复的会话信息
            if agent.use_persistence and agent.session.messages:
                msg_count = len(agent.session.messages)
                print(f"[已恢复上次会话，包含 {msg_count} 条消息]\n")

            while True:
                # 获取用户输入
                try:
                    task = input("你 > ").strip()
                except EOFError:
                    print("\n再见!")
                    break

                # 检查退出命令
                if task.lower() in ['exit', 'quit', '退出']:
                    # 退出前保存会话
                    if agent.use_persistence:
                        agent.save_session()
                        print("[会话已保存]")
                    print("再见!")
                    break

                # 检查调试模式切换
                if task.lower() == 'debug':
                    current_level = logger.level
                    if current_level == logging.DEBUG:
                        logger.setLevel(logging.INFO)
                        print("已切换到INFO模式\n")
                    else:
                        logger.setLevel(logging.DEBUG)
                        print("已切换到DEBUG模式(显示详细信息)\n")
                    continue

                # 清空历史命令（归档到长期记忆）
                if task.lower() in ['clear', '清空']:
                    agent.clear_session(archive=True)
                    print("对话历史已清空（已归档到长期记忆）\n")
                    continue

                # 开始新会话
                if task.lower() in ['new', '新建']:
                    agent.clear_session(archive=True)
                    print("已开始新会话（上次会话已归档到长期记忆）\n")
                    continue

                # 列出所有会话
                if task.lower() in ['sessions', '会话']:
                    sessions = agent.session_manager.list_sessions()
                    if sessions:
                        print("\n保存的会话:")
                        print("-" * 50)
                        for s in sessions:
                            print(f"  Key: {s['key']}")
                            print(f"  更新: {s['updated_at']}")
                            print(f"  路径: {s['path']}")
                            print("-" * 50)
                    else:
                        print("暂无保存的会话")
                    print()
                    continue

                # 查看长期记忆
                if task.lower() in ['memory', '记忆']:
                    content = agent.memory_store.read_long_term()
                    if content:
                        print("\n长期记忆 (MEMORY.md):")
                        print("-" * 50)
                        print(content)
                        print("-" * 50 + "\n")
                    else:
                        print("长期记忆为空（对话足够多后会自动生成）\n")
                    continue

                # 查看统计信息
                if task.lower() in ['stats', '统计']:
                    agent.print_memory_stats()
                    continue

                # 跳过空输入
                if not task:
                    continue

                # 执行任务
                result = agent.run(task)

                # 打印结果（plan_executor 已打印执行进度，此处仅输出最终结果正文）
                print(f"\n{result}\n")

    except KeyboardInterrupt:
        print("\n\n用户中断,程序退出")
        # 退出前保存会话
        if agent.use_persistence:
            agent.save_session()
            print("[会话已保存]")
    except Exception as e:
        logger.error(f"\n错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
