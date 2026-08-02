from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from .state import AgentState
from ..tools.search_tool import web_search
from ..schemas.plan import PlanStep
import json

async def research_node(state: AgentState) -> dict:
    """
    Research Agent:执行当前步骤的搜索任务
    :return: intermediate_steps 追加一条搜索记录，current_step_index推进1
    """
    #读取当前计划
    plan = state.get("plan")
    if not plan:
        return {"intermediate_steps": [{"error": "没有可执行的计划"}]}

    current_idx = state.get("current_step_index", 0)
    steps = plan.steps

    #检查是否所有步骤都执行完了
    if current_idx >= len(steps):
        return {"intermediate_steps": [{"info": "所有步骤已执行完毕"}]}

    #获取当前步骤
    current_step: PlanStep = steps[current_idx]

    #防御性检查，如果当前步骤不是research类型，跳过（但保留接口）
    if current_step.agent_type != "research":
        #不是研究任务，直接推进（留白给writer处理）
        return {"current_step_index": current_idx +1}

    #执行搜索
    query = current_step.description
    print(f"Research Agent 正在搜索: {query}")

    if "天气" in query:
        search_result = "今天天气晴朗，适合户外活动"
        print("天气关键词命中，使用模拟结果（降级策略）")
    else:
        search_result = await web_search(query, max_results=3)

    #格式化结果为结构化记录（方便Trace 可视化）
    step_record = {
        "step_id": current_step.step_id,
        "step_description": query,
        "search_result": search_result,
        "status": "completed"
    }

    return {
        "intermediate_steps": [step_record],
        "current_step_index": current_idx + 1
    }