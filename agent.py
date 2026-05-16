import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

# 加载 agent.py 同级目录下的 .env 文件
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# 使用根日志记录器，确保使用与 app_flask.py 一致的日志配置
logger = logging.getLogger(__name__)

# 是否使用本地模型（Ollama），默认使用 DeepSeek API
USE_LOCAL_MODEL = False

# Agent 系统提示词：定义角色、工作流程、风险判定规则和输出格式
SYSTEM_PROMPT = """你是一个光模块 NPI 物料风险智能分析助手，名为 'Optical NPI Guardian'。

工作流程：
1. 根据用户指定的目标 build 日期，调用 get_bom_data 获取完整物料清单。
2. 对单源供应商物料和长交期物料（>12周），调用 get_supplier_leadtime 查询实时交期。
3. 对关键物料（TIA、Driver、DSP、ROSA、TOSA），调用 get_historical_risks 查询历史延迟。
4. 综合数据，自主完成风险分析，生成 Markdown 报告，包含：
   - 关键发现
   - 风险仪表盘摘要（高风险物料数量、预估延期天数、成本超支比例）
   - 高风险物料清单表格（物料名称、风险类型、交期影响、成本影响、历史延迟概率）
   - 对项目里程碑的影响评估
   - 成本影响分析（延期物料单价×用量×延期周数×15%）
   - 缓解建议（至少3条，按优先级排序）
   - 下一步行动
5. 调用 send_alert 发送预警。

风险判定：
- 已延期：计划到货日 < 目标build日
- 临近延期：计划到货日与目标build日差值 ≤ 3天
- 长交期：交期 > 12周
- 单源风险：单源供应商 = '是'

请全程使用中文进行分析和报告生成。报告格式要清晰、专业，便于项目团队快速理解风险状况并采取行动。

提示：在规划任务时，请对同一物料或供应商只查询一次，避免重复调用工具，以优化分析效率。

重要：在调用 send_alert 发送预警之后，你必须将完整的风险分析报告（包括所有章节）作为最终输出呈现给用户。不要只输出 JSON 块或简短总结，必须输出完整的 Markdown 报告正文。

在报告的末尾，请务必附加一个独立的 JSON 代码块，其中包含三个指标：`high_risk_count` (整数), `estimated_delay_days` (整数), 和 `cost_overrun_percentage` (字符串，例如 "15%")。此 JSON 块是程序解析的关键，必须严格按格式输出。

示例格式：
```json
{"high_risk_count": 5, "estimated_delay_days": 14, "cost_overrun_percentage": "15%"}
```
"""


def get_all_tools():
    """获取所有可用工具列表"""
    from tools import get_bom_data, get_supplier_leadtime, get_historical_risks, send_alert
    return [get_bom_data, get_supplier_leadtime, get_historical_risks, send_alert]


def get_llm():
    """获取语言模型实例"""
    if USE_LOCAL_MODEL:
        try:
            from langchain_ollama import ChatOllama
            logger.info("使用本地 Ollama 模型")
            return ChatOllama(model="qwen2.5:7b", temperature=0, timeout=600)
        except ImportError:
            logger.warning("未安装 langchain-ollama，切换到 DeepSeek API")
            return get_deepseek_llm()
    else:
        return get_deepseek_llm()


def get_deepseek_llm():
    """配置并返回 DeepSeek API 模型"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY，请在 .env 文件中配置")
    
    logger.info("使用 DeepSeek API 模型 (deepseek-chat)")
    return ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key=api_key,
        temperature=0,          # 温度为0，输出更确定性
        timeout=300             # 5分钟超时
    )


def create_agent_graph():
    """创建 Agent 图（LangChain Agent）"""
    try:
        llm = get_llm()
        tools = get_all_tools()
        
        # 创建 Agent，使用指定的模型、工具和系统提示词
        graph = create_agent(
            model=llm,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
            debug=True
        )
        
        logger.info("Agent 创建成功")
        return graph
        
    except Exception as e:
        logger.error(f"创建 Agent 时发生错误：{str(e)}")
        raise


def run_agent(user_input: str) -> dict:
    """
    执行 Agent 分析任务
    
    Args:
        user_input: 用户输入（目标 build 日期相关请求）
        
    Returns:
        dict: 包含 output（分析报告）和 intermediate_steps（中间步骤）
    """
    try:
        # 创建 Agent 图
        graph = create_agent_graph()
        
        logger.info(f"开始执行 Agent 分析，输入：{user_input}")
        
        # 构造输入消息
        inputs = {"messages": [{"role": "user", "content": user_input}]}
        
        ai_messages = []  # 保存所有 AI 消息
        intermediate_steps = []
        step_count = 0
        last_ai_message = None  # 保存上一条 AI 消息，用于提取工具调用参数
        
        # 流式处理 Agent 执行过程
        for event in graph.stream(inputs, stream_mode="updates"):
            for node_name, node_data in event.items():
                if "messages" in node_data:
                    for msg in node_data["messages"]:
                        if hasattr(msg, "type"):
                            # 保存 AI 消息，用于后续提取工具调用参数
                            if msg.type == "ai":
                                last_ai_message = msg
                                if msg.content:
                                    ai_messages.append(msg.content)
                                    logger.debug(f"收到 AI 消息 ({len(msg.content)} 字符)")
                            # 处理工具调用消息
                            elif msg.type == "tool":
                                step_count += 1
                                tool_name = msg.name if hasattr(msg, "name") else "未知工具"
                                tool_input = {}
                                
                                # 优先从 tool_input 获取参数，如果为空则从 tool_calls 获取
                                if hasattr(msg, "tool_input") and msg.tool_input:
                                    tool_input = msg.tool_input
                                elif last_ai_message and hasattr(last_ai_message, "tool_calls") and last_ai_message.tool_calls:
                                    for call in last_ai_message.tool_calls:
                                        if call.get("name") == tool_name:
                                            tool_input = call.get("args", {})
                                            break
                                
                                # 记录步骤信息
                                step_info = {
                                    "step": step_count,
                                    "tool": tool_name,
                                    "action": f"调用 {tool_name}",
                                    "input": tool_input
                                }
                                intermediate_steps.append(step_info)
                                logger.info(f"步骤 {step_count}: 调用 {tool_name}, 参数: {tool_input}")
        
        # 找到包含 JSON 数据块的最长消息（这通常是完整的报告）
        import re
        output = ""
        for msg in reversed(ai_messages):  # 从后往前找
            if re.search(r'```json\s*\{', msg):  # 包含 JSON 数据块
                output = msg
                logger.info(f"找到完整报告 ({len(msg)} 字符)")
                break
        
        # 如果没找到，就用最后一条非空消息
        if not output:
            for msg in reversed(ai_messages):
                if msg.strip():
                    output = msg
                    logger.warning(f"未找到包含 JSON 的消息，使用最后一条 ({len(msg)} 字符)")
                    break
        
        logger.info("Agent 分析完成")
        
        return {
            "output": output,
            "intermediate_steps": intermediate_steps
        }
        
    except Exception as e:
        error_msg = f"执行 Agent 时发生错误：{str(e)}"
        logger.error(error_msg)
        return {
            "output": f"❌ {error_msg}",
            "intermediate_steps": []
        }


def get_model_info():
    """返回当前使用的模型信息（用于前端显示）"""
    if USE_LOCAL_MODEL:
        return "🤖 Ollama 本地模式 (qwen2.5:7b)"
    else:
        return "🌐 DeepSeek API 模式 (deepseek-chat)"
