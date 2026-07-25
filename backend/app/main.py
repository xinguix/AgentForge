import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .core.config import settings

#配置日志（PyCharm底部的Run窗口会显示这些彩色日志）
logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(levelname)s - %(message)s')
#配置了控制台输出级别（info）和格式（时间-级别-消息）
#info:一个比print更专业的输出工具，方便控制是否显示、输出到文件、以及区分严重程度
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    #启动前（将来这里放Redis、DB连接池）
    logger.info(f"{settings.project_name}正在启动（环境：{settings.env}）...")
    yield
    #关闭后
    logger.info(f"{settings.project_name}正在优雅关闭...")

app = FastAPI(title=settings.project_name,lifespan=lifespan)

@app.get("/health")
async def health_check():
    return{"status":"ok","env": settings.env}