from typing import List, Optional
from pydantic import BaseModel, Field

class PlannerRequest(BaseModel):
    repository: str = Field(..., description="GitHub repository URL or identifier")
    task: str = Field(..., description="The software-engineering task description", max_length=2000)
    execution_id: Optional[str] = Field(None, description="Execution identifier")

class PlanFileTarget(BaseModel):
    path: str
    reason: str

class PlanStep(BaseModel):
    step: int
    description: str
    files: List[str]

class RetrievedSource(BaseModel):
    file_path: str
    start_line: int
    end_line: int

class StructuredPlanResponse(BaseModel):
    task_summary: str = Field(..., description="Brief summary of the requested task.")
    understanding: str = Field(..., description="Detailed understanding of the task and approach.")
    files_to_modify: List[PlanFileTarget] = Field(default_factory=list, description="Existing files that need modification.")
    files_to_add: List[PlanFileTarget] = Field(default_factory=list, description="New files to be created.")
    files_to_delete: List[PlanFileTarget] = Field(default_factory=list, description="Files to be deleted.")
    implementation_steps: List[PlanStep] = Field(default_factory=list, description="Step-by-step implementation plan.")
    testing_plan: List[str] = Field(default_factory=list, description="List of testing strategies or tests to write.")
    dependencies: List[str] = Field(default_factory=list, description="Required dependencies to install or modify.")
    risks: List[str] = Field(default_factory=list, description="Potential risks or side-effects of this change.")
    unknowns: List[str] = Field(default_factory=list, description="Missing information or assumptions made.")
    retrieved_sources: List[RetrievedSource] = Field(default_factory=list, description="List of retrieved source code segments used for context.")
