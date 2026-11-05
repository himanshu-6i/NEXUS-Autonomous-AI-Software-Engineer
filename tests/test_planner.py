import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

os.environ["GEMINI_API_KEY"] = "mock_api_key"

from api.main import app
from models.planner import StructuredPlanResponse

client = TestClient(app)

@patch("agents.planner.github_service")
@patch("agents.planner.retrieval_service")
@patch("agents.planner.PromptOrchestrator")
def test_planner_api(mock_orchestrator, mock_retrieval, mock_github):
    mock_github._parse_repo_url.return_value = "facebook/react"
    
    # Mock retrieval
    mock_chunk = MagicMock()
    mock_chunk.file_path = "src/auth.js"
    mock_chunk.start_line = 10
    mock_chunk.end_line = 20
    mock_chunk.content = "function auth() {}"
    mock_retrieval.retrieve.return_value = [mock_chunk]
    
    # Mock orchestrator plan
    mock_orchestrator.run_planner.return_value = StructuredPlanResponse(
        task_summary="Add auth",
        understanding="I understand.",
        files_to_modify=[{"path": "src/auth.js", "reason": "Need to update auth logic."}],
        files_to_add=[],
        files_to_delete=[],
        implementation_steps=[{"step": 1, "description": "Update auth()", "files": ["src/auth.js"]}],
        testing_plan=["Test auth"],
        dependencies=[],
        risks=[],
        unknowns=[],
        retrieved_sources=[] # Agent should fill this
    )
    
    response = client.post("/api/agents/planner", json={
        "repository": "facebook/react",
        "task": "Add auth"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["task_summary"] == "Add auth"
    assert len(data["retrieved_sources"]) == 1
    assert data["retrieved_sources"][0]["file_path"] == "src/auth.js"
    
def test_planner_api_empty_task():
    response = client.post("/api/agents/planner", json={
        "repository": "facebook/react",
        "task": "   "
    })
    
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
