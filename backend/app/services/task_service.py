from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid

from ..core.planner import planner_node
from ..core.state import AgentState
from ..models.task import Task
from ..schemas.task import TaskCreate
from ..core.graph import get_graph


class TaskService:
    @staticmethod
    async def create_planning_task(
            db: AsyncSession,
            task_data: TaskCreate,
            user_id: str = "default_user"
    ) -> Task:
        """
        :param db: 调用planner生成计划
        :param task_data: 存入数据库
        :return: Task对象
        """
        #0.去重：调用planner前，先看这个用户是不是已经有了相同的input还在planning的任务
        existing = await db.execute(
            select(Task).where(
                Task.user_id == user_id,
                Task.input == task_data.message,
                Task.status == "planning",
            )
        )
        existing_task = existing.scalars().first()
        if existing_task is not None:
            return existing_task

        #1.构造Planner需要的state
        messages = []
        if task_data.system_prompt:
            messages.append(SystemMessage(content=task_data.system_prompt))
        messages.append(HumanMessage(content=task_data.message))

        initial_state = AgentState(
            messages = messages,
            task_id = None,
            intermediate_steps=[],
            plan = None,
            current_step_index = 0
        )

        #2.调用Planner节点
        #注意：planner_node返回的是（“plan”: plan, "current_step_index": 0）
        graph = get_graph()
        final_state = await graph.ainvoke(initial_state)

        review_status = final_state.get("review_status", "unknown")
        intermediate = final_state.get("intermediate_steps", [])

        plan_obj = final_state.get("plan")

        #4.整理搜索结果（写入output字段，方便前端展示）
        output_text = f"任务执行完成。审查结果：{review_status}\n"
        output_text += "=" * 40 + "\n"
        for idx, step in enumerate(intermediate):
            if "search_result" in step:
                output_text += f"步骤 {step['step_id']} - {step['step_description']}:\n"
                output_text += f"{step['search_result'][:300]}...\n\n"
                #把step_id 、描述、搜索结果（截取前200字符）拼接到output_text中，用于前端展示

        #3.创建Task记录
        new_task = Task(
            id = str(uuid.uuid4()),
            user_id = user_id,
            status = "completed",
            input = task_data.message,
            output = output_text,
            plan_data = plan_obj.model_dump() if plan_obj else None,  #转成字典存JSON
            current_step_index = len(plan_obj.steps) if plan_obj else 0
        )

        db.add(new_task)
        await db.commit()
        await db.refresh(new_task)
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