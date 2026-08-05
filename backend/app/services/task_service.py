import json
import traceback

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid

from ..core.planner import planner_node
from ..core.redis_client import get_redis
from ..core.state import AgentState
from ..models.task import Task, TaskStatus
from ..schemas.task import TaskCreate
from ..core.graph import get_graph


class TaskService:
    @staticmethod
    async def create_planning_task(
            db: AsyncSession,
            task_data: TaskCreate,
            user_id: str = "default_user"
    ) -> Task:
        #1.创建Task记录,状态为CREATED
        new_task = Task(
            id = str(uuid.uuid4()),
            user_id = user_id,
            status = TaskStatus.CREATED,
            input = task_data.message
        )
        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)

        #2.更新状态为PLANNING(还没跑图，先占位)
        new_task.status = TaskStatus.PLANNING
        await db.commit()

        #3.构造初始状态
        messages = []
        if task_data.system_prompt:
            messages.append(SystemMessage(content=task_data.system_prompt))
        messages.append(HumanMessage(content=task_data.message))

        initial_state = AgentState(
            messages = messages,
            task_id = new_task.id,
            intermediate_steps=[],
            plan = None,
            current_step_index = 0,
            review_status=None,
            retry_count=0
        )

        #4.把初始状态存入Redis(key: task:{id}:state)
        try:
            redis_client = await get_redis()
            #状态快照
            state_snapshot = {
                "task_id": new_task.id,
                "current_step_index": 0,
                "retry_count": 0,
                "messages_count": len(messages),
            }
            await redis_client.setex(
            #setex: Redis命令，意为SET with EXpiration(设置值并同时指定过期时间)
                f"task:{new_task.id}:state",
                3600, #一小时过期
                json.dumps(state_snapshot)#将字典转化为JSON字符串在存入redis(redis只能存文本后二进制)
            )
        except Exception as e:
            print(f"Redis 存储失败：{e}")

        #5. 更新状态为RUNNING
        new_task.status = TaskStatus.RUNNING
        await db.commit()

        #6.调用langgraph
        try:
            graph = await get_graph()
            final_state = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": new_task.id, "db":db}})

            #提取结果
            plan_obj = final_state.get("plan")
        #安全的plan数据处理块
            final_answer = final_state.get("final_answer", "")
            intermediate = final_state.get("intermediate_steps", [])

            if not final_answer:
                fallback = "【系统生成】\n"
                for step in intermediate:
                    if "search_result" in step:
                        fallback += f"- {step.get('step_description', '')}: {step['search_result'][:200]}...\n"
                final_answer = fallback or "系统未能生成有效回答。"

            new_task.status = TaskStatus.COMPLETED
            new_task.output = final_answer
            new_task.plan_data = plan_obj.model_dump() if plan_obj else None
            new_task.current_step_index = len(plan_obj.steps) if plan_obj else 0

            await db.commit()
            await db.refresh(new_task)

        except Exception as e:
            new_task.status = TaskStatus.FAILED
            new_task.error = traceback.format_exc()[:500]
            await db.commit()
            await db.refresh(new_task)
            raise

        #无论成功与否都要跑finally
        finally:
            #7.清理Redis缓存（任务结束）
            try:
                redis_client = await get_redis()
                await redis_client.delete(f"task:{new_task.id}:state")
            except:
                pass

        return new_task

    @staticmethod
    async def get_task_by_id(db: AsyncSession, task_id: str, user_id: str="default_user") -> Optional[Task]:
        """根据ID获取任务"""
        result = await db.execute(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        )
        return result.scalar_one_or_none()
        #返回任务ID和用户ID查询单个任务，如果不存在就返回None

    @staticmethod
    async def list_tasks(db: AsyncSession, skip: int=0, limit: int = 100, user_id: str="default_user"):
        """获取任务列表"""
        result = await db.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def resume_task(db: AsyncSession, task_id: str, user_id: str="default_user") -> Task:
        """从CHeckpoint恢复任务（断点续跑）"""
        #检查任务是否存在并且状态为FAILED
        task = await TaskService.get_task_by_id(db, task_id, user_id)
        if not task:
            raise ValueError("任务不存在")

        if task.status != TaskStatus.FAILED:
            raise ValueError("只有失败的任务才能恢复")

        #2.更新状态为RUNNING
        task.status = TaskStatus.RUNNING
        await db.commit()

        #3.获取编译好的图
        graph = await get_graph()

        #4.在同一个thread_id(task_id)重新调用，LangGraph会自动从最近的checkpointer恢复
        try:
            #注意：这里需要重建初始状态（但图会从checkpoint 恢复，不是从头跑）
            #我们传入一个空状态，只带thread_id
            final_state = await graph.ainvoke(
                {},
                config={"configurable": {"thread_id": task_id, "db":db}},
            )

            #5.提取结果并更新Task
            final_answer = final_state.get("final_answer", "")
            plan_obj = final_state.get("plan")

            task.status = TaskStatus.COMPLETED
            task.output = final_answer
            task.plan_data = plan_obj.model_dump() if plan_obj else None
            await db.commit()
            await db.refresh(task)

        except Exception as e:
            task.error = traceback.format_exc()[:500]
            await db.commit()
            raise