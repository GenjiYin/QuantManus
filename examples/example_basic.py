"""
基础示例:演示如何创建和使用Agent
"""
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import SimpleAgent, LLMClient
from tools import ReadFileTool, WriteFileTool, PythonExecuteTool


def example_1_simple_task():
    """
    示例1:执行简单的Python计算任务
    """
    print("\n" + "="*60)
    print("示例1: 简单的Python计算任务")
    print("="*60)

    # 创建LLM客户端
    llm_client = LLMClient(
        model="gpt-4o",
        api_key="your-api-key",  # 请替换为真实的API密钥
        base_url="https://api.openai.com/v1"
    )

    # 创建Agent
    agent = SimpleAgent(
        name="计算助手",
        llm_client=llm_client,
        tools=[PythonExecuteTool()],
        system_prompt="你是一个计算助手,可以执行Python代码来完成计算任务。",
        max_steps=5
    )

    # 执行任务
    result = agent.run("计算斐波那契数列的前10项")

    print(f"\n结果: {result}")


def example_2_file_operations():
    """
    示例2:文件操作任务
    """
    print("\n" + "="*60)
    print("示例2: 文件操作任务")
    print("="*60)

    # 创建LLM客户端
    llm_client = LLMClient(
        model="gpt-4o",
        api_key="your-api-key",  # 请替换为真实的API密钥
        base_url="https://api.openai.com/v1"
    )

    # 创建Agent
    agent = SimpleAgent(
        name="文件助手",
        llm_client=llm_client,
        tools=[ReadFileTool(), WriteFileTool()],
        system_prompt="你是一个文件操作助手,可以读写文件。",
        max_steps=10
    )

    # 执行任务
    result = agent.run("创建一个名为test.txt的文件,内容是'Hello, QuantManus!'")

    print(f"\n结果: {result}")


def example_3_combined_tools():
    """
    示例3:组合使用多个工具
    """
    print("\n" + "="*60)
    print("示例3: 组合使用多个工具")
    print("="*60)

    # 创建LLM客户端
    llm_client = LLMClient(
        model="gpt-4o",
        api_key="your-api-key",  # 请替换为真实的API密钥
        base_url="https://api.openai.com/v1"
    )

    # 创建Agent,包含多种工具
    agent = SimpleAgent(
        name="全能助手",
        llm_client=llm_client,
        tools=[
            ReadFileTool(),
            WriteFileTool(),
            PythonExecuteTool()
        ],
        system_prompt="""你是一个全能助手,可以执行多种任务:
        1. 读写文件
        2. 执行Python代码
        根据用户需求灵活使用工具。""",
        max_steps=15
    )

    # 执行复杂任务
    result = agent.run("""
    请完成以下任务:
    1. 用Python生成一个包含1到10的平方数的列表
    2. 将结果保存到squares.txt文件中
    """)

    print(f"\n结果: {result}")


if __name__ == "__main__":
    print("QuantManus - 使用示例")
    print("="*60)
    print("注意: 运行这些示例前,请先在代码中填入你的API密钥")
    print("="*60)

    # 选择要运行的示例
    print("\n请选择示例:")
    print("1. 简单的Python计算任务")
    print("2. 文件操作任务")
    print("3. 组合使用多个工具")

    choice = input("\n输入选项(1/2/3): ")

    if choice == "1":
        example_1_simple_task()
    elif choice == "2":
        example_2_file_operations()
    elif choice == "3":
        example_3_combined_tools()
    else:
        print("无效的选项")
