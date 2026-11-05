from typing import List, Optional
from pydantic import BaseModel, Field
from models.planner import StructuredPlanResponse

class CodingRequest(BaseModel):
    repository: str
    task: str
    plan: StructuredPlanResponse
    execution_id: Optional[str] = None

class CodeChangeTarget(BaseModel):
    operation: str = Field(..., description="'modify', 'create', or 'delete'")
    file_path: str = Field(..., description="Path to the file to change")
    reason: str = Field(..., description="Why this change is being made")
    changes_description: str = Field(..., description="Description of the change")
    new_content: Optional[str] = Field(None, description="The complete new content of the file. Required for 'modify' and 'create'.")

class StructuredCodeChangeResponse(BaseModel):
    changes: List[CodeChangeTarget] = Field(default_factory=list, description="List of changes to apply.")
    additional_notes: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)

class CodingResponse(BaseModel):
    workspace_id: str
    status: str = Field(..., description="'completed', 'failed', or 'rolled_back'")
    files_changed: List[str]
    diff: str
    warnings: List[str]
    unknowns: List[str]
