"""
规划模式示例
演示如何使用Agent的规划功能来执行复杂任务
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import SimpleAgent, LLMClient, setup_logger
from tools import ReadFileTool, WriteFileTool, ListDirectoryTool, PythonExecuteTool
from config import GlobalConfig


def create_planning_agent():
    """创建启用规划模式的Agent"""
    # 初始化配置
    global_config = GlobalConfig()
    llm_config = global_config.get_llm_config()

    # 创建LLM客户端
    llm_client = LLMClient(
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        base_url=llm_config.get("base_url"),
        temperature=llm_config.get("temperature", 0.7),
        max_tokens=llm_config.get("max_tokens", 2000)
    )

    # 创建工具集合
    tools = [
        ReadFileTool(),
        WriteFileTool(),
        ListDirectoryTool(),
        PythonExecuteTool()
    ]

    # 系统提示词
    system_prompt = """你是QuantManus,一个专业的AI助手。

你的能力:
1. 文件操作: 读取、写入、列举目录
2. Python代码执行: 可以运行Python代码进行数据分析和处理
3. 任务规划: 将复杂任务分解为可执行的步骤

工作原则:
- 先思考再行动,制定清晰的执行计划
- 每个步骤要有明确的目标
- 合理设置步骤之间的依赖关系
- 及时总结每个步骤的执行结果

注意事项:
- 文件路径使用绝对路径
- 执行Python代码前确保逻辑正确
- 遇到错误时要分析原因并尝试修复"""

    # 创建Agent (启用规划模式)
    agent = SimpleAgent(
        name="PlanningAgent",
        llm_client=llm_client,
        tools=tools,
        system_prompt=system_prompt,
        max_steps=global_config.get_max_steps(),
        use_memory_manager=True,
        enable_planning=True  # 启用规划模式
    )

    return agent


def example_1_data_analysis():
    """示例1: 数据分析任务"""
    print("\n" + "="*60)
    print("示例1: 数据分析任务 (规划模式)")
    print("="*60 + "\n")

    agent = create_planning_agent()

    task = """分析一组销售数据:
1. 生成100条模拟销售记录(包含日期、产品、销售额)
2. 将数据保存到CSV文件
3. 读取数据并进行统计分析(总销售额、平均值、最高/最低)
4. 生成分析报告并保存"""

    result = agent.run(task)
    print("\n最终结果:")
    print(result)


def example_2_file_processing():
    """示例2: 文件处理任务"""
    print("\n" + "="*60)
    print("示例2: 批量文件处理 (规划模式)")
    print("="*60 + "\n")

    agent = create_planning_agent()

    task = """处理文本文件:
1. 创建3个测试文本文件,每个文件包含不同内容
2. 读取所有文件的内容
3. 统计每个文件的字数和行数
4. 生成汇总报告"""

    result = agent.run(task)
    print("\n最终结果:")
    print(result)


def example_3_comparison():
    """示例3: 对比规划模式vs普通模式"""
    print("\n" + "="*60)
    print("示例3: 规划模式 vs 普通模式对比")
    print("="*60 + "\n")

    # 创建两个Agent
    global_config = GlobalConfig()
    llm_config = global_config.get_llm_config()

    llm_client = LLMClient(
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        base_url=llm_config.get("base_url"),
        temperature=llm_config.get("temperature", 0.7),
        max_tokens=llm_config.get("max_tokens", 2000)
    )

    tools = [
        ReadFileTool(),
        WriteFileTool(),
        PythonExecuteTool()
    ]

    system_prompt = "你是一个AI助手,帮助用户完成各种任务。"

    # Agent 1: 启用规划
    agent_with_planning = SimpleAgent(
        name="PlanningAgent",
        llm_client=llm_client,
        tools=tools,
        system_prompt=system_prompt,
        enable_planning=True
    )

    # Agent 2: 不启用规划
    agent_without_planning = SimpleAgent(
        name="NormalAgent",
        llm_client=llm_client,
        tools=tools,
        system_prompt=system_prompt,
        enable_planning=False
    )

    task = "创建一个Python脚本,计算1到100的所有偶数的和,并将结果保存到文件"

    print("\n【使用规划模式】")
    print("-" * 60)
    result1 = agent_with_planning.run(task)

    print("\n\n【使用普通模式】")
    print("-" * 60)
    result2 = agent_without_planning.run(task)

    print("\n\n对比总结:")
    print("规划模式: 先制定计划,分步执行,更有条理")
    print("普通模式: 直接执行,灵活但可能缺乏整体规划")


if __name__ == "__main__":
    # 设置日志
    setup_logger(level="INFO")

    # 运行示例
    print("\n选择要运行的示例:")
    print("1. 数据分析任务")
    print("2. 批量文件处理")
    print("3. 规划模式vs普通模式对比")
    print("0. 运行所有示例")

    choice = input("\n请输入选项 (0-3): ").strip()

    if choice == "1":
        example_1_data_analysis()
    elif choice == "2":
        example_2_file_processing()
    elif choice == "3":
        example_3_comparison()
    elif choice == "0":
        example_1_data_analysis()
        example_2_file_processing()
        example_3_comparison()
    else:
        print("无效选项")
