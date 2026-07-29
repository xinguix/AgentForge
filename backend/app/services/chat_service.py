from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from ..core.config import settings
from ..core.llm import  get_llm
from ..schemas.chat import  ChatRequest

class ChatService:
    @staticmethod
    async def generate_response(request: ChatRequest) -> dict:
        """处理用户消息，返回AI回答和token信息"""

        #1.获取单例LLM
        llm = get_llm()

        #2.定义Prompt Template(这是“提示词工程根基”)
        #如果前端传了system_prompt 就用，否则就用默认的严谨AI角色。
        system_template = request.system_prompt or "你是一个专业、严谨的AI助手，请准确回答用户的问题。"

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("user","{input}")
        ])

        #3.构建LCET链
        #这种写法让代码极其简洁且可扩展
        chain = (
            {"input": RunnablePassthrough()}  #传递用户输入(原封不动)
            | prompt
            | llm
            | StrOutputParser()
        )
        answer = await chain.ainvoke({"input": request.message})

        return {
            "answer": answer,
            "model": settings.default_model
        }