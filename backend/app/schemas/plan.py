from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class PlanStep(BaseModel):
    """计划中的单个步骤"""
    step_id: int = Field(..., description="步骤序号，从1开始")
    description: str = Field(..., description="该步骤的具体任务描述")
    agent_type: Literal["research", "writer", "reviewer"] = Field(
        ...,
        description="执行该步骤的Agent类型：research(搜索/检索)，writer(撰写/生成)， reviewer(审核/质检)"
    )
    depends_on: Optional[List[int]] = Field(
        default=[],
        description="依赖的前置步骤ID列表，为空表示无依赖"
    )

class Plan(BaseModel):
    """完整的任务计划"""
    steps: List[PlanStep] = Field(..., description="任务步骤列表")
    rationale: str = Field(..., description="制定该计划的理由/思路（用于Trace可视化）")
    need_research: bool = Field(True, description="该问题是否需要外部检索、研究，False表示可直接回答。")