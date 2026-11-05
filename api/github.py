import logging
from fastapi import APIRouter, HTTPException
from models.github import AnalyzeRepoRequest, AnalyzeRepoResponse
from services.github_service import github_service, GitHubServiceError
from services.prompt_orchestrator import PromptOrchestrator
from services.llm_service import LLMServiceError

router = APIRouter(prefix="/api/github", tags=["github"])
logger = logging.getLogger(__name__)

@router.post("/analyze", response_model=AnalyzeRepoResponse)
async def analyze_repo(request: AnalyzeRepoRequest):
    """
    Analyzes a GitHub repository by fetching metadata and tree, then invoking Gemini for an architecture summary.
    """
    try:
        logger.info(f"Analyzing repository: {request.repository}")
        
        # 1. Fetch metadata
        metadata = github_service.get_repo_metadata(request.repository)
        
        # 2. Fetch tree
        tree = github_service.get_repo_tree(request.repository, metadata.default_branch)
        
        # 3. Analyze with Gemini
        analysis = PromptOrchestrator.run_repo_analysis(
            repo_name=metadata.name,
            repo_metadata=metadata.model_dump(),
            repo_tree=tree
        )
        
        return AnalyzeRepoResponse(
            metadata=metadata,
            structure=tree[:100],  # Return up to 100 paths for frontend display
            analysis=analysis.model_dump()
        )
        
    except GitHubServiceError as e:
        logger.error(f"GitHub Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except LLMServiceError as e:
        logger.error(f"LLM Error: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to generate analysis: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during repo analysis")
        raise HTTPException(status_code=500, detail="Internal Server Error")
