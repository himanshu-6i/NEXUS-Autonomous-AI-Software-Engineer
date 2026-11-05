from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import logging
from dotenv import load_dotenv

load_dotenv()

from api.ai import router as ai_router
from api.github import router as github_router
from api.retrieval import router as retrieval_router
from api.planner import router as planner_router
from api.coder import router as coder_router
from api.tester import router as tester_router
from api.debugger import router as debugger_router
from api.reviewer import router as reviewer_router
from api.pr import router as pr_router
from api.executions import router as executions_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="NEXUS AI Software Engineering Platform",
    description="API for NEXUS agentic workflow",
    version="0.1.0",
)

# CORS configuration
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler for safe 500 errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "error": "An unexpected error occurred."}
    )

app.include_router(ai_router)
app.include_router(github_router)
app.include_router(retrieval_router)
app.include_router(planner_router)
app.include_router(coder_router)
app.include_router(tester_router)
app.include_router(debugger_router)
app.include_router(reviewer_router)
app.include_router(pr_router)
app.include_router(executions_router)

class HealthResponse(BaseModel):
    status: str
    environment: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for Docker and Cloud Run.
    """
    return {
        "status": "ok",
        "environment": os.getenv("ENVIRONMENT", "development")
    }
