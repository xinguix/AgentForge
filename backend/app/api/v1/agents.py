from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ...core.database import get_db
from ...schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from ...services.agent_services import  AgentService

router = APIRouter(
    prefix="/agents",  #前缀
    tags=["Agent管理"]  #标签
)

FIXED_USER_ID = "default_user"

@router.post(
    "/",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_agent(
        agent_data: AgentCreate,
        db: AsyncSession = Depends(get_db)
):
    """创建新的Agent"""
    try:
        new_agent = await AgentService.create_agent(db, agent_data, FIXED_USER_ID)
        return new_agent
    except ValueError as e:
        raise HTTPException(status_code=400,detail=str(e))

@router.get(
    "/",
    response_model=List[AgentResponse]
)
async def list_agents(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    """获取Agent列表（分页）"""
    agents = await AgentService.get_agent(db, skip, limit, FIXED_USER_ID)
    return agents

@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_agent(
        agent_id: str,
        db: AsyncSession = Depends(get_db)
):
    """删除指定Agent(根据ID)"""
    deleted = await AgentService.delete_agent(db, agent_id, FIXED_USER_ID)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent{agent_id}未找到或无权限删除"
        )
    return