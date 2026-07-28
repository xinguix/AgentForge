from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from .config import settings

#1.创建异步引擎（连接池）
engine = create_async_engine(
    settings.database_url,
    echo=True,  #开发时打印sql语句，方便调试，上线关掉
    pool_size=10,  #连接池大小（工程标配）
    max_overflow=20
)

#2.创建会话工厂（每次请求从这里拿session）
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  #提交后不过期对象，保持关联
)

#3.定义Base(所有ORM模型的爹)
Base = declarative_base()

#4.依赖注入函数（用于FastAPI路由里获取session）
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session