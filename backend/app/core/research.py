import asyncio
import time

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from .database import AsyncSessionLocal
from .state import AgentState
from ..services.trace_service import TraceService
from ..services.vector_service import VectorService
from ..tools.search_tool import web_search
from ..schemas.plan import PlanStep
import json

async def research_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Research Agent:执行当前步骤的搜索任务
    :return: intermediate_steps 追加一条搜索记录，current_step_index推进1
    """
    start_time = time.time()
    task_id = state.get("task_id", "unknown")

    db = config.get("configurable", {}).get("db")
    #读取当前计划
    plan = state.get("plan")
    input_data = {"plan_exists": plan is not None}
    try:
        if not plan:
            output_data = {"error": "没有可执行的计划"}
            raise ValueError("没有可执行的计划")

        current_idx = state.get("current_step_index", 0)
        steps = plan.steps

        #检查是否所有步骤都执行完了
        if current_idx >= len(steps):
            output_data = {"info": "所有步骤已执行完毕"}
            async with AsyncSessionLocal() as db_session:
                await TraceService.record_run(
                    db=db_session,
                    task_id=task_id,
                    node_name="research",
                    node_type="tool",
                    input_data=input_data,
                    output_data=output_data,
                    latency_ms=(time.time() - start_time) * 1000,
                    token_used=0,
                    status="success"
                )
            return {"intermediate_steps": [{"info": "所有步骤已执行完毕"}]}

        #获取当前步骤
        current_step: PlanStep = steps[current_idx]
        input_data["step_id"] = current_step.step_id
        input_data["step_description"] = current_step.description

        #防御性检查，如果当前步骤不是research类型，跳过（但保留接口）
        if current_step.agent_type != "research":
            output_data = {"skipped": "当前步骤不是research类型，直接跳过"}
            async with AsyncSessionLocal() as db_session:
                await TraceService.record_run(
                    db=db_session,
                    task_id=task_id,
                    node_name="research",
                    node_type="tool",
                    input_data=input_data,
                    output_data=output_data,
                    latency_ms=(time.time() - start_time) * 1000,
                    token_used=0,
                    status="success"
                )
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

        output_data = {
            "step_record": step_record,
            "search_result_preview": search_result[:500]
        }
        # 记录成功轨迹
        async with AsyncSessionLocal() as db_session:
            await TraceService.record_run(
                db=db_session,
                task_id=task_id,
                node_name="research",
                node_type="tool",
                input_data=input_data,
                output_data=output_data,
                latency_ms=(time.time() - start_time) * 1000,
                token_used=0,
                status="success"
            )

        return {
            "intermediate_steps": [step_record],
            "current_step_index": current_idx + 1
        }

    except Exception as e:
        # 记录失败轨迹
        async with AsyncSessionLocal() as db_session:
            await TraceService.record_run(
                db=db_session,
                task_id=task_id,
                node_name="research",
                node_type="tool",
                input_data=input_data,
                latency_ms=(time.time() - start_time) * 1000,
                status="error",
                error=str(e)
            )
        raise

async def hybrid_search(query: str, db: AsyncSession, user_id: str="default") -> str:
    """
    混合检索：根据query内容决定检索策略，返回整合后的文本摘要
    """
    #永远双查：始终并行执行联网+内部检索，返回整合后的文本摘要
    results =[]
    web_task = web_search(query, max_results=2)
    internal_task = VectorService.search_similar(db, query, user_id, top_k=5)
    web_result, internal_chunks = await asyncio.gather(web_task, internal_task)

    if internal_chunks:
        results.append("【企业内部知识库】")
        results.extend(f"- {chunk}" for chunk in internal_chunks)

    if web_result and not web_result.startswith("搜索失败"):
        results.append("【互联网搜索结果】")
        results.append(web_result[:2000])

    if not results:
        return "未找到相关信息，请检查网路或上传更多文档。"

    return "\n".join(results)