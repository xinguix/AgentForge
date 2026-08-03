import logging

from langchain_core.messages import HumanMessage, AIMessage ,SystemMessage
from langgraph.graph import StateGraph, START, END
from typing import Literal

from .reviewer import review_node
from .state import AgentState
from .llm import get_llm
from .writer import writer_node
from ..core.config import settings
from .planner import planner_node
from .research import research_node

logger = logging.getLogger(__name__)
#初始化LLM(复用单例)
llm = get_llm()
MAX_RETRIES = 2

#1.节点1：Agent调用
async def agent_node(state: AgentState) -> dict:
    """
    核心Agnet节点：接受当前messages,调用LLM,返回新的AIMessage
    返回值会通过reducer(operator.add)自动追加到state['messages']末尾
    """
    raw_messages = state.get("messages",[])
    logger.info(f"DEBUG: raw_messages = {raw_messages}")
    #1.从状态中取出所有历史消息
    flat_messages = []
    for m in raw_messages:
       if isinstance(m, list):
           flat_messages.extend(m)
       else:
           flat_messages.append(m)
    logger.debug(f"展平后消息列表 = {flat_messages}")
    #2.如果没有系统消息，加一个默认的（这是防御性编程）

    if not any(isinstance(m, SystemMessage) for m in flat_messages):
        flat_messages = [SystemMessage(content="你是一个专业、严谨的AI助手，请准确回答用户的问题。")] + flat_messages

    #3.异步调用LLM（注意：这里传入的是BaseMessage列表，Langchain自动识别）
    try:
        response = await llm.ainvoke(flat_messages)
    except Exception as e:
        logger.error(f"LLM调用失败：{e}")
        raise

    #4.返回更新（只返回新增的AI消息，LangGraph自动append）
    return {"messages": [response]}

#节点二：路由决策
def should_continue(state: AgentState) -> Literal["research", "reviewer", "writer", END]:
    """
    条件边：决定下一步去哪里
    条件路由：如果还有Research步骤未执行，继续走research 节点;
    否则结束。
    """
    plan = state.get("plan")
    if not plan:
        return END

    current_idx = state.get("current_step_index", 0)
    steps = plan.steps

    if current_idx >= len(steps):
        return "writer"

    current_step = steps[current_idx]

    if current_step.agent_type == "research":
        retry_count = state.get("retry_count", 0)
        if retry_count >= MAX_RETRIES:
            return "writer"
        return "research"
    elif current_step.agent_type == "reviewer":
        return "reviewer"
    else:
        return "research"

def route_after_reviewer(state: AgentState) -> Literal["research", "writer"]:
    """
    Reviewer: 执行后的条件边：通过则进入writer(生成报告)，不通过则回到research 重试
    """
    status = state.get("review_status", "pass")
    retry_count = state.get("retry_count", 0)

    if status == "pass":
        #需要重试，回到research节点
        #注意：current_step_index不变，所以会执行同一个步骤
        return "research"
    elif retry_count < MAX_RETRIES:
        return "research"
    else:
        #通过，或者重试次数用尽，进入writer
        return "writer"

#构建图
def build_agent_graph():
    #1.创建状态图（指定状态类型）
    workflow = StateGraph(AgentState)
    #2.添加节点
    #workflow.add_node("agent",agent_node)#"agent"是这个节点名称
    workflow.add_node("planner", planner_node)
    workflow.add_node("research", research_node)
    workflow.add_node("reviewer", review_node)
    workflow.add_node("writer", writer_node)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "research")

    #条件边：research执行完后，决定是继续下一个research 还是结束
    workflow.add_conditional_edges(
        "research",
        should_continue,
        {
            "research": "research",
            #如果还有研究步骤，循环
            "reviewer": "reviewer",
            "writer": "writer",
            END: END   #否则结束
        }
    )

    #Reviewer的条件边（决定是重试还是结束）
    workflow.add_conditional_edges(
        "reviewer",
        route_after_reviewer,
        {
            "research": "research", #重试
            "writer": "writer"  #通过后进入Write
        }
    )

    workflow.add_edge("writer", END)

    #3.添加边
    """
    workflow.add_edge(START, "agent")  #从开始->agent
    workflow.add_conditional_edges(
        "agent",    #从agent节点出发
        should_continue,   #路由函数
        {
            END: END   #如果返回END,就结束
        }
    )"""

    #4.编译（编译后才能invole）
    graph = workflow.compile()
    return graph

#全局单例图（启动时编译一次，和LLM一样复用）
_compiled_graph = None

def get_graph():
    """获取编译好的图（单例）"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_agent_graph()
    return _compiled_graph