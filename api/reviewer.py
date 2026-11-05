import logging
from fastapi import APIRouter, HTTPException
from models.reviewer import ReviewerRequest, ReviewerResponse
from agents.reviewer import reviewer_agent
from workspace.manager import WorkspaceError
from services.llm_service import LLMServiceError

from api.execution_utils import update_execution_state, append_execution_event

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)

@router.post("/reviewer", response_model=ReviewerResponse)
async def run_reviewer_agent(request: ReviewerRequest):
    """
    Executes the Reviewer Agent to evaluate a workspace's diff.
    """
    if not request.workspace_id:
        raise HTTPException(status_code=400, detail="Workspace ID is required")
        
    try:
        if request.execution_id:
            update_execution_state(request.execution_id, "reviewing", "in_progress")
            append_execution_event(request.execution_id, "review_started", "reviewing")
            
        result = reviewer_agent.run_review(request)
        
        if request.execution_id:
            status = "ready_for_pr" if result.verdict == "approve" else "blocked"
            update_execution_state(request.execution_id, "reviewing", status, {"review_result": result.model_dump()})
            append_execution_event(request.execution_id, "review_completed", "reviewing", {"verdict": result.verdict})
            
        return result
    except WorkspaceError as e:
        logger.error(f"Workspace Error during review: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except LLMServiceError as e:
        logger.error(f"LLM Error during review: {str(e)}")
        raise HTTPException(status_code=502, detail=f"AI Service Error: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during review")
        raise HTTPException(status_code=500, detail="Internal Server Error")
