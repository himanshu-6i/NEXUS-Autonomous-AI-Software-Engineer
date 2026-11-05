from typing import List
from pydantic import BaseModel, Field

class TestPromptRequest(BaseModel):
    prompt: str = Field(..., description="The prompt to test against the Gemini model.")

class StructuredTestResponse(BaseModel):
    summary: str = Field(..., description="A short summary of the explanation.")
    steps: List[str] = Field(..., description="A list of steps explaining the concept.")
    risks: List[str] = Field(..., description="A list of risks or pitfalls related to the topic.")
