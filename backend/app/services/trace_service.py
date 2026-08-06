import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import time
from typing import List, Optional, Any, Dict

from ..models.run import Run
from ..models.task import Task

class TraceService:
    @staticmethod
    async def record_run(
            db: AsyncSession,
            task_id: str,
            node_name: str,
            node_type: str,
            input_data: Optional[Dict[str, Any]] = None,
            output_data: Optional[Dict[str, Any]] = None,
            latency_ms: Optional[int] = None,#延迟
            token_used: Optional[int] = None,
            status: str = "success",
            error: Optional[str] = None
    ) -> Run:
        """记录一次执行"""
        run = Run(
            task_id=task_id,
            node_name=node_name,
            node_type=node_type,
            input=input_data,
            output=json.dumps(output_data, ensure_ascii=False, default=str) if output_data else None,
            latency_ms=latency_ms,
            token_used=token_used,
            status=status,
            error=error
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    @staticmethod
    async def get_task_trace(db: AsyncSession, task_id: str) -> List[Run]:
        """获取任务完整执行轨迹（按时间排序）"""
        result = await db.execute(
            #db.execute:执行构建好的SQL语句
            select(Run)
            .where(Run.task_id == task_id)
            .order_by(Run.created_at.asc())  #asc():升序  desc:降序
        )
        return result.scalars().all()
       #scalars()：去掉外面的信封，只留下里面的信

    @staticmethod
    async def get_task_trace_summary(db: AsyncSession, task_id: str) -> Dict[str, Any]:
        """获取任务轨迹摘要（含总耗时、总token）"""
        runs = await TraceService.get_task_trace(db, task_id)

        total_latency = sum(r.latency_ms or 0 for r in runs)
        total_tokens = sum(r.token_used or 0 for r in runs)

        return {
            "task_id": task_id,
            "total_nodes" : len(runs),
            "total_latency_ms": total_latency,
            "total_tokens": total_tokens,
            "nodes": [
                {
                    "name": r.node_name,
                    "type": r.node_type,
                    "latency_ms": r.latency_ms,
                    "tokens": r.token_used,
                    "status": r.status,
                    "timestamp": r.created_at.isoformat()
                    #isoformat:将时间戳转化成国际标准的字符串
                }
                for r in runs
            ]
        }