from typing import List, Optional, Any
from pydantic import BaseModel, Field
from models.tester import StructuredTestReport
from models.coder import CodeChangeTarget

class DebuggerRequest(BaseModel):
    workspace_id: str
    repository: str
    task: str
    test_result: StructuredTestReport
    retry_count: int = Field(0, description="Initial retry count, default 0")
    execution_id: Optional[str] = None

class StructuredDebuggerResponse(BaseModel):
    """Schema for Gemini to return a debugging analysis and proposed fix."""
    failure_class: str = Field(..., description="E.g., logic_error, syntax_error, missing_dependency, unknown")
    diagnosis: str
    confidence: float
    root_cause: str
    changes: List[CodeChangeTarget] = Field(default_factory=list)
    expected_effect: str
    risks: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)

class DebuggerAttemptState(BaseModel):
    attempt: int
    failure_class: str
    diagnosis: str
    files_changed: List[str]
    test_status: str

class DebuggerResponse(BaseModel):
    status: str = Field(..., description="'fixed', 'debugging_failed', 'repeated_failure', 'unsafe_fix', 'max_retries_reached'")
    workspace_id: str
    attempts: int
    final_test_status: str
    diagnosis: str
    files_changed: List[str]
    attempt_history: List[DebuggerAttemptState]
    final_diff: str
    warnings: List[str]
    unknowns: List[str]
