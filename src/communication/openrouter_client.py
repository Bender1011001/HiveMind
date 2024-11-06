"""OpenRouter API client for model interactions with event monitoring."""

import os
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List
from ..settings.settings import settings
from ..utils.event_bus import EventBus

class OpenRouterClient:
    """Client for interacting with OpenRouter API with event monitoring."""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """Initialize OpenRouter client with API key, base URL, and event bus."""
        self.api_key = settings.api_key
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured in settings")
            
        self.base_url = "https://openrouter.ai/api/v1"
        self.event_bus = event_bus
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self.available_models = self._fetch_available_models()
        
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event if event bus is configured."""
        if self.event_bus:
            self.event_bus.emit(event_type, data)
            
    def _fetch_available_models(self) -> Dict[str, Any]:
        """Fetch available models from OpenRouter API with event tracking."""
        start_time = time.time()
        try:
            self._emit_event('api_call_start', {
                'operation': 'fetch_models',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            response = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            
            duration = time.time() - start_time
            self._emit_event('api_call_complete', {
                'operation': 'fetch_models',
                'duration': duration,
                'status': 'success',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return response.json()
        except Exception as e:
            duration = time.time() - start_time
            self._emit_event('api_call_error', {
                'operation': 'fetch_models',
                'error': str(e),
                'duration': duration,
                'timestamp': datetime.utcnow().isoformat()
            })
            raise RuntimeError(f"Failed to fetch available models: {e}")
            
    def get_available_models(self) -> Dict[str, Any]:
        """Get list of available models."""
        return self.available_models
        
    def _calculate_tokens(self, response: Dict[str, Any]) -> Dict[str, int]:
        """Calculate token usage from response."""
        usage = response.get('usage', {})
        return {
            'prompt_tokens': usage.get('prompt_tokens', 0),
            'completion_tokens': usage.get('completion_tokens', 0),
            'total_tokens': usage.get('total_tokens', 0)
        }
        
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "anthropic/claude-3-opus",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send a chat completion request to OpenRouter API with monitoring."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/yourusername/hivemind",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            data["max_tokens"] = max_tokens
            
        retries = 0
        while retries <= self.max_retries:
            start_time = time.time()
            try:
                self._emit_event('api_call_start', {
                    'operation': 'chat_completion',
                    'model': model,
                    'message_count': len(messages),
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data
                )
                response.raise_for_status()
                result = response.json()
                
                duration = time.time() - start_time
                token_usage = self._calculate_tokens(result)
                
                self._emit_event('api_call_complete', {
                    'operation': 'chat_completion',
                    'model': model,
                    'duration': duration,
                    'token_usage': token_usage,
                    'status': 'success',
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                return result
                
            except requests.exceptions.RequestException as e:
                duration = time.time() - start_time
                retries += 1
                
                self._emit_event('api_call_error', {
                    'operation': 'chat_completion',
                    'model': model,
                    'error': str(e),
                    'duration': duration,
                    'retry_count': retries,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                if retries <= self.max_retries:
                    time.sleep(self.retry_delay * retries)  # Exponential backoff
                    continue
                    
                raise RuntimeError(f"Failed to get chat completion after {retries} retries: {e}")
