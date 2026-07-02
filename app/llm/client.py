# app/llm/client.py
import json
import time
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from ..config import config
from ..logger import get_logger
from ..exceptions import LLMError

logger = get_logger(__name__)


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate response from LLM"""
        pass
    
    @abstractmethod
    def extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response"""
        pass


class GeminiClient(BaseLLMClient):
    """Google Gemini API client"""
    
    def __init__(self, model: str = "gemini-2.0-flash-exp"):
        self.model_name = model
        self._client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Gemini client"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.llm_api_key)
            self._client = genai.GenerativeModel(self.model_name)
            logger.info(f"Gemini client initialized with model: {self.model_name}")
        except ImportError:
            logger.error("google-generativeai not installed")
            raise LLMError("google-generativeai is required for Gemini client")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            raise LLMError(f"Gemini initialization failed: {e}")
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate response from Gemini"""
        if self._client is None:
            logger.warning("Gemini client not available, using fallback")
            return self._fallback_response(prompt)
        
        full_prompt = self._build_prompt(prompt, system_prompt)
        
        try:
            response = self._client.generate_content(full_prompt)
            if response and response.text:
                return response.text
            else:
                logger.warning("Empty response from Gemini")
                return self._fallback_response(prompt)
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return self._fallback_response(prompt)
    
    def _build_prompt(self, prompt: str, system_prompt: Optional[str]) -> str:
        """Build full prompt with system instructions"""
        if system_prompt:
            return f"{system_prompt}\n\n{prompt}"
        return prompt
    
    def extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from Gemini response"""
        if not text:
            return None
        
        try:
            # Try to find JSON block
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
        except Exception as e:
            logger.debug(f"Failed to extract JSON: {e}")
        return None
    
    def _fallback_response(self, prompt: str) -> str:
        """Generate fallback response when LLM is unavailable"""
        # Detect intent from prompt
        if "classify" in prompt.lower():
            return '{"intent": "clarify", "reason": "LLM unavailable, defaulting to clarify"}'
        
        if "extract" in prompt.lower():
            return '{"role": null, "seniority": null, "competencies": [], "test_types": []}'
        
        # Default fallback
        return "I'm here to help you find the right SHL assessments. Could you tell me more about the role you're hiring for?"


class LLMClient(BaseLLMClient):
    """Factory class for LLM clients"""
    
    def __init__(self):
        self.provider = config.llm_provider
        self._client: Optional[BaseLLMClient] = None
        self._initialize()
    
    def _initialize(self):
        """Initialize the appropriate LLM client"""
        try:
            if self.provider == "gemini":
                self._client = GeminiClient(config.llm_model)
            else:
                logger.warning(f"Provider {self.provider} not supported, using fallback")
                self._client = GeminiClient("gemini-2.0-flash-exp")  # Default fallback
        except Exception as e:
            logger.error(f"LLM client initialization failed: {e}")
            self._client = None
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate response from LLM"""
        if self._client is None:
            logger.warning("LLM client not available, using fallback")
            return self._fallback_response(prompt)
        
        return self._client.generate(prompt, system_prompt)
    
    def extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response"""
        if self._client is None:
            return None
        return self._client.extract_json(text)
    
    def _fallback_response(self, prompt: str) -> str:
        """Generate fallback response"""
        if "classify" in prompt.lower():
            return '{"intent": "clarify", "reason": "LLM unavailable"}'
        if "extract" in prompt.lower():
            return '{"role": null, "seniority": null, "competencies": [], "test_types": []}'
        return "I'm here to help with SHL assessments. What role are you hiring for?"