from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from .llm import get_llm
from .state import AgentState
from ..schemas.plan import Plan

#获取LLM（复用单例）
llm = get_llm()

#1.创建结构化输出链
#with_structured_output 会强制LLM返回Plan类型的Json
structured_llm = llm.with_structured_output(Plan)

#2.设计提示词
PLANNER_PROMPT = """
你是一位资深项目规划专家。你的任务是将用户的复杂问题拆解为可执行的任务步骤。

用户问题：{question}

请遵循以下原则制定计划：
1.每个步骤必须有明确的执行主体（research/ writer/ reviewer）
2.步骤之间若有依赖关系，请在depends_on 中明确指出。
3.步骤数量控制在2~5步，不要过度拆解。
4.最后输出你的规划思路（rationale）。
5.特殊规则（优先级最高）：如果问题过于简单（少于10个字），只生成一个步骤，该步骤的 agent_type 为 "writer",且depends_on 为空数组。此时无需遵循第3条的数量限制

请严格按照Plan Schema输出。
"""

async def planner_node(state: AgentState) -> dict:
    """
    Planner节点：根据用户输入生成任务计划。
    """
    #1.从状态中提取用户消息（取最后一条HumanMessage）
    messages = state.get("messages", [])
    user_query = ""
    for msg in reversed(messages):   #reversed()反向遍历messages列表（读取最新消息）
        if isinstance(msg, HumanMessage):  #判断当前消息对象是否是HumanMessage类型，如果是则继续执行代码
            user_query = msg.content
            break

    if not user_query:
        #防御性编程：如果没有用户消息，抛出异常或返回默认计划
        return {"plan": Plan(steps=[], rationale="No user query provided")}

    prompt = ChatPromptTemplate.from_messages([
        #ChatPromptTemplate:用于生成messages的模版
        ("system", PLANNER_PROMPT),
        ("user", "{question}")
    ])

    chain =prompt | structured_llm
    plan = await chain.ainvoke({"question": user_query})

    #3.返回更新（只更新plan 和重置当前步骤索引）
    return{
        "plan": plan,
        "current_step_index": 0  #从头开始执行
    }