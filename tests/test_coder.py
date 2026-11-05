import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

os.environ["GEMINI_API_KEY"] = "mock_api_key"

from api.main import app
from workspace.manager import workspace_manager, WorkspaceError

client = TestClient(app)

def test_workspace_path_traversal():
    workspace_manager.workspaces["test_ws"] = os.path.abspath("/tmp/fake_ws")
    
    with pytest.raises(WorkspaceError):
        workspace_manager._resolve_and_verify_path("test_ws", "/etc/passwd")
        
    with pytest.raises(WorkspaceError):
        workspace_manager._resolve_and_verify_path("test_ws", "../outside.txt")
        
    with pytest.raises(WorkspaceError):
        workspace_manager._resolve_and_verify_path("test_ws", "folder/../../outside.txt")
        
    # Valid
    assert workspace_manager._resolve_and_verify_path("test_ws", "src/main.py").startswith(os.path.abspath("/tmp/fake_ws"))

def test_workspace_rollback(tmp_path):
    ws_id = "test_rollback_ws"
    ws_dir = str(tmp_path)
    workspace_manager.workspaces[ws_id] = ws_dir
    
    # Setup initial file
    initial_file = os.path.join(ws_dir, "app.py")
    with open(initial_file, "w") as f:
        f.write("original content")
        
    # Transaction
    workspace_manager.begin_transaction(ws_id)
    workspace_manager.write_file(ws_id, "app.py", "modified content")
    workspace_manager.write_file(ws_id, "new_file.py", "new")
    
    # Verify modified
    with open(initial_file, "r") as f:
        assert f.read() == "modified content"
        
    # Rollback
    workspace_manager.rollback_transaction(ws_id)
    
    # Verify restored
    with open(initial_file, "r") as f:
        assert f.read() == "original content"
    assert not os.path.exists(os.path.join(ws_dir, "new_file.py"))

@patch("agents.coder.github_service")
@patch("agents.coder.workspace_manager")
@patch("agents.coder.PromptOrchestrator")
def test_coding_api(mock_orchestrator, mock_workspace, mock_github):
    mock_github._parse_repo_url.return_value = "facebook/react"
    mock_workspace.create_workspace.return_value = "nexus_workspace_test123"
    
    # Mock LLM Response
    from models.coder import StructuredCodeChangeResponse
    mock_orchestrator.run_coder.return_value = StructuredCodeChangeResponse(
        changes=[
            {
                "operation": "modify",
                "file_path": "src/app.js",
                "reason": "Update",
                "changes_description": "Added stuff",
                "new_content": "console.log('hi');"
            }
        ]
    )
    
    mock_workspace.generate_diff.return_value = "--- a/src/app.js\n+++ b/src/app.js\n+console.log('hi');"
    
    # Mock valid plan
    plan_data = {
        "task_summary": "Task",
        "understanding": "Understanding",
        "files_to_modify": [{"path": "src/app.js", "reason": "reason"}],
        "files_to_add": [],
        "files_to_delete": [],
        "implementation_steps": [],
        "testing_plan": [],
        "dependencies": [],
        "risks": [],
        "unknowns": [],
        "retrieved_sources": []
    }
    
    response = client.post("/api/agents/coder", json={
        "repository": "facebook/react",
        "task": "do something",
        "plan": plan_data
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "src/app.js" in data["files_changed"]
    assert "console.log" in data["diff"]
