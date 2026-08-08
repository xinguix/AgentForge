
from fastapi import APIRouter, Depends, HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ...core.database import get_db
from ...schemas.task import TaskResponse, TaskCreate
from ...services.task_service import TaskService
from ...services.trace_service import TraceService

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

@router.post("/{task_id}/resume", response_model=TaskResponse)
async def resume_task(
        #resume:恢复
        task_id: str,
        db: AsyncSession = Depends(get_db)
):
    """恢复失败的任务（从checkpoint 续跑）"""
    try:
        task = await TaskService.resume_task(db, task_id, FIXED_USER_ID)
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败：{str(e)}")

@router.get("/{task_id}/trace")
async def get_task_trace(
        task_id: str,
        db: AsyncSession = Depends(get_db)
):
    """获取任务完整执行轨迹（JSON）"""
    task = await TaskService.get_task_by_id(db, task_id, FIXED_USER_ID)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    trace = await TraceService.get_task_trace_summary(db, task_id)
    return trace

@router.get("/{task_id}/trace/raw")
async def get_task_trace_raw(
        task_id: str,
        db: AsyncSession = Depends(get_db)
):
    """获取任务执行轨迹原始数据（包含完整输入输出）"""
    task = await TaskService.get_task_by_id(db, task_id, FIXED_USER_ID)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    runs = await TraceService.get_task_trace(db, task_id)
    return [
        {
            "node": r.node_name,
            "type": r.node_type,
            "input": r.input,
            "output": r.output,
            "latency_ms": r.latency_ms,
            "tokens": r.token_used,
            "status": r.status,
            "error": r.error,
            "timestamp": r.created_at.isoformat()
        }
        for r in runs
    ]