import os
import logging
import time
from typing import Optional, Type, TypeVar, Dict, Any
from google import genai
from google.genai import errors
from pydantic import BaseModel

# Initialize basic logging
logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class LLMServiceError(Exception):
    """Custom exception for LLM service errors."""
    pass

class LLMConfigurationError(LLMServiceError):
    """Exception raised when the LLM service is improperly configured (e.g., missing API key)."""
    pass

class LLMService:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("GEMINI_API_KEY is not set in environment variables.")
        else:
            self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name

    def _check_config(self):
        if not self.api_key:
            raise LLMConfigurationError("Gemini API key is missing. Please set GEMINI_API_KEY environment variable.")

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, temperature: float = 0.7) -> str:
        self._check_config()
        
        start_time = time.time()
        logger.info(f"Gemini request started: model={self.model_name}")
        
        config = {"temperature": temperature}
        if system_instruction:
            config["system_instruction"] = system_instruction
            
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            latency = time.time() - start_time
            logger.info(f"Gemini request success. Latency: {latency:.2f}s")
            
            if not response.text:
                raise LLMServiceError("Received empty response from Gemini API.")
                
            return response.text
        except errors.APIError as e:
            latency = time.time() - start_time
            logger.error(f"Gemini request failed. Latency: {latency:.2f}s. Error: {str(e)}")
            raise LLMServiceError(f"Gemini API Error: {str(e)}")
        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"Gemini request failed with unexpected error. Latency: {latency:.2f}s. Error: {str(e)}")
            raise LLMServiceError(f"Unexpected error calling Gemini: {str(e)}")

    def generate_structured(
        self, 
        prompt: str, 
        response_schema: Type[T], 
        system_instruction: Optional[str] = None,
        temperature: float = 0.2
    ) -> T:
        self._check_config()
        
        start_time = time.time()
        logger.info(f"Gemini structured request started: model={self.model_name}, schema={response_schema.__name__}")
        
        config = {
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_schema": response_schema
        }
        if system_instruction:
            config["system_instruction"] = system_instruction
            
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            latency = time.time() - start_time
            logger.info(f"Gemini structured request success. Latency: {latency:.2f}s")
            
            # Use the SDK's built-in parsed parsing, or fallback to json parsing if needed
            # For google-genai 0.3+, the parsed object should be available if we provided schema
            if hasattr(response, 'parsed') and response.parsed:
                return response.parsed
                
            # Fallback if parsed is not set directly
            if not response.text:
                raise LLMServiceError("Received empty response from Gemini API.")
                
            # The google-genai SDK when given response_schema should return JSON text
            return response_schema.model_validate_json(response.text)
            
        except errors.APIError as e:
            latency = time.time() - start_time
            logger.error(f"Gemini structured request failed. Latency: {latency:.2f}s. Error: {str(e)}")
            raise LLMServiceError(f"Gemini API Error: {str(e)}")
        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"Gemini structured request failed with unexpected error. Latency: {latency:.2f}s. Error: {str(e)}")
            raise LLMServiceError(f"Failed to generate structured output: {str(e)}")

# Singleton instance for the application to use
llm_service = LLMService()
