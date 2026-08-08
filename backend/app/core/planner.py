from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from .llm import get_llm, TokenUsageHandler
from .state import AgentState
from ..schemas.plan import Plan, PlanStep
from ..core.database import AsyncSessionLocal
from ..services.trace_service import TraceService
import time

#获取LLM（复用单例）
llm = get_llm()

#1.创建结构化输出链
#with_structured_output 会强制LLM返回Plan类型的Json
structured_llm = llm.with_structured_output(Plan, method="function_calling")

#2.设计提示词
PLANNER_PROMPT = """
你是一位资深项目规划专家。你的任务是将用户的复杂问题拆解为可执行的任务步骤。

用户问题：{question}

请遵循以下原则制定计划：
1.每个步骤必须有明确的执行主体（research/ writer/ reviewer）
2.步骤之间若有依赖关系，请在depends_on 中明确指出。
3.步骤数量控制在2~5步，不要过度拆解。
4.最后输出你的规划思路（rationale）。
5.特殊规则（优先级最高）：默认所有问题都需要研究（need_research 必须为 true）。仅当问题属于以下明确类型之一时，need_research 才可为 false：(a) 纯问候/闲聊（如"你好""谢谢"）；(b) 纯创意请求（如"讲个笑话"）；(c) 要求总结当前对话内容。注意：任何涉及具体项目、公司、产品、专有名词、技术栈、数据库、文档内容、数字的问题，你都不具备相关知识，必须将 need_research 设为 true 并通过检索获取答案，严禁凭训练知识猜测。
6. 除第5条描述的简单问题外（即need_research为 true时），涉及搜索调研的问题，步骤必须成对出现：每个 research 步骤后紧跟一个 reviewer 步骤（审查该步骤的搜索结果质量）。禁止生成 agent_type 为 "writer" 的步骤，最终报告由系统在全部步骤完成后自动生成,步骤描述应尽量保留用户原问题的关键词与问法,不要过度改写。

请严格按照Plan Schema输出。
"""

async def planner_node(state: AgentState) -> dict:
    """
    Planner节点：根据用户输入生成任务计划。
    """
    start_time = time.time()
    task_id = state.get("task_id", "unknown")
    #1.从状态中提取用户消息（取最后一条HumanMessage）
    messages = state.get("messages", [])
    user_query = ""
    for msg in reversed(messages):   #reversed()反向遍历messages列表（读取最新消息）
        if isinstance(msg, HumanMessage):  #判断当前消息对象是否是HumanMessage类型，如果是则继续执行代码
            user_query = msg.content
            break

    input_data = {"user_query": user_query[:200]}

    try:
        if not user_query:
            #防御性编程：如果没有用户消息，抛出异常或返回默认计划
            plan = Plan(steps=[], rationale="No user query provided")

        else:
            prompt = ChatPromptTemplate.from_messages([
                    #ChatPromptTemplate:用于生成messages的模版
                    ("system", PLANNER_PROMPT),
                    ("user", "{question}")
            ])

            usage_handler = TokenUsageHandler()
            chain =prompt | structured_llm
            plan = await chain.ainvoke({"question": user_query}, config={"callbacks": [usage_handler]})

            if not plan.need_research:
                #简单问题：强制单步writer计划，不信任LLM生成的步骤数量
                plan = Plan(
                    steps=[PlanStep(step_id=1, description=user_query, agent_type="writer", depends_on=[])],
                    rationale=plan.rationale,
                    need_research=False,
                )

        output_data = {
            "steps": [step.model_dump() for step in plan.steps],
            "rationale": plan.rationale[:200] if plan.rationale else ""
        }
        token_used = usage_handler.total_tokens

        async with AsyncSessionLocal() as db:
            await TraceService.record_run(
                db=db,
                task_id=task_id,
                node_name="planner",
                node_type="agent",
                input_data = input_data,
                output_data = output_data,
                latency_ms = (time.time() - start_time) * 1000,
                token_used = token_used,
                status = "success"

            )
    #3.返回更新（只更新plan 和重置当前步骤索引）
        return{
            "plan": plan,
            "current_step_index": 0  #从头开始执行
        }

    except Exception as e:
        #记录失败轨迹到数据库
        async with AsyncSessionLocal() as db:
            await TraceService.record_run(
                db=db,
                task_id=task_id,
                node_name="planner",
                node_type="agent",
                input_data = input_data,
                latency_ms = (time.time() - start_time) * 1000,
                status = "error",
                error=str(e)
            )
        raise
