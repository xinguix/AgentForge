from typing import List, Dict, Optional, Any, Annotated, Literal
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import operator

from ..schemas.plan import Plan


class AgentState(TypedDict):
    """LangGraph的全局状态"""
    #Annotated[list, operator.add]表示这个字段是累加的
    #多个节点返回的messages会自动合并（append）,而不是覆盖
    messages: Annotated[List[BaseMessage], operator.add]
    #Annotated:类型的“附加便签纸”：Annotated[类型，额外元数据]，不改变原有的类型，只是给这个类型“贴上一张附加信息的标签”

    #当前任务ID(第二周做多任务追踪时很有用
    task_id: Optional[str]

    #中间思考过程
    intermediate_steps: Annotated[Optional[List[Dict[str, Any]]], operator.add]

    #当前执行计划（整个plan对象）
    plan: Optional[Plan]

    #当前执行到第几步（从0开始）
    current_step_index: int

    #审查结果（pass/fail/retry）  #retry：重试
    review_status: Optional[Literal["pass", "fail", "retry"]]
    #literal:只允许返回括号里的内容（三选一）

    #当前步骤的重试次数（防止无限循环）
    retry_count: int

    #最终答案（Writer节点写入，供前端展示）
    final_answer: Optional[str]