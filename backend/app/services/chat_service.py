import asyncio
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage


from ..core import graph
from ..core.config import settings
from ..core.graph import  get_graph
from ..core.llm import get_llm
from ..schemas.chat import  ChatRequest

class ChatService:
    @staticmethod
    async def generate_response(request: ChatRequest) -> dict:
        """处理用户消息，返回AI回答和token信息"""

        #1.获取编译好的图
        graph = get_graph()


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
    async def stream_response(request: ChatRequest):
        """
        流式生成回答
        这是一个异步生成器（Async Generator）,每次yield一个token
        """
        try:
            llm = get_llm()
            messages = []
            if request.system_prompt:
                messages.append(SystemMessage(content=request.system_prompt))
            messages.append(HumanMessage(content=request.message))

            model_name = (
                getattr(llm, "model_name", None) or
                getattr(llm, "model", None) or
                settings.default_model
             )
            yield f"data:{json.dumps({'model': model_name, 'event': 'start'},ensure_ascii=False)}\n\n"
        #关键：使用astream而不是ainvoke
        # astream返回一个异步迭代器，每收到一个token就触发一次
            async for chunk in llm.astream(messages):
                #每个chunk是一个AIMessageChunk,包含content和可选的其他信息
                content = chunk.content
                if content:
                    #4.按照SSE协议格式输出（标准格式: data:{json}\n\n）
                    #这样前端EventSource API可以直接解析
                    yield f"data:{json.dumps({'token': content}, ensure_ascii=False)}\n\n"
                    #\n\n:换行符，表示一条事件结束

                #5.发送结束标记（前端检测到[DONE]就关闭连接）
            yield f"data:{json.dumps({'done': True})}\n\n"
        except asyncio.CancelledError:
            #客户端断开连接，立刻停止生成，节约API token
            print("客户断开流式连接，已停止生成")
            raise