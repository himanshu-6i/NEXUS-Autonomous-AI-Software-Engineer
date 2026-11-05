from typing import List, Optional
from pydantic import BaseModel, Field
from models.planner import StructuredPlanResponse
from models.tester import StructuredTestReport

class ReviewFinding(BaseModel):
    severity: str = Field(..., description="'critical', 'high', 'medium', 'low', 'info'")
    category: str = Field(..., description="'correctness', 'testing', 'security', 'maintainability', 'regression', 'scope'")
    title: str
    description: str
    file: Optional[str] = None
    line: Optional[int] = None
    evidence: str = Field(..., description="Quote or context from the diff or code.")
    recommendation: str

class StructuredReviewReport(BaseModel):
    """Schema for Gemini to return a code review."""
    verdict: str = Field(..., description="'approve', 'request_changes', 'block'")
    overall_score: int = Field(..., ge=0, le=100)
    correctness_score: int = Field(..., ge=0, le=100)
    test_score: int = Field(..., ge=0, le=100)
    maintainability_score: int = Field(..., ge=0, le=100)
    security_score: int = Field(..., ge=0, le=100)
    scope_score: int = Field(..., ge=0, le=100)
    findings: List[ReviewFinding] = Field(default_factory=list)
    summary: str
    recommendations: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)

class ReviewerRequest(BaseModel):
    workspace_id: str
    repository: str
    task: str
    planner_result: StructuredPlanResponse
    changed_files: List[str]
    diff: str
    final_test_result: Optional[StructuredTestReport] = None
    debug_history: Optional[List[dict]] = None
    execution_id: Optional[str] = None

class ReviewerResponse(StructuredReviewReport):
    workspace_id: str
