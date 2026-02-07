"""
主入口文件
展示如何使用重构后的QuantManus系统
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core import SimpleAgent, LLMClient, Message, setup_logger
from tools import ReadFileTool, WriteFileTool, ListDirectoryTool, PythonExecuteTool
from config.config import global_config
import logging


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
        max_tokens=llm_config.get("max_tokens", 4096)
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

    # 创建Agent
    agent = SimpleAgent(
        name="QuantManus",
        llm_client=llm_client,
        tools=tools,
        system_prompt=system_prompt,
        max_steps=global_config.get_max_steps(),
        use_memory_manager=True,      # ← 启用记忆管理
        enable_planning=True          # ← 启用规划模式
    )

    return agent

def main():
    """
    主函数
    """
    # 设置日志
    logger = setup_logger("QuantManus", level="INFO")

    logger.info("="*60)
    logger.info("欢迎使用 quantmanus ")
    logger.info("="*60)

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
            logger.info("\n" + "="*60)
            logger.info("最终结果:")
            logger.info("="*60)
            print(result)  # 最终结果用print输出,更清晰

        else:
            # 交互式多轮对话模式
            print("\n交互式对话模式")
            print("输入你的任务,Agent会帮你完成")
            print("输入 'exit' 或 'quit' 退出程序")
            print("输入 'clear' 清空对话历史")
            print("输入 'debug' 切换调试模式")
            print("="*60 + "\n")

            while True:
                # 获取用户输入
                try:
                    task = input("你 > ").strip()
                except EOFError:
                    print("\n再见!")
                    break

                # 检查退出命令
                if task.lower() in ['exit', 'quit', '退出']:
                    print("再见!")
                    break

                # 检查调试模式切换
                if task.lower() == 'debug':
                    current_level = logger.level
                    if current_level == logging.DEBUG:
                        logger.setLevel(logging.INFO)
                        print("✓ 已切换到INFO模式\n")
                    else:
                        logger.setLevel(logging.DEBUG)
                        print("✓ 已切换到DEBUG模式(显示详细信息)\n")
                    continue

                # 检查清空历史命令
                if task.lower() in ['clear', '清空']:
                    agent.message_history.clear()
                    # 重新添加系统提示词
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
                    agent.message_history.add_message(
                        Message.system_message(system_prompt)
                    )
                    print("✓ 对话历史已清空\n")
                    continue

                # 跳过空输入
                if not task:
                    continue

                # 执行任务
                result = agent.run(task)

                # 打印结果
                print("\n" + "-"*60)
                print(f"最终结果: {result}")
                print("-"*60 + "\n")

    except KeyboardInterrupt:
        print("\n\n用户中断,程序退出")
    except Exception as e:
        logger.error(f"\n错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
