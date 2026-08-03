from langchain_core.messages import SystemMessage, HumanMessage
from .llm import get_llm
from .state import AgentState
import json

llm = get_llm()

WRITER_PROMPT = """
你是一位资深技术报告撰写专家。你的任务是根据“研究成果”，生成一份面向企业高管的、结构清晰地专业报告。

【用户原始问题】
{user_query}

【研究素材（来自Research Agent的搜索结果）】
{research_materials}

【撰写要求】
1. 结构必须包含： **摘要**、 **核心发现**、 **详细分析** 、**结论与建议** 四个部分。
2. 语言风格：专业、严谨、客观，避免口语化。
3. 如果素材不足，请明确指出“基于现有资料，以下信息尚不完整”，而不是胡编乱造。
4. 在引用具体数据或案例时，注明来源（如“根据搜索结果显示”）

请直接输出 Markdown 格式的报告，不要有任何额外的开场白或结束语。
"""

async def writer_node(state: AgentState) -> dict:
    """
    :param state: 将研究结果整合成最终报告。
    """
    #1.提取用户问题
    messages = state.get("messages", [])
    user_query =""
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == "human":
            user_query = msg.content
            break

    #2.提取所有研究步骤的中间结果
    intermediate = state.get("intermediate_steps", [])
    if not intermediate:
        #如果没有研究成果，直接生成一个占位回答
        fallback_answer = "抱歉，由于未能获取到足够的研究资料，暂时无法生成完整报告。请检查搜索配置或稍后重试。"
        return {"final_answer": fallback_answer}

    #3.格式化研究素材（让LLM容易理解）
    research_materials = ""
    for idx, step in enumerate(intermediate):   #往列表intermediate里面累加结果
        if "search_result" in step:
            step_desc = step.get("step_description", f"步骤{idx+1}")  #python下标从0开始的，累加1才能从1开始
            result = step.get("search_result", "无结果")
            research_materials += f"### 研究项{idx+1}:{step_desc}\n{result}\n\n"

    #4.调用LLM生成报告
    prompt = WRITER_PROMPT.format(
        user_query=user_query,
        research_materials=research_materials[:3000]  #截断防止超token
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    final_answer = response.content.strip()

    return {"final_answer": final_answer}