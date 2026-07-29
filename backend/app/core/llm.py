from langchain_openai import ChatOpenAI
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