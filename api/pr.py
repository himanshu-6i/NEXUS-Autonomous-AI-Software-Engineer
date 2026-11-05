import logging
from fastapi import APIRouter, HTTPException
from models.pr import PRRequest, PRResponse
from agents.pr import pr_agent, PRAgentError
from workspace.manager import WorkspaceError
from services.github_service import GitHubServiceError

from api.execution_utils import update_execution_state, append_execution_event

router = APIRouter(prefix="/api/github", tags=["github"])
logger = logging.getLogger(__name__)

@router.post("/pr", response_model=PRResponse)
async def create_pull_request(request: PRRequest):
    """
    Creates a dedicated branch, commit, and Pull Request.
    """
    if not request.workspace_id:
        raise HTTPException(status_code=400, detail="Workspace ID is required")
        
    try:
        if request.execution_id:
            append_execution_event(request.execution_id, "github_pr_creation_started", "pr_creation")
            
        result = pr_agent.run_pr_workflow(request)
        
        if request.execution_id:
            update_execution_state(request.execution_id, "completed", "pr_created", {
                "nexus_branch": result.branch_name,
                "commit_sha": result.commit_sha,
                "pr_url": result.pr_url
            })
            append_execution_event(request.execution_id, "github_pr_created", "pr_creation", {"pr_url": result.pr_url})
            
        return result
    except (WorkspaceError, PRAgentError) as e:
        if request.execution_id:
            append_execution_event(request.execution_id, "github_pr_creation_failed", "pr_creation", {"error": str(e)})
        logger.error(f"Validation Error during PR creation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except GitHubServiceError as e:
        logger.error(f"GitHub API Error during PR creation: {str(e)}")
        raise HTTPException(status_code=502, detail=f"GitHub Error: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during PR creation")
        raise HTTPException(status_code=500, detail="Internal Server Error")
