from typing import List
from pydantic import BaseModel, Field

class RetrieveRequest(BaseModel):
    repository: str = Field(..., description="GitHub repository URL or identifier")
    query: str = Field(..., description="The query to search the repository for")
    top_k: int = Field(5, description="Number of results to return", ge=1, le=20)

class RetrievalResultModel(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    score: float
    content: str

class RetrieveResponse(BaseModel):
    query: str
    results: List[RetrievalResultModel]
