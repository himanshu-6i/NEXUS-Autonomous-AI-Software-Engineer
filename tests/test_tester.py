import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from models.tester import TestCommand
from workspace.runner import test_runner, RunnerError
from workspace.manager import workspace_manager
from api.main import app

client = TestClient(app)

def test_runner_validation():
    # Valid
    test_runner.validate_command("fake_ws", TestCommand(executable="pytest", arguments=["tests/"]))
    
    # Invalid executable
    with pytest.raises(RunnerError, match="not allowed"):
        test_runner.validate_command("fake_ws", TestCommand(executable="bash", arguments=["-c", "echo hello"]))
        
    # Shell characters
    with pytest.raises(RunnerError, match="forbidden shell characters"):
        test_runner.validate_command("fake_ws", TestCommand(executable="pytest", arguments=["tests/", "&&", "rm", "-rf", "/"]))
        
    # Path traversal in arguments
    with pytest.raises(RunnerError, match="path traversal attempt"):
        test_runner.validate_command("fake_ws", TestCommand(executable="pytest", arguments=["../../tests/"]))

def test_test_output_parsing():
    from agents.tester import tester_agent
    
    # pytest success output
    out = "============================= test session starts =============================\n2 passed in 0.10s"
    res, fails = tester_agent._parse_test_output("pytest", out, exit_code=0, duration_ms=100)
    assert res.tests_passed == 2
    assert res.tests_failed == 0
    assert res.tests_run == 2
    
    # pytest failure output
    out = "============================= test session starts =============================\n1 failed, 3 passed in 0.20s"
    res, fails = tester_agent._parse_test_output("pytest", out, exit_code=1, duration_ms=200)
    assert res.tests_passed == 3
    assert res.tests_failed == 1
    assert res.tests_run == 4
    assert len(fails) > 0

@patch("agents.tester.PromptOrchestrator")
@patch("agents.tester.test_runner")
def test_tester_api(mock_runner, mock_orchestrator, tmp_path):
    ws_id = "nexus_workspace_test"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    
    from models.tester import StructuredTestSelectionResponse, TestSelection, TestCommand
    
    # Mock LLM Selection
    mock_orchestrator.run_test_selection.return_value = StructuredTestSelectionResponse(
        selections=[TestSelection(command=TestCommand(executable="pytest", arguments=["test_auth.py"]), reason="Modified auth.")],
        framework="pytest",
        unknowns=[]
    )
    
    # Mock Runner execution
    mock_runner.execute.return_value = (0, "1 passed in 0.05s")
    
    response = client.post("/api/agents/tester", json={
        "workspace_id": ws_id,
        "repository": "facebook/react",
        "task": "do something",
        "changed_files": ["auth.py"]
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "passed"
    assert data["framework"] == "pytest"
    assert data["execution"]["tests_passed"] == 1
    assert "1 passed in 0.05s" in data["output"]
