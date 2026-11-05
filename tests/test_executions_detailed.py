import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app
from api.execution_utils import update_execution_state, append_execution_event, StateTransitionError, truncate_large_data, redact_secrets
from services.firestore_service import firestore_service

client = TestClient(app)

def test_invalid_state_transition():
    # create new
    res = client.post("/api/executions", json={"repository": "test/repo", "task": "test task"})
    exec_id = res.json()["execution_id"]
    
    # created -> planning is valid
    update_execution_state(exec_id, "planning", "in_progress")
    
    # planning -> reviewing is INVALID (skipping coding/testing)
    with pytest.raises(StateTransitionError):
        update_execution_state(exec_id, "reviewing", "in_progress")
        
def test_idempotent_execution_updates():
    res = client.post("/api/executions", json={"repository": "test/repo", "task": "test task"})
    exec_id = res.json()["execution_id"]
    
    # Calling the same state update multiple times should not crash and should work (idempotency in states like planning -> planning)
    update_execution_state(exec_id, "planning", "in_progress")
    update_execution_state(exec_id, "planning", "completed")
    
    exec_data = client.get(f"/api/executions/{exec_id}").json()
    assert exec_data["current_stage"] == "planning"
    assert exec_data["status"] == "completed"
    
def test_firestore_failure_handled_safely():
    res = client.post("/api/executions", json={"repository": "test/repo", "task": "test task"})
    exec_id = res.json()["execution_id"]
    
    with patch("services.firestore_service.firestore_service.update_execution", side_effect=Exception("DB DOWN")):
        # Should not raise exception
        update_execution_state(exec_id, "planning", "in_progress")
        
    with patch("services.firestore_service.firestore_service.append_event", side_effect=Exception("DB DOWN")):
        # Should not raise exception
        append_execution_event(exec_id, "test_event", "testing")

def test_secret_redaction_in_persistence():
    raw_metadata = {
        "user_token": "ghp_1234567890abcdefGHIJKLmnopqrstuvwxyz",
        "aws_secret_key": "some_secret_key_here",
        "authorization": "Bearer ya29.c.c0AY_VpZ...",
        "nested": {
            "api_key": "12345"
        },
        "safe_field": "hello world"
    }
    
    sanitized = redact_secrets(raw_metadata)
    assert sanitized["user_token"] == "***REDACTED***"
    assert sanitized["aws_secret_key"] == "***REDACTED***"
    assert "ya29" not in sanitized["authorization"]
    assert sanitized["nested"]["api_key"] == "***REDACTED***"
    assert sanitized["safe_field"] == "hello world"

def test_large_data_truncation_in_persistence():
    large_string = "A" * 10000
    data = {
        "diff": large_string,
        "small": "hello"
    }
    
    truncated = truncate_large_data(data, max_string_len=5000)
    assert len(truncated["diff"]) < 6000
    assert "TRUNCATED" in truncated["diff"]
    assert truncated["small"] == "hello"


