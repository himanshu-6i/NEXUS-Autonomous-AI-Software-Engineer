import logging
from fastapi import APIRouter, HTTPException
from models.coder import CodingRequest, CodingResponse
from agents.coder import coding_agent
from services.github_service import GitHubServiceError
from services.llm_service import LLMServiceError
from workspace.manager import WorkspaceError

from api.execution_utils import update_execution_state, append_execution_event

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)

@router.post("/coder", response_model=CodingResponse)
async def run_coding_agent(request: CodingRequest):
    """
    Executes the Coding Agent to safely apply changes inside a workspace.
    """
    if not request.task.strip():
        raise HTTPException(status_code=400, detail="Task cannot be empty")
        
    try:
        if request.execution_id:
            update_execution_state(request.execution_id, "coding", "in_progress")
            append_execution_event(request.execution_id, "coding_started", "coding")
            
        result = coding_agent.run_task(request)
        
        if request.execution_id:
            update_execution_state(request.execution_id, "coding", "completed", {"coding_result": result.model_dump()})
            append_execution_event(request.execution_id, "coding_completed", "coding")
            
        return result
    except (GitHubServiceError, WorkspaceError) as e:
        logger.error(f"Workspace/GitHub Error during coding: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except LLMServiceError as e:
        logger.error(f"LLM Error during coding: {str(e)}")
        raise HTTPException(status_code=502, detail=f"AI Service Error: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during coding")
        raise HTTPException(status_code=500, detail="Internal Server Error")
