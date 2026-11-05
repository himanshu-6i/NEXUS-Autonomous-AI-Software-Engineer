import logging
from fastapi import APIRouter, HTTPException
from models.planner import PlannerRequest, StructuredPlanResponse
from agents.planner import planner_agent
from services.github_service import GitHubServiceError
from services.llm_service import LLMServiceError

from api.execution_utils import update_execution_state, append_execution_event

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)

@router.post("/planner", response_model=StructuredPlanResponse)
async def run_planner_agent(request: PlannerRequest):
    """
    Executes the Planner Agent to generate a structured implementation plan.
    """
    if not request.task.strip():
        raise HTTPException(status_code=400, detail="Task cannot be empty")
        
    try:
        if request.execution_id:
            update_execution_state(request.execution_id, "planning", "in_progress")
            append_execution_event(request.execution_id, "planning_started", "planning")
            
        result = planner_agent.plan_task(request)
        
        if request.execution_id:
            update_execution_state(request.execution_id, "planning", "completed", {"planner_result": result.model_dump()})
            append_execution_event(request.execution_id, "planning_completed", "planning")
            
        return result
    except GitHubServiceError as e:
        logger.error(f"GitHub Error during planning: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except LLMServiceError as e:
        logger.error(f"LLM Error during planning: {str(e)}")
        raise HTTPException(status_code=502, detail=f"AI Service Error: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during planning")
        raise HTTPException(status_code=500, detail="Internal Server Error")
