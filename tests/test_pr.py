import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from workspace.manager import workspace_manager
from api.main import app
from models.reviewer import StructuredReviewReport, ReviewFinding
from models.tester import StructuredTestReport, TestExecutionResult
from models.planner import StructuredPlanResponse

client = TestClient(app)

def create_mock_pr_request(ws_id: str, test_status: str = "passed", review_verdict: str = "approve", files: list = ["app.py"], confirm: bool = True):
    planner_result = StructuredPlanResponse(
        task_summary="", understanding="", files_to_modify=[], files_to_add=[], files_to_delete=[], implementation_steps=[], testing_plan=[], dependencies=[], risks=[], unknowns=[], retrieved_sources=[]
    )
    test_result = StructuredTestReport(
        workspace_id=ws_id, status=test_status, framework="pytest", tests_selected=[],
        execution=TestExecutionResult(exit_code=0, duration_ms=10, tests_passed=1),
        failures=[], output=""
    )
    review_result = StructuredReviewReport(
        verdict=review_verdict, overall_score=100, correctness_score=100, test_score=100, maintainability_score=100, security_score=100, scope_score=100,
        findings=[], summary=""
    )
    return {
        "workspace_id": ws_id,
        "repository": "facebook/react",
        "task": "Test Task",
        "planner_result": planner_result.model_dump(),
        "changed_files": files,
        "final_test_result": test_result.model_dump(),
        "review_result": review_result.model_dump(),
        "confirm": confirm
    }

@patch("agents.pr.github_service")
def test_pr_success(mock_github, tmp_path):
    ws_id = "nexus_workspace_pr_success"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    (tmp_path / "app.py").write_text("code")
    
    # Mock github service
    from models.github import RepoMetadata
    mock_github.get_repo_metadata.return_value = RepoMetadata(
        name="react", owner="facebook", default_branch="main", description="", visibility="public", primary_language="ts", url="", latest_commit_sha="abcdef"
    )
    mock_github.create_commit_from_workspace.return_value = "newcommitsha"
    mock_github.create_pull_request.return_value = "https://github.com/facebook/react/pull/123"
    
    req = create_mock_pr_request(ws_id)
    response = client.post("/api/github/pr", json=req)
    
    assert response.status_code == 200
    data = response.json()
    assert data["pr_url"] == "https://github.com/facebook/react/pull/123"
    assert data["commit_sha"] == "newcommitsha"
    assert data["status"] == "created"

@patch("agents.pr.github_service")
def test_pr_blocks_on_unconfirmed(mock_github, tmp_path):
    ws_id = "nexus_workspace_pr_noconfirm"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    
    req = create_mock_pr_request(ws_id, confirm=False)
    response = client.post("/api/github/pr", json=req)
    
    assert response.status_code == 400
    assert "User confirmation is required" in response.json()["detail"]

@patch("agents.pr.github_service")
def test_pr_blocks_on_failed_tests(mock_github, tmp_path):
    ws_id = "nexus_workspace_pr_badtest"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    
    req = create_mock_pr_request(ws_id, test_status="failed")
    response = client.post("/api/github/pr", json=req)
    
    assert response.status_code == 400
    assert "tests must pass" in response.json()["detail"]

@patch("agents.pr.github_service")
def test_pr_blocks_on_review_changes(mock_github, tmp_path):
    ws_id = "nexus_workspace_pr_badreview"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    
    req = create_mock_pr_request(ws_id, review_verdict="request_changes")
    response = client.post("/api/github/pr", json=req)
    
    assert response.status_code == 400
    assert "verdict must be 'approve'" in response.json()["detail"]

@patch("agents.pr.github_service")
def test_pr_blocks_on_secrets(mock_github, tmp_path):
    ws_id = "nexus_workspace_pr_secrets"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    
    # Create an .env file
    (tmp_path / ".env.local").write_text("SECRET=123")
    
    req = create_mock_pr_request(ws_id, files=[".env.local"])
    response = client.post("/api/github/pr", json=req)
    
    assert response.status_code == 400
    assert "Security check failed" in response.json()["detail"]
    assert "Sensitive file blocked" in response.json()["detail"]

@patch("agents.pr.github_service")
def test_pr_blocks_on_secret_content(mock_github, tmp_path):
    ws_id = "nexus_workspace_pr_secretcontent"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    
    # Create a normal file with secret content
    (tmp_path / "app.py").write_text("api_key = 'abcdef123456'")
    
    req = create_mock_pr_request(ws_id, files=["app.py"])
    response = client.post("/api/github/pr", json=req)
    
    assert response.status_code == 400
    assert "Security check failed" in response.json()["detail"]
    assert "Sensitive content detected" in response.json()["detail"]

