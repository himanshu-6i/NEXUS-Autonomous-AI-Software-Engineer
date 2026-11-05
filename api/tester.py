import logging
from fastapi import APIRouter, HTTPException
from models.tester import TesterRequest, StructuredTestReport
from agents.tester import tester_agent
from workspace.manager import WorkspaceError
from services.llm_service import LLMServiceError

from api.execution_utils import update_execution_state, append_execution_event

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)

@router.post("/tester", response_model=StructuredTestReport)
async def run_test_agent(request: TesterRequest):
    """
    Executes the Test Agent inside a controlled workspace sandbox.
    """
    if not request.workspace_id:
        raise HTTPException(status_code=400, detail="Workspace ID is required")
        
    try:
        if request.execution_id:
            update_execution_state(request.execution_id, "testing", "in_progress")
            append_execution_event(request.execution_id, "testing_started", "testing")
            
        result = tester_agent.run_tests(request)
        
        if request.execution_id:
            update_execution_state(request.execution_id, "testing", result.status, {"test_result": result.model_dump()})
            append_execution_event(request.execution_id, "testing_completed", "testing", {"status": result.status})
            
        return result
    except WorkspaceError as e:
        logger.error(f"Workspace Error during testing: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except LLMServiceError as e:
        logger.error(f"LLM Error during testing: {str(e)}")
        raise HTTPException(status_code=502, detail=f"AI Service Error: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during testing")
        raise HTTPException(status_code=500, detail="Internal Server Error")
