from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from pyexpat.errors import messages

from ..core import graph
from ..core.config import settings
from ..core.graph import  get_graph
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

        initial_state = {"message": messages}

        #3.异步调用图（ainvoke）
        #注意：图会一直执行到触发END节点
        final_state = await graph.ainvoke(initial_state)

        #4.从最终状态中提取AI的答复
        # final_state["messages"]是所有消息的列表，最后一条是AI的回复
        ai_messages = [msg for msg in final_state.get("messages",[]) if isinstance(msg, AIMessage)]
        if not ai_messages:
            raise ValueError("AI没有返回任何消息")

        last_ai_message = ai_messages[-1]

        return {
            "answer": last_ai_message.content,
            "model": settinel
        }