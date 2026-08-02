from langchain_community.tools.tavily_search import TavilySearchResults
import asyncio

#初始化搜索工具（单例，复用连接）
_search_instance = None

def get_search_tool():
    """获取搜索工具单例"""
    global _search_instance
    if _search_instance is None:
        _search_instance = TavilySearchResults(max_results=3)
    return _search_instance

async def web_search(query: str, max_results: int = 3) -> str:
    """
    异步执行web搜索（封装异步调用）
    Args:
        query:搜索关键词
        max_results:最大结果数（DuckDuckGo 默认返回摘要，我们用提示词限制）
    return:
        搜索结果的文本摘要
    """
    tool = get_search_tool()

    #DuckDuckGo的 arun方法原生支持异步
    #但为了避免阻塞事件循环，我们直接用await
    try:
        results = await tool.ainvoke(query)
        if not results:
            return "未搜索到相关内容"
        parts = []
        for i, item in enumerate(results, 1):
            title = item.get("title", "")
            content = item.get("content", "")
            url = item.get("url", "")
            parts.append(f"{i}. {title}\n{content}\n来源：{url}")
        return "\n\n".join(parts)
    except Exception as e:
        return f"搜索失败：{str(e)}。请检查网络或稍后重试。"