from typing import List, Optional
from pydantic import BaseModel, Field
from models.reviewer import StructuredReviewReport
from models.tester import StructuredTestReport
from models.planner import StructuredPlanResponse

class PRRequest(BaseModel):
    workspace_id: str
    repository: str
    task: str
    planner_result: StructuredPlanResponse
    changed_files: List[str]
    final_test_result: StructuredTestReport
    review_result: StructuredReviewReport
    confirm: bool = False
    execution_id: Optional[str] = None

class PRResponse(BaseModel):
    workspace_id: str
    repository: str
    branch_name: str
    commit_sha: str
    pr_url: str
    status: str
