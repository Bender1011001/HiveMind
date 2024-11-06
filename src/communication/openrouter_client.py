"""OpenRouter API client for model interactions."""

import os
import json
import requests
from typing import Dict, Any, Optional
from ..settings.settings import settings

class OpenRouterClient:
    """Client for interacting with OpenRouter API."""
    
    def __init__(self):
        """Initialize OpenRouter client with API key and base URL."""
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
            
        self.base_url = "https://openrouter.ai/api/v1"
        self.available_models = self._fetch_available_models()
        
    def _fetch_available_models(self) -> Dict[str, Any]:
        """Fetch available models from OpenRouter API."""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch available models: {e}")
            
    def get_available_models(self) -> Dict[str, Any]:
        """Get list of available models."""
        return self.available_models
        
    def chat_completion(
        self,
        messages: list,
        model: str = "anthropic/claude-3-opus",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send a chat completion request to OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/yourusername/hivemind",  # Replace with your project URL
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            data["max_tokens"] = max_tokens
            
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to get chat completion: {e}")
