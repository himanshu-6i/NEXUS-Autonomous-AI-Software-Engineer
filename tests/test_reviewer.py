import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from workspace.manager import workspace_manager
from api.main import app
from models.reviewer import StructuredReviewReport, ReviewFinding
from models.tester import StructuredTestReport, TestExecutionResult
from models.planner import StructuredPlanResponse

client = TestClient(app)

@patch("agents.reviewer.PromptOrchestrator")
def test_reviewer_approve_success(mock_orchestrator, tmp_path):
    ws_id = "nexus_workspace_review_pass"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    (tmp_path / "app.py").write_text("code")
    
    # LLM returns approve
    mock_orchestrator.run_reviewer.return_value = StructuredReviewReport(
        verdict="approve",
        overall_score=95,
        correctness_score=90,
        test_score=100,
        maintainability_score=90,
        security_score=100,
        scope_score=100,
        findings=[],
        summary="Looks great."
    )
    
    planner_result = StructuredPlanResponse(
        task_summary="", understanding="", files_to_modify=[],
        files_to_add=[], files_to_delete=[], implementation_steps=[],
        testing_plan=[], dependencies=[], risks=[], unknowns=[], retrieved_sources=[]
    )
    
    test_result = StructuredTestReport(
        workspace_id=ws_id,
        status="passed", # tests passed
        framework="pytest",
        tests_selected=[],
        execution=TestExecutionResult(exit_code=0, duration_ms=10, tests_passed=1),
        failures=[],
        output=""
    )
    
    response = client.post("/api/agents/reviewer", json={
        "workspace_id": ws_id,
        "repository": "facebook/react",
        "task": "task",
        "planner_result": planner_result.model_dump(),
        "changed_files": ["app.py"],
        "diff": "diff",
        "final_test_result": test_result.model_dump()
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "approve"
    assert data["overall_score"] == 95

@patch("agents.reviewer.PromptOrchestrator")
def test_reviewer_blocks_on_failed_tests(mock_orchestrator, tmp_path):
    ws_id = "nexus_workspace_review_fail"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    
    # LLM tries to approve
    mock_orchestrator.run_reviewer.return_value = StructuredReviewReport(
        verdict="approve",
        overall_score=90,
        correctness_score=90, test_score=90, maintainability_score=90, security_score=90, scope_score=90,
        findings=[],
        summary="I think it's good."
    )
    
    planner_result = StructuredPlanResponse(
        task_summary="", understanding="", files_to_modify=[], files_to_add=[], files_to_delete=[], implementation_steps=[], testing_plan=[], dependencies=[], risks=[], unknowns=[], retrieved_sources=[]
    )
    
    # But tests FAILED
    test_result = StructuredTestReport(
        workspace_id=ws_id,
        status="failed",
        framework="pytest",
        tests_selected=[],
        execution=TestExecutionResult(exit_code=1, duration_ms=10, tests_failed=1),
        failures=[],
        output=""
    )
    
    response = client.post("/api/agents/reviewer", json={
        "workspace_id": ws_id,
        "repository": "facebook/react",
        "task": "task",
        "planner_result": planner_result.model_dump(),
        "changed_files": [],
        "diff": "",
        "final_test_result": test_result.model_dump()
    })
    
    assert response.status_code == 200
    data = response.json()
    # Backend overrides LLM
    assert data["verdict"] == "block"
    assert "[SYSTEM INJECTED]" in data["summary"]

@patch("agents.reviewer.PromptOrchestrator")
def test_reviewer_blocks_on_critical_security(mock_orchestrator, tmp_path):
    ws_id = "nexus_workspace_review_sec"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    
    # LLM tries to request_changes but there is a critical finding
    mock_orchestrator.run_reviewer.return_value = StructuredReviewReport(
        verdict="request_changes",
        overall_score=50,
        correctness_score=50, test_score=50, maintainability_score=50, security_score=0, scope_score=50,
        findings=[
            ReviewFinding(severity="critical", category="security", title="SQLi", description="Bad", evidence="x", recommendation="fix")
        ],
        summary="Please fix."
    )
    
    planner_result = StructuredPlanResponse(task_summary="", understanding="", files_to_modify=[], files_to_add=[], files_to_delete=[], implementation_steps=[], testing_plan=[], dependencies=[], risks=[], unknowns=[], retrieved_sources=[])
    
    response = client.post("/api/agents/reviewer", json={
        "workspace_id": ws_id,
        "repository": "facebook/react",
        "task": "task",
        "planner_result": planner_result.model_dump(),
        "changed_files": [],
        "diff": ""
    })
    
    assert response.status_code == 200
    data = response.json()
    # Backend overrides to block
    assert data["verdict"] == "block"
    assert "Critical security findings detected" in data["summary"]
