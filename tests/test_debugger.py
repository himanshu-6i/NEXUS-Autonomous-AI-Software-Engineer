import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from workspace.manager import workspace_manager
from api.main import app

client = TestClient(app)

@patch("agents.debugger.PromptOrchestrator")
@patch("agents.debugger.tester_agent")
def test_debugger_success_loop(mock_tester, mock_orchestrator, tmp_path):
    ws_id = "nexus_workspace_debug_success"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    
    # Setup files for rollback testing
    (tmp_path / "app.py").write_text("def buggy(): pass")
    
    from models.debugger import StructuredDebuggerResponse, CodeChangeTarget
    from models.tester import StructuredTestReport, TestExecutionResult
    
    # Mock LLM to return a fix
    mock_orchestrator.run_debugger.return_value = StructuredDebuggerResponse(
        failure_class="logic_error",
        diagnosis="Missing return.",
        confidence=0.9,
        root_cause="Forgot return.",
        changes=[
            CodeChangeTarget(
                operation="modify",
                file_path="app.py",
                reason="Fix bug",
                new_content="def buggy(): return True",
                changes_description=""
            )
        ],
        expected_effect="Tests pass.",
        risks=[],
        unknowns=[]
    )
    
    # Mock Tester to return success on the rerun
    mock_tester.run_tests.return_value = StructuredTestReport(
        workspace_id=ws_id,
        status="passed",
        framework="pytest",
        tests_selected=[],
        execution=TestExecutionResult(exit_code=0, duration_ms=10, tests_passed=1),
        failures=[],
        output="1 passed"
    )
    
    initial_test_result = {
        "workspace_id": ws_id,
        "status": "failed",
        "framework": "pytest",
        "tests_selected": [],
        "execution": {"exit_code": 1, "duration_ms": 10, "tests_failed": 1, "tests_passed": 0, "tests_run": 1, "tests_skipped": 0},
        "failures": [],
        "output": "1 failed"
    }
    
    response = client.post("/api/agents/debugger", json={
        "workspace_id": ws_id,
        "repository": "facebook/react",
        "task": "task",
        "test_result": initial_test_result,
        "retry_count": 0
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "fixed"
    assert data["attempts"] == 1
    assert data["final_test_status"] == "passed"
    assert "app.py" in data["files_changed"]
    assert len(data["attempt_history"]) == 1
    
@patch("agents.debugger.PromptOrchestrator")
@patch("agents.debugger.tester_agent")
def test_debugger_worse_rollback(mock_tester, mock_orchestrator, tmp_path):
    ws_id = "nexus_workspace_debug_worse"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    
    (tmp_path / "app.py").write_text("def func(): pass")
    
    from models.debugger import StructuredDebuggerResponse, CodeChangeTarget
    from models.tester import StructuredTestReport, TestExecutionResult
    
    # Fix breaks MORE tests
    mock_orchestrator.run_debugger.return_value = StructuredDebuggerResponse(
        failure_class="syntax_error",
        diagnosis="Break everything",
        confidence=1.0,
        root_cause="N/A",
        changes=[
            CodeChangeTarget(
                operation="modify",
                file_path="app.py",
                reason="Bad fix",
                new_content="def func(:: syntax error",
                changes_description=""
            )
        ],
        expected_effect="",
    )
    
    mock_tester.run_tests.return_value = StructuredTestReport(
        workspace_id=ws_id,
        status="failed",
        framework="pytest",
        tests_selected=[],
        execution=TestExecutionResult(exit_code=1, duration_ms=10, tests_failed=5), # Worsened from 1 to 5
        failures=[],
        output="5 failed"
    )
    
    initial_test_result = {
        "workspace_id": ws_id,
        "status": "failed",
        "framework": "pytest",
        "tests_selected": [],
        "execution": {"exit_code": 1, "duration_ms": 10, "tests_failed": 1, "tests_passed": 0, "tests_run": 1, "tests_skipped": 0},
        "failures": [],
        "output": "1 failed"
    }
    
    response = client.post("/api/agents/debugger", json={
        "workspace_id": ws_id,
        "repository": "facebook/react",
        "task": "task",
        "test_result": initial_test_result,
        "retry_count": 0
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "debugging_failed" # Loop breaks because tests worsened
    assert data["attempts"] == 1
    assert "Rolled back attempt" in data["warnings"][0]
    
    # Assert file was rolled back
    assert (tmp_path / "app.py").read_text() == "def func(): pass"
    
@patch("agents.debugger.PromptOrchestrator")
@patch("agents.debugger.tester_agent")
def test_debugger_max_retries(mock_tester, mock_orchestrator, tmp_path):
    ws_id = "nexus_workspace_debug_max"
    workspace_manager.workspaces[ws_id] = str(tmp_path)
    (tmp_path / "app.py").write_text("def a(): pass")
    
    from models.debugger import StructuredDebuggerResponse, CodeChangeTarget
    from models.tester import StructuredTestReport, TestExecutionResult
    
    # Returns same failure count, different diagnosis to avoid repeated_failure early exit
    side_effects_orchestrator = [
        StructuredDebuggerResponse(failure_class="logic", diagnosis="A", confidence=1, root_cause="", expected_effect="", changes=[CodeChangeTarget(operation="modify", file_path="app.py", reason="", new_content="A", changes_description="")]),
        StructuredDebuggerResponse(failure_class="logic", diagnosis="B", confidence=1, root_cause="", expected_effect="", changes=[CodeChangeTarget(operation="modify", file_path="app.py", reason="", new_content="B", changes_description="")]),
        StructuredDebuggerResponse(failure_class="logic", diagnosis="C", confidence=1, root_cause="", expected_effect="", changes=[CodeChangeTarget(operation="modify", file_path="app.py", reason="", new_content="C", changes_description="")]),
    ]
    mock_orchestrator.run_debugger.side_effect = side_effects_orchestrator
    
    mock_tester.run_tests.return_value = StructuredTestReport(
        workspace_id=ws_id,
        status="failed",
        framework="pytest",
        tests_selected=[],
        execution=TestExecutionResult(exit_code=1, duration_ms=10, tests_failed=1), # Never worsens, never passes
        failures=[],
        output="1 failed"
    )
    
    initial_test_result = {
        "workspace_id": ws_id,
        "status": "failed",
        "framework": "pytest",
        "tests_selected": [],
        "execution": {"exit_code": 1, "duration_ms": 10, "tests_failed": 1, "tests_passed": 0, "tests_run": 1, "tests_skipped": 0},
        "failures": [],
        "output": "1 failed"
    }
    
    response = client.post("/api/agents/debugger", json={
        "workspace_id": ws_id,
        "repository": "facebook/react",
        "task": "task",
        "test_result": initial_test_result,
        "retry_count": 0
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "max_retries_reached"
    assert data["attempts"] == 3
