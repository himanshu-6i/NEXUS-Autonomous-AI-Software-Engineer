import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Must set the environment variable before importing main
os.environ["GEMINI_API_KEY"] = "mock_api_key"

from api.main import app
from services.llm_service import LLMConfigurationError, LLMServiceError

client = TestClient(app)

def test_missing_prompt():
    response = client.post("/api/ai/test", json={"prompt": " "})
    assert response.status_code == 400
    assert "Prompt cannot be empty" in response.json()["detail"]

@patch("services.llm_service.genai.Client")
def test_successful_structured_response(mock_client_class):
    # Setup mock
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Mock generate_content response
    mock_response = MagicMock()
    mock_response.text = '{"summary": "Test Summary", "steps": ["Step 1"], "risks": ["Risk 1"]}'
    
    # Set the parsed property to a mock object if using the new SDK feature
    from models.llm import StructuredTestResponse
    mock_response.parsed = StructuredTestResponse(
        summary="Test Summary", 
        steps=["Step 1"], 
        risks=["Risk 1"]
    )
    
    mock_client.models.generate_content.return_value = mock_response
    
    # Needs to be re-initialized because the module already initialized llm_service singleton
    from services.llm_service import llm_service
    llm_service.client = mock_client
    
    response = client.post("/api/ai/test", json={"prompt": "Explain software repository"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Test Summary"
    assert "Step 1" in data["steps"]
    assert "Risk 1" in data["risks"]

@patch("services.llm_service.genai.Client")
def test_llm_service_error_handling(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    from google.genai import errors
    mock_client.models.generate_content.side_effect = Exception("Mock API Error")
    
    from services.llm_service import llm_service
    llm_service.client = mock_client
    
    response = client.post("/api/ai/test", json={"prompt": "Cause error"})
    
    assert response.status_code == 502
    assert "Mock API Error" in response.json()["detail"]
