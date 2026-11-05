from typing import List, Optional
from pydantic import BaseModel, Field

class AnalyzeRepoRequest(BaseModel):
    repository: str = Field(..., description="GitHub repository URL or 'owner/repo' identifier")

class RepoMetadata(BaseModel):
    name: str
    owner: str
    default_branch: str
    description: Optional[str] = None
    visibility: str
    primary_language: Optional[str] = None
    url: str
    latest_commit_sha: Optional[str] = None

class AnalyzeRepoResponse(BaseModel):
    metadata: RepoMetadata
    structure: List[str]
    analysis: dict  # Will be StructuredRepoAnalysisResponse
