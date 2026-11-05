from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TesterRequest(BaseModel):
    workspace_id: str
    repository: str
    task: str
    changed_files: List[str]
    execution_id: Optional[str] = None

class TestCommand(BaseModel):
    executable: str = Field(..., description="The whitelisted test runner (e.g., 'pytest', 'npm')")
    arguments: List[str] = Field(default_factory=list, description="Arguments for the test runner.")

class TestSelection(BaseModel):
    command: TestCommand
    reason: str

class TestFailure(BaseModel):
    test: str
    file: Optional[str] = None
    message: str
    traceback: Optional[str] = None

class TestExecutionResult(BaseModel):
    exit_code: int
    duration_ms: int
    tests_run: int | str = "unknown"
    tests_passed: int | str = "unknown"
    tests_failed: int | str = "unknown"
    tests_skipped: int | str = "unknown"

class StructuredTestReport(BaseModel):
    workspace_id: str
    status: str = Field(..., description="'passed', 'failed', 'error', 'timeout', 'dependencies_unavailable'")
    framework: str
    tests_selected: List[TestSelection]
    execution: Optional[TestExecutionResult] = None
    failures: List[TestFailure] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    output: str = Field(..., description="Truncated stdout/stderr of the test run.")
    unknowns: List[str] = Field(default_factory=list)

class StructuredTestSelectionResponse(BaseModel):
    """Schema for Gemini to return selected test commands."""
    selections: List[TestSelection]
    framework: str
    unknowns: List[str] = Field(default_factory=list)
