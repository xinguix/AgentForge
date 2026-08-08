import asyncio
import json
import uuid

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from sqlalchemy import select

from ..core import graph
from ..core.config import settings
from ..core.graph import get_graph, agent_node
from ..core.llm import get_llm
from ..models import Task
from ..models.agent import Agent
from ..models.task import TaskStatus
from ..schemas.chat import  ChatRequest

class ChatService:
    @staticmethod
    async def generate_response(request: ChatRequest) -> dict:
        """处理用户消息，返回AI回答和token信息"""

        #1.获取编译好的图
        graph = await get_graph()


        #2.构造输入状态（LangGraph的初始状态）
        # 如果有system_prompt,封装成SystemMessage;否则只传HumanMessage
        messages = []
        if request.system_prompt:
            messages.append(SystemMessage(content=request.system_prompt))
        messages.append(HumanMessage(content=request.message))

        initial_state = {"messages": messages}
        print(f"DEBUG_CHAT: initial_state = {initial_state}")

        #3.异步调用图（ainvoke）
        #注意：图会一直执行到触发END节点
        final_state = await graph.ainvoke(initial_state)
        print("生成的计划", final_state.get("plan"))
        #4.从最终状态中提取AI的答复
        # final_state["messages"]是所有消息的列表，最后一条是AI的回复
        ai_messages = [msg for msg in final_state.get("messages",[]) if isinstance(msg, AIMessage)]
        if not ai_messages:
            raise ValueError("AI没有返回任何消息")

        last_ai_message = ai_messages[-1]

        return {
            "answer": last_ai_message.content,
            "model": settings.default_model
        }
    @staticmethod
    async def stream_response(request: ChatRequest, db):
        """
        SSE流式走图： thinking(节点)->token(writer)->done(task_id, answer)
        """
        try:
            llm = get_llm()
            graph = await get_graph()
            model_name = (
                    getattr(llm, "model_name", None) or
                    getattr(llm, "model", None) or
                    settings.default_model
            )
            #json.dumps:将字典转为JSON, ensure_ascii=False不转义非ASCII字符（支持中文）

            #2.Agent注入：传入agent_id就查库拿配置
            agent_config = None
            if request.agent_id:
                agent = (await db.execute(
                    select(Agent).where(Agent.id == request.agent_id, Agent.user_id == "default_user")
                )).scalar_one_or_none()
                if not agent:
                    raise ValueError(f"Agent 不存在：{request.agent_id}")
                agent_config = {"id": agent.id, "name": agent.name, "system_prompt": agent.system_prompt, "model": agent.model}

           #1.先建任务记录：拿到task_id ,节点内部会自动用state.task_id写trace
            new_task = Task(
                id=str(uuid.uuid4()),
                user_id="default_user",
                status=TaskStatus.RUNNING,
                input=request.message,
            )
            db.add(new_task)
            await db.commit()
            await db.refresh(new_task)
            yield f"data:{json.dumps({'event': 'start', 'model': model_name, 'task_id': new_task.id}, ensure_ascii=False)}\n\n"

            #2.构造初始状态（关键：task_id注入）
            messages = []
            if request.system_prompt:
                messages.append(SystemMessage(content=request.system_prompt))
            messages.append(HumanMessage(content=request.message))
            initial_state = {"messages": messages, "task_id": new_task.id, "agent_config": agent_config}

            #3.双模式流式： updates驱动节点指示器，messages驱动writer文字流
            active = None   #当前活跃节点
            answer_parts = []   #writer文字积累
            final_answer = ""   #updates里捕获的完整答案
            plan_data = None    #planner的plan，落库用

            #关键：使用astream而不是ainvoke
            # astream返回一个异步迭代器，每收到一个token就触发一次
            async for event in graph.astream(
                initial_state,
                stream_mode=["messages","updates"],
                config={"configurable": {"thread_id": new_task.id, "db": db}},
            ):
                mode, data =event
                if mode == "updates":
                    for node_name, update in data.items():
                        #节点切换：结束上一个，开始新的
                        if active and active != node_name:
                            yield f"data:{json.dumps({'event': 'thinking', 'node': active, 'status': 'end'}, ensure_ascii=False)}\n\n"
                        if node_name != active:
                            yield f"data:{json.dumps({'event': 'thinking', 'node': node_name, 'status': 'start'}, ensure_ascii=False)}\n\n"
                            active = node_name
                        #捕获writer的完整答案和planner的计划
                        if node_name == "writer" and update.get("final_answer"):
                            final_answer = update["final_answer"]
                        if node_name == "planner" and update.get("plan"):
                            plan_data = update["plan"]
                elif mode == "messages":
                    chunk, metadata = data
                    node = metadata.get("langgraph_node")
                #每个chunk是一个AIMessageChunk,包含content和可选的其他信息
                    content = getattr(chunk, "content", "")
                    if node == "writer" and content:
                        answer_parts.append(content)
                        #4.按照SSE协议格式输出（标准格式: data:{json}\n\n）
                        #这样前端EventSource API可以直接解析
                        yield f"data:{json.dumps({'event': 'token' ,'token': content}, ensure_ascii=False)}\n\n"
                        #\n\n:换行符，表示一条事件结束


            if active:
                yield f"data:{json.dumps({'event':'thinking', 'node': active, 'status': 'end'}, ensure_ascii=False)}\n\n"

            #4.落库：状态+输出+计划（writer在messages模式下不吐全量，用updates捕获的）
            new_task.status = TaskStatus.COMPLETED
            new_task.output = final_answer or "".join(answer_parts)
            if plan_data is not None:
                new_task.plan_data = plan_data.model_dump(mode="json") if hasattr(plan_data, "model_dump") else plan_data
            await db.commit()
                #5.发送结束标记（前端检测到[DONE]就关闭连接）
            yield f"data:{json.dumps({'event': 'done', 'task_id': new_task.id, 'answer': new_task.output}, ensure_ascii=False)}\n\n"
        except Exception as e:
            #失败也要落库+通知前端
            if "new_task" in locals():
                try:
                    new_task.status = TaskStatus.FAILED
                    new_task.error = str(e)
                    await db.commit()
                except Exception :
                    pass
            yield f"data:{json.dumps({'event': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"