import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text

from .core.config import settings
from .core.database import engine, Base
from .core.redis_client import get_redis, close_redis
from .core.graph import get_graph
from .models import *
from .api.v1 import agents, chat, tasks, documents

#配置日志（PyCharm底部的Run窗口会显示这些彩色日志）
logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(levelname)s - %(message)s')
#配置了控制台输出级别（info）和格式（时间-级别-消息）
#info:一个比print更专业的输出工具，方便控制是否显示、输出到文件、以及区分严重程度
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    #启动前1.新建一个数据库
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"{settings.project_name}数据库检查/创建完成")

    #启动前预热Redis
    try:
        redis_client = await get_redis()
        await redis_client.ping()
        #ping（） :是redis提供的一个心跳检测命令，想redis发送"PING",如果服务器正常或者就恢复"PONG"
        logger.info("Redis 连接成功")
    except Exception as e:
        logger.error(f"Redis连接失败：{e}")

    logging.info("正在编译LangGraph工作流...")
    graph = get_graph()
    logging.info(f"LangGraph编译完成，节点数:{len(graph.nodes)}")

    yield  #服务开始运行
    #关闭后：释放Redis连接池
    await close_redis()
    logger.info("Redis连接已释放")

    #关闭后：释放数据库连接池
    await engine.dispose()
    logger.info(f"{settings.project_name}数据库连接已释放")

app = FastAPI(title=settings.project_name,lifespan=lifespan)
#挂载V1路由
app.include_router(agents.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(tasks.router,prefix="/api/v1")

app.include_router(documents.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return{"status":"ok","env": settings.env}