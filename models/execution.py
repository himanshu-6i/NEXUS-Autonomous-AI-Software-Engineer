from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from pydantic import BaseModel, Field

def utc_now():
    return datetime.now(timezone.utc)

class ExecutionEvent(BaseModel):
    event_type: str
    execution_id: str
    stage: str
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ExecutionState(BaseModel):
    execution_id: str
    workspace_id: str
    repository: str
    task: str
    status: str = "created"  # e.g., created, planning, coding, testing, debugging, reviewing, pr_created, failed
    current_stage: str = "created"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    
    # Store minimal metadata to recreate the view
    base_branch: Optional[str] = None
    base_sha: Optional[str] = None
    nexus_branch: Optional[str] = None
    commit_sha: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None

    # Agent Results (Stored concisely)
    planner_result: Optional[Dict[str, Any]] = None
    coding_result: Optional[Dict[str, Any]] = None
    test_result: Optional[Dict[str, Any]] = None
    debug_history: List[Dict[str, Any]] = Field(default_factory=list)
    review_result: Optional[Dict[str, Any]] = None
