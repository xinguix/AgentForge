from langchain_core.messages import HumanMessage, SystemMessage
from .llm import get_llm, TokenUsageHandler
from .state import AgentState
from ..schemas.plan import PlanStep
from ..core.database import AsyncSessionLocal
from ..services.trace_service import TraceService
import time
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
    start_time = time.time()
    task_id = state.get("task_id", "unknown")

    # 1.获取用户原始问题（从messages 中提取）
    messages = state.get("messages", [])
    user_query = ""
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == "human":
            user_query = msg.content
            break

    input_data = {
        "user_query": user_query[:200],
        "has_messages": bool(messages)
    }

    try:
        # 2.获取当前步骤和中间结果
        plan = state.get("plan")
        current_idx = state.get("current_step_index", 0)

        if not plan or current_idx >= len(plan.steps):
            output_data = {"decision": "pass", "reason": "没有更多步骤，直接跳过"}
            async with AsyncSessionLocal() as db:
                await TraceService.record_run(
                    db=db,
                    task_id=task_id,
                    node_name="reviewer",
                    node_type="agent",
                    input_data=input_data,
                    output_data=output_data,
                    latency_ms=(time.time() - start_time) * 1000,
                    token_used=0,
                    status="success"
                )
            return {"review_status": "pass"}

        current_step = plan.steps[current_idx]
        input_data["step_id"] = current_step.step_id
        input_data["step_description"] = current_step.description

        intermediate = state.get("intermediate_steps", [])

        # 3.整理本次研究的结果（只取当前步骤的搜索结果）
        # 因为intermediate_steps 是累积的，我们只取最后一条
        last_result = intermediate[-1] if intermediate else {}
        research_summary = last_result.get("search_result", "无搜索结果")
        input_data["research_summary_preview"] = research_summary[:300]

        # 4.如果搜索结果是错误信息，直接判fail(防御性编程)
        if "搜索失败" in research_summary or "无搜索结果" in research_summary:
            review_status = "fail"
            retry_count = state.get("retry_count", 0) + 1
            output_data = {"decision": review_status, "retry_count": retry_count}
            async with AsyncSessionLocal() as db:
                await TraceService.record_run(
                    db=db,
                    task_id=task_id,
                    node_name="reviewer",
                    node_type="agent",
                    input_data=input_data,
                    output_data=output_data,
                    latency_ms=(time.time() - start_time) * 1000,
                    token_used=0,
                    status="success"
                )
            return {
                "review_status": review_status,
                "retry_count": retry_count,
                "current_step_index": current_idx - 1
            }

        elif len(research_summary.strip()) < 50:
            review_status = "retry"
            retry_count = state.get("retry_count", 0) + 1
            output_data = {"decision": review_status, "retry_count": retry_count}
            async with AsyncSessionLocal() as db:
                await TraceService.record_run(
                    db=db,
                    task_id=task_id,
                    node_name="reviewer",
                    node_type="agent",
                    input_data=input_data,
                    output_data=output_data,
                    latency_ms=(time.time() - start_time) * 1000,
                    token_used=0,
                    status="success"
                )
            return {
                "review_status": review_status,
                "retry_count": retry_count,
                "current_step_index": current_idx - 1
            }

        # 5.调用LLM进行智能审查（结构化判断）
        prompt = REVIEWER_PROMPT.format(
            user_query=user_query,
            research_summary=research_summary[:1000]
        )

        usage_handler = TokenUsageHandler()
        response = await llm.ainvoke([HumanMessage(content=prompt)], config={"callbacks": [usage_handler]})
        decision = response.content.strip().lower()

        # 6.解决决策（容错处理）
        if "pass" in decision:
            review_status = "pass"
        elif "retry" in decision:
            review_status = "retry"
        else:
            review_status = "fail"

        output_data = {
            "decision": review_status,
            "raw_llm_response": decision,
            "retry_count": state.get("retry_count", 0) + 1 if review_status in ("fail", "retry") else 0
        }

        # 记录成功轨迹
        async with AsyncSessionLocal() as db:
            await TraceService.record_run(
                db=db,
                task_id=task_id,
                node_name="reviewer",
                node_type="agent",
                input_data=input_data,
                output_data=output_data,
                latency_ms=(time.time() - start_time) * 1000,
                token_used=usage_handler.total_tokens,
                status="success"
            )

        return {
            "review_status": review_status,
            "retry_count": output_data["retry_count"],
            "current_step_index": current_idx - 1 if review_status in ("fail", "retry") else current_idx
        }

    except Exception as e:
        # 记录失败轨迹
        async with AsyncSessionLocal() as db:
            await TraceService.record_run(
                db=db,
                task_id=task_id,
                node_name="reviewer",
                node_type="agent",
                input_data=input_data,
                latency_ms=(time.time() - start_time) * 1000,
                status="error",
                error=str(e)
            )
        raise