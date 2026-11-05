import logging
from fastapi import APIRouter, HTTPException
from models.retrieval import RetrieveRequest, RetrieveResponse, RetrievalResultModel
from services.retrieval_service import retrieval_service
from services.github_service import GitHubServiceError

router = APIRouter(prefix="/api/repository", tags=["retrieval"])
logger = logging.getLogger(__name__)

@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_code(request: RetrieveRequest):
    """
    Retrieves top relevant code chunks from a repository based on a query.
    """
    if len(request.query) > 500:
        raise HTTPException(status_code=400, detail="Query too long (max 500 characters)")
        
    try:
        logger.info(f"Retrieving from {request.repository}: '{request.query}'")
        
        results = retrieval_service.retrieve(request.repository, request.query, request.top_k)
        
        response_results = [
            RetrievalResultModel(
                file_path=r.file_path,
                start_line=r.start_line,
                end_line=r.end_line,
                score=r.score,
                content=r.content
            )
            for r in results
        ]
        
        return RetrieveResponse(
            query=request.query,
            results=response_results
        )
        
    except GitHubServiceError as e:
        logger.error(f"GitHub Error during retrieval: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error during retrieval")
        raise HTTPException(status_code=500, detail="Internal Server Error")
