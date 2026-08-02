from langchain_core.messages import HumanMessage,SystemMessage
from .llm import get_llm
from .state import AgentState
from ..schemas.plan import PlanStep
import json

llm = get_llm()

REVIEWER_PROMPT = """
你是一位严格的质量审核专家。你的任务是评估“研究成果”是否足以支撑回答用户的问题。

【用户原始问题】
{user_query}

【已执行的研究步骤及结果】
{research_summary}

请根据以下标准判断：
1. 如果搜索结果为空或明显不相关 -> 判定为 fail
2. 如果搜索结果包含关键信息（事实、数据、案例） -> 判定为pass
3. 如果搜索结果部分相关但不够充分 -> 判定为 retry (需要重新搜索)

请只回复一个单词： pass / fail / retry
不要解释，不要加标点。
"""

async def review_node(state: AgentState) -> dict:
    """
    :param state:检查研究质量，决定下一步
    :return: review_status 和可能的重试索引。
    """
    #1.获取用户原始问题（从messages 中提取）
    messages = state.get("messages", [])
    user_query=""
    for msg in reversed(messages):  #将消息倒序遍历
        if hasattr(msg, 'type') and msg.type == "human":
            #hasattr:检查一个对象是否拥有指定的属性名
            #检查msg里面是否有一个名为type的属性，如果有，那他的值就等于字符串human
            user_query = msg.content
            break

    #2.获取当前步骤和中间结果
    plan = state.get("plan")
    current_idx = state.get("current_step_index", 0)
    if not plan or current_idx >= len(plan.steps):
        return {"review_status": "pass"}  #没有更多步骤，直接跳过

    current_step = plan.steps[current_idx]
    intermediate = state.get("intermediate_steps", [])

    #3.整理本次研究的结果（只取当前步骤的搜索结果）
    #因为intermediate_steps 是累积的，我们只取最后一条
    last_result = intermediate[-1] if intermediate else {}
    research_summary = last_result.get("search_result", "无搜索结果")

    #4.如果搜索结果是错误信息，直接判fail(防御性编程)
    if "搜索失败" in research_summary or "无搜索结果" in research_summary:
        return {"review_status": "fail", "retry_count": state.get("retry_count", 0) + 1}
    elif len(research_summary.strip()) < 50:
        return {"review_status": "retry", "retry_count": state.get("retry_count", 0) + 1}

    #5.调用LLM进行智能审查（结构化判断）
    prompt = REVIEWER_PROMPT.format(
        user_query=user_query,
        research_summary=research_summary[:1000]  #截断防止超token
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    decision = response.content.strip().lower()
    # .lower: 全部转换成小写  .strip:去除字符串首尾的空白字符

    #6.解决决策（容错处理）
    if "pass" in decision:
        review_status = "pass"
    elif "retry" in decision:
        review_status = "retry"
    else:
        review_status = "fail"

    return {
        "review_status": review_status,
        "retry_count": state.get("retry_count", 0) + 1 if review_status == "retry" else state.get("retry_count", 0)
        #三元表达式： 结果A if 条件 else 结果B。条件成立返回结果A,不满足返回B
    }