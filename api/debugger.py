import logging
from fastapi import APIRouter, HTTPException
from models.debugger import DebuggerRequest, DebuggerResponse
from agents.debugger import debugger_agent
from workspace.manager import WorkspaceError
from services.llm_service import LLMServiceError

from api.execution_utils import update_execution_state, append_execution_event

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)

@router.post("/debugger", response_model=DebuggerResponse)
async def run_debugger_agent(request: DebuggerRequest):
    """
    Executes the Debugger Agent loop safely.
    """
    if not request.workspace_id:
        raise HTTPException(status_code=400, detail="Workspace ID is required")
        
    try:
        if request.execution_id:
            update_execution_state(request.execution_id, "debugging", "in_progress")
            append_execution_event(request.execution_id, "debug_started", "debugging")
            
        result = debugger_agent.run_debug_loop(request)
        
        if request.execution_id:
            from services.firestore_service import firestore_service
            # We want to append to debug_history, but since we get the full list in result.attempt_history, we can just set it
            update_execution_state(request.execution_id, "debugging", result.status, {"debug_history": [a.model_dump() for a in result.attempt_history]})
            append_execution_event(request.execution_id, "debug_completed", "debugging", {"status": result.status, "attempts": len(result.attempt_history)})
            
        return result
    except WorkspaceError as e:
        logger.error(f"Workspace Error during debugging: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except LLMServiceError as e:
        logger.error(f"LLM Error during debugging: {str(e)}")
        raise HTTPException(status_code=502, detail=f"AI Service Error: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during debugging")
        raise HTTPException(status_code=500, detail="Internal Server Error")
