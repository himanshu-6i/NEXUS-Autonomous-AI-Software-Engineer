from typing import List, Optional
from pydantic import BaseModel, Field

class StructuredRepoAnalysisResponse(BaseModel):
    repository: str = Field(..., description="The repository name.")
    project_type: str = Field(..., description="The type of project (e.g., 'Web Application', 'Library', 'CLI Tool').")
    languages: List[str] = Field(..., description="Programming languages used in the repository.")
    frameworks: List[str] = Field(..., description="Frameworks and libraries detected.")
    structure: List[str] = Field(..., description="Important directories and their purpose.")
    entry_points: List[str] = Field(..., description="Likely entry points of the application (e.g., 'src/index.js', 'main.py').")
    test_frameworks: List[str] = Field(..., description="Testing frameworks detected.")
    package_managers: List[str] = Field(..., description="Package managers used (e.g., 'npm', 'pip', 'poetry').")
    important_files: List[str] = Field(..., description="Crucial configuration or documentation files.")
    architecture_summary: str = Field(..., description="A short summary of the likely software architecture.")
    detected_commands: List[str] = Field(..., description="Obvious development/build/test commands.")
    unknowns: List[str] = Field(..., description="Information that could not be determined.")
