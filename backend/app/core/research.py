from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from .state import AgentState
from ..services.vector_service import VectorService
from ..tools.search_tool import web_search
from ..schemas.plan import PlanStep
import json

async def research_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Research Agent:执行当前步骤的搜索任务
    :return: intermediate_steps 追加一条搜索记录，current_step_index推进1
    """
    db = config.get("configurable", {}).get("db")
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

    search_result = await hybrid_search(query, db)
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

async def hybrid_search(query: str, db: AsyncSession, user_id: str="default") -> str:
    """
    混合检索：根据query内容决定检索策略，返回整合后的文本摘要
    """
    #internal:内部的
    internal_keywords = ["内部", "公司", "文档", "资料", "文件", "根据", "参考"]

    #1.判断是否需要内部检索
    need_internal = any(kw in query for kw in internal_keywords)

    #2.并行执行检索
    results = []
    if need_internal:
        #只做内部检查（如果明确指定了内部，就不做联网，更精准）
        internal_chunks = await VectorService.search_similar(db, query, user_id, top_k=3)
        if internal_chunks:
            results.append("【内部知识库】")
            results.extend(f"- {chunk}" for chunk in internal_chunks)
    else:
        #通用问题：同时执行联网+内部检索，互为补充
        #注意：并发执行，节省时间
        import asyncio
        web_task = web_search(query, max_results=2)
        internal_task = VectorService.search_similar(db, query, user_id, top_k=2)
        web_result, internal_chunks = await asyncio.gather(web_task, internal_task)

        if web_result and not web_result.startswith("搜索失败"):
            results.append("【互联网搜索结果】")
            results.append(web_result)
        if internal_chunks:
            results.append("【企业内部知识库】")
            results.extend(f"- {chunk}" for chunk in internal_chunks)

    if not results:
        return "未找到相关信息，请检查网络或上传更多文档。"

    return "\n\n".join(results)