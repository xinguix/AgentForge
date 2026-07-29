from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
import uuid

from ..models.agent import  Agent
from ..schemas.agent import AgentCreate, AgentUpdate

class AgentService:
    @staticmethod
    async def create_agent(
            db: AsyncSession,  #数据库对话
            agent_data: AgentCreate,
            user_id: str = "default_user"
    ) -> Agent:
        """创建Agent"""
        #1.转换成字典，准备插入数据库
        new_agent = Agent(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=agent_data.name,
            description=agent_data.description,
            model=agent_data.model,
            system_prompt=agent_data.system_prompt,
            tools=agent_data.tools or [],
            knowledge_bindings=agent_data.knowledge_bindings or []
        )

        #2.加入会话并提交
        db.add(new_agent)   #纳入工作单元
        try:
            await db.commit()   #提交事务
            await db.refresh(new_agent)  #刷新对象
            return new_agent   #返回结果
        except IntegrityError as e:  #捕获数据库完整性错误（名称重复、外键不存在）
            await db.rollback()   #事务回滚，撤销所有错误
            #这里可以抛出自定义异常
            print(f"数据库唯一约束冲突：{e}")
            raise ValueError("Agent 名称或字段重复")

    @staticmethod
    async def get_agent(
            db: AsyncSession,
            skip: int=0,   #分页：跳过前0条（偏移量）
            limit: int=100,  #分页：最多取100条
            user_id: str="default_user"
    ) -> List[Agent]:
        """获取Agent列表（带分页）"""
        result = await db.execute(
            select(Agent)
            .where(Agent.user_id == user_id)
            .offset(skip)  #偏移（跳过）
            .limit(limit)
            .order_by(Agent.created_at.desc())
        )
        return result.scalars().all()
    #result.scalars():把查询结果里的行数据转化成ORM对象
    #.all()：把所有对象拿出来装进一个python列表里

    @staticmethod
    async def get_agent_by_id(
            db: AsyncSession,
            agent_id: str,
            user_id: str="default_user"
    ) -> Optional[Agent]:
        """根据ID获取单个Agent(用于更新、删除时检验)"""
        result = await db.execute(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
    #用来查询“唯一的一条”，要么找到返回给你，要么给个None,不会返回一堆列表让自己去遍历

    @staticmethod
    async def delete_agent(
            db: AsyncSession,
            agent_id: str,
            user_id: str="default_user"
    ) -> bool:
        """根据ID删除Agent，返回是否删除成功"""
        agent = await AgentService.get_agent_by_id(db, agent_id,user_id)
        #先找出来这个对象
        if not agent:
            return False
        await db.delete(agent)
        #删除对象

        try:
            await db.commit()
            return True #正式提交事务，提交成功说明删掉了
        except Exception as e:
            await db.rollback()
            print("删除失败：{e}")
            return False