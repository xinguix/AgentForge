
from fastapi import APIRouter, Depends, HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ...core.database import get_db
from ...schemas.task import TaskResponse, TaskCreate
from ...services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["任务管理"])

FIXED_USER_ID = "default_user"

@router.post("/plan",response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_plan_task(
        task_data: TaskCreate,
        db: AsyncSession = Depends(get_db)
):
    """创建任务并生成计划（Planner自动执行）"""
    try:
        task = await TaskService.create_planning_task(db, task_data, FIXED_USER_ID)
        return task
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500,detail=f"任务创建失败：{str(e)}")

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
        task_id: str,
        db: AsyncSession = Depends(get_db)
):
    """获取任务详情（包含完整的Plan）"""
    task = await TaskService.get_task_by_id(db, task_id, FIXED_USER_ID)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task

@router.get("/{task_id}/status")
async def get_task_status(
        task_id: str,
        db: AsyncSession = Depends(get_db)
):
    """快速获取任务状态（不返回完整详情，省流量）"""
    task = await TaskService.get_task_by_id(db, task_id, FIXED_USER_ID)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"id": task.id, "status": task.status.value}

@router.get("/", response_model=List[TaskResponse])
async def List_tasks(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db)
):
    """获取任务列表（分页）"""
    tasks = await TaskService.list_tasks(db, skip, limit, FIXED_USER_ID)
    return tasks