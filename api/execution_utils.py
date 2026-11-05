import logging
import re
import copy
from typing import Any, Dict
from models.execution import ExecutionEvent
from services.firestore_service import firestore_service

logger = logging.getLogger(__name__)

# Valid state transitions mapping
# current_stage -> list of valid next stages
VALID_TRANSITIONS = {
    "created": ["planning", "completed", "failed"],
    "planning": ["planning", "coding", "completed", "failed"],
    "coding": ["coding", "testing", "completed", "failed"],
    "testing": ["testing", "debugging", "reviewing", "completed", "failed"],
    "debugging": ["debugging", "testing", "reviewing", "completed", "failed"],
    "reviewing": ["reviewing", "completed", "failed"],
    "completed": ["completed"],
    "failed": ["failed", "planning", "coding"] # allow retry from failed
}

def redact_secrets(data: Any) -> Any:
    """Recursively redacts suspected secrets from nested structures."""
    if isinstance(data, dict):
        redacted_data = {}
        for k, v in data.items():
            k_lower = k.lower()
            if any(secret_kw in k_lower for secret_kw in ['key', 'token', 'secret', 'password', 'auth', 'credential']):
                redacted_data[k] = "***REDACTED***"
            else:
                redacted_data[k] = redact_secrets(v)
        return redacted_data
    elif isinstance(data, list):
        return [redact_secrets(item) for item in data]
    elif isinstance(data, str):
        # Quick inline redaction for potential keys
        sanitized = re.sub(r'(Bearer\s+)[A-Za-z0-9\-\._~\+/]+=*', r'\1***REDACTED***', data)
        sanitized = re.sub(r'(gh[p|o|u|s|r]_[A-Za-z0-9_]+)', r'***REDACTED_GITHUB_TOKEN***', sanitized)
        return sanitized
    return data

def truncate_large_data(data: Any, max_string_len: int = 5000) -> Any:
    """Recursively truncates oversized strings, particularly useful for massive diffs/code blobs."""
    if isinstance(data, dict):
        return {k: truncate_large_data(v, max_string_len) for k, v in data.items()}
    elif isinstance(data, list):
        return [truncate_large_data(item, max_string_len) for item in data]
    elif isinstance(data, str):
        if len(data) > max_string_len:
            return data[:max_string_len] + f"\n...[TRUNCATED: original length {len(data)}]..."
        return data
    return data

class StateTransitionError(Exception):
    pass

def enforce_state_transition(execution_id: str, new_stage: str) -> None:
    current_execution = firestore_service.get_execution(execution_id)
    if not current_execution:
        return # Cannot validate
    
    current_stage = current_execution.current_stage
    if current_stage not in VALID_TRANSITIONS:
        return
        
    if new_stage not in VALID_TRANSITIONS[current_stage]:
        raise StateTransitionError(f"Invalid transition from {current_stage} to {new_stage}")

def update_execution_state(execution_id: str, stage: str, status: str, updates: Dict[str, Any] = None):
    if not execution_id:
        return
        
    try:
        enforce_state_transition(execution_id, stage)
        
        final_updates = {"current_stage": stage, "status": status}
        if updates:
            # Deep copy to avoid mutating original objects passed by reference
            sanitized_updates = truncate_large_data(redact_secrets(copy.deepcopy(updates)))
            final_updates.update(sanitized_updates)
            
        firestore_service.update_execution(execution_id, final_updates)
    except StateTransitionError as e:
        logger.error(f"State transition error for {execution_id}: {e}")
        raise # Let API handle this explicitly
    except Exception as e:
        logger.error(f"Failed to update execution {execution_id}: {e}")

def append_execution_event(execution_id: str, event_type: str, stage: str, metadata: Dict[str, Any] = None):
    if not execution_id:
        return
        
    try:
        sanitized_meta = truncate_large_data(redact_secrets(copy.deepcopy(metadata or {})))
        event = ExecutionEvent(
            event_type=event_type,
            execution_id=execution_id,
            stage=stage,
            metadata=sanitized_meta
        )
        firestore_service.append_event(event)
    except Exception as e:
        logger.error(f"Failed to append event for {execution_id}: {e}")
