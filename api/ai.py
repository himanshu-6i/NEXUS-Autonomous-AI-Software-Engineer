from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models.llm import TestPromptRequest, StructuredTestResponse
from services.prompt_orchestrator import PromptOrchestrator
from services.llm_service import LLMConfigurationError, LLMServiceError

router = APIRouter(prefix="/api/ai", tags=["ai"])

@router.post("/test", response_model=StructuredTestResponse)
async def test_ai_endpoint(request: TestPromptRequest):
    """
    Test endpoint for Gemini integration.
    Validates the prompt and returns a structured JSON response from Gemini.
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
        
    try:
        response = PromptOrchestrator.run_test_prompt(request.prompt)
        return response
    except LLMConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMServiceError as e:
        raise HTTPException(status_code=502, detail=f"AI Service Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
