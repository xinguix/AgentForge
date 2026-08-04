from langchain_core.messages import SystemMessage, HumanMessage
from .llm import get_llm
from .state import AgentState
import json
from datetime import datetime

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
5. 如果研究素材不足（少于 2 个有效搜索结果），不要强行编造，而是直接回复：‘抱歉，目前公开资料有限，无法生成完整的分析报告。建议您提供更多具体方向或开放相关数据权限。
6. 今天是{current_date},报告日期请使用今天。

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
    #筛选出真正有搜索结果的step
    valid_results = [s for s in intermediate if s.get("search_result")]

    if not intermediate or len(valid_results) < 2:
        #分支1： 先看plan里面有没有research步骤
        plan = state.get("plan")
        has_research_step = False
        if plan and plan.steps:
            has_research_step = any(
                step.agent_type == "research" for step in plan.steps
            )
        if not has_research_step:
            #简单问题：预期不搜索，这里直接调用大模型回答
            response = await llm.ainvoke([
                SystemMessage(content="你是一个知识渊博的AI助手，请直接、准确、简洁地回答用户的问题。"),
                HumanMessage(content=user_query)
            ])
            return {"final_answer": response.content.strip()}
        else:
            #复杂问题但是搜索失败：如实告知，不硬答、不浪费token
            fallback_answer = "抱歉，由于未能获取到足够的研究资料，暂时无法生成完整报告。请检查搜索配置或稍后重试。"
            return {"final_answer": fallback_answer}

    #3.格式化研究素材（让LLM容易理解）
    research_materials = ""
    for idx, step in enumerate(intermediate):   #往列表intermediate里面累加结果
        if "search_result" in step:
            step_desc = step.get("step_description", f"步骤{idx+1}")  #python下标从0开始的，累加1才能从1开始
            result = step.get("search_result", "无结果")
            research_materials += f"### 研究项{idx+1}:{step_desc}\n{result}\n\n"

    # 4.调用LLM生成报告
    current_date = datetime.now().strftime("%Y-%m-%d")
    prompt = WRITER_PROMPT.format(
        user_query=user_query,
        research_materials=research_materials[:3000],
        current_date=current_date
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    final_answer = response.content.strip()

    return {"final_answer": final_answer}