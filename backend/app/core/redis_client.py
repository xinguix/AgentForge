import redis.asyncio as redis
from .config import settings

_redis_client = None
#client:客户

async def get_redis():
    """获取Redis客户端单例（懒加载）"""
    global _redis_client
    #在函数内部申明要修改外部的全局变量_redis_client，不写的话python会认为在函数内部新建了一个局部变量
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            #按照utf-8的转换规则自动把字节转换成字符串
            max_connections=10
        )
    return _redis_client

async def close_redis():
    """关闭Redis连接（在lifespan关闭时调用）"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
