import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_create_execution():
    response = client.post("/api/executions", json={"repository": "test/repo", "task": "test task"})
    assert response.status_code == 200
    data = response.json()
    assert data["repository"] == "test/repo"
    assert data["status"] == "created"
    assert "execution_id" in data

def test_get_execution():
    # First create
    res = client.post("/api/executions", json={"repository": "test/repo2", "task": "test task 2"})
    exec_id = res.json()["execution_id"]
    
    # Then get
    response = client.get(f"/api/executions/{exec_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["execution_id"] == exec_id
    assert data["repository"] == "test/repo2"

def test_list_executions():
    response = client.get("/api/executions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

def test_get_execution_events():
    res = client.post("/api/executions", json={"repository": "test/repo", "task": "test task"})
    exec_id = res.json()["execution_id"]
    
    response = client.get(f"/api/executions/{exec_id}/events")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["event_type"] == "execution_created"

def test_execution_not_found():
    response = client.get("/api/executions/nonexistent_id")
    assert response.status_code == 404

def test_agents_persist_state(tmp_path):
    # This tests whether calling the agents actually updates the state
    res = client.post("/api/executions", json={"repository": "test/repo", "task": "Add email validation"})
    exec_id = res.json()["execution_id"]
    
    with patch("api.planner.planner_agent") as mock_planner:
        from models.planner import StructuredPlanResponse
        mock_planner.plan_task.return_value = StructuredPlanResponse(
            task_summary="", understanding="", files_to_modify=[], files_to_add=[], files_to_delete=[], implementation_steps=[], testing_plan=[], dependencies=[], risks=[], unknowns=[], retrieved_sources=[]
        )
        # Call planner with exec_id
        plan_res = client.post("/api/agents/planner", json={
            "repository": "test/repo",
            "task": "Add email validation",
            "execution_id": exec_id
        })
        assert plan_res.status_code == 200
        
        # Verify state updated
        exec_state = client.get(f"/api/executions/{exec_id}").json()
        assert exec_state["current_stage"] == "planning"
        assert exec_state["status"] == "completed"
        assert exec_state["planner_result"] is not None
