from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from .config import settings

#全局变量，懒加载
_llm_instance = None

def get_llm() -> ChatOpenAI:
    """获取全局唯一的LLM实例（单例模式）"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=settings.default_model,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=0.7,
            timeout=60,
            max_retries=2,
        )
    return _llm_instance

class TokenUsageHandler(BaseCallbackHandler):
    """按次累积LLM调用返回的token消耗，供节点记录到runs表"""

    def __init__(self) -> None:
        self.total_tokens = 0

    def on_llm_end(self, response, **kwargs) ->None:
        #** kwargs是Python函数定义中的可变关键字参数收集器，用于接收所有未命名的键值对，并以字典形式存储。
        usage = (response.llm_output or {}).get("token_usage") or {}
        self.total_tokens += usage.get("total_tokens", 0)