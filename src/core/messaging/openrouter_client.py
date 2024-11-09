"""OpenRouter API client for model interactions with event monitoring."""

import os
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List
from ..settings.config import settings
from ...utils.event_bus import EventBus
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

class OpenRouterClient:
    """Client for interacting with OpenRouter API with event monitoring."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        """Initialize OpenRouter client with API key, base URL, and event bus."""
        try:
            logger.info("Initializing OpenRouter client")
            self.api_key = settings.api_key
            if not self.api_key:
                logger.error("OpenRouter API key not configured in settings")
                raise ValueError("OpenRouter API key not configured in settings")

            self.base_url = "https://openrouter.ai/api/v1"
            self.event_bus = event_bus
            self.max_retries = 3
            self.retry_delay = 1  # seconds

            logger.debug("Fetching available models")
            self.available_models = self._fetch_available_models()
            logger.info(f"OpenRouter client initialized successfully with {len(self.available_models)} available models")

        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter client: {str(e)}", exc_info=True)
            raise

    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event if event bus is configured."""
        try:
            if self.event_bus:
                logger.debug(f"Emitting event: {event_type}")
                self.event_bus.emit(event_type, data)
                logger.debug(f"Event {event_type} emitted successfully")
            else:
                logger.debug("Event bus not configured, skipping event emission")
        except Exception as e:
            logger.error(f"Failed to emit event {event_type}: {str(e)}", exc_info=True)

    def _fetch_available_models(self) -> Dict[str, Any]:
        """Fetch available models from OpenRouter API with event tracking."""
        start_time = time.time()
        try:
            logger.info("Fetching available models from OpenRouter API")
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
            models = response.json()

            logger.info(f"Successfully fetched {len(models)} models in {duration:.2f}s")
            self._emit_event('api_call_complete', {
                'operation': 'fetch_models',
                'duration': duration,
                'status': 'success',
                'model_count': len(models),
                'timestamp': datetime.utcnow().isoformat()
            })

            return models

        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            error_msg = f"Failed to fetch available models: {str(e)}"
            logger.error(error_msg, exc_info=True)

            self._emit_event('api_call_error', {
                'operation': 'fetch_models',
                'error': str(e),
                'duration': duration,
                'timestamp': datetime.utcnow().isoformat()
            })

            raise RuntimeError(error_msg)

    def get_available_models(self) -> Dict[str, Any]:
        """Get list of available models."""
        try:
            logger.debug("Retrieving available models")
            return self.available_models
        except Exception as e:
            logger.error(f"Error retrieving available models: {str(e)}", exc_info=True)
            raise

    def _calculate_tokens(self, response: Dict[str, Any]) -> Dict[str, int]:
        """Calculate token usage from response."""
        try:
            logger.debug("Calculating token usage from response")
            usage = response.get('usage', {})
            tokens = {
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0)
            }
            logger.debug(f"Token usage calculated: {tokens}")
            return tokens
        except Exception as e:
            logger.error(f"Error calculating token usage: {str(e)}", exc_info=True)
            raise

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "anthropic/claude-3-opus",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send a chat completion request to OpenRouter API with monitoring."""
        try:
            logger.info(f"Initiating chat completion request with model {model}")
            logger.debug(f"Request parameters - Temperature: {temperature}, Max tokens: {max_tokens}")

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
                    logger.debug(f"Attempt {retries + 1}/{self.max_retries + 1}")
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

                    logger.info(
                        f"Chat completion successful - Duration: {duration:.2f}s, "
                        f"Tokens: {token_usage['total_tokens']}"
                    )

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

                    logger.warning(
                        f"Request failed (attempt {retries}/{self.max_retries + 1}): {str(e)}",
                        exc_info=True
                    )

                    self._emit_event('api_call_error', {
                        'operation': 'chat_completion',
                        'model': model,
                        'error': str(e),
                        'duration': duration,
                        'retry_count': retries,
                        'timestamp': datetime.utcnow().isoformat()
                    })

                    if retries <= self.max_retries:
                        delay = self.retry_delay * retries
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)  # Exponential backoff
                        continue

                    error_msg = f"Failed to get chat completion after {retries} retries: {e}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

        except Exception as e:
            logger.error(f"Error in chat completion: {str(e)}", exc_info=True)
            raise

    def validate_model(self, model: str) -> bool:
        """Validate if a model is available."""
        try:
            logger.debug(f"Validating model: {model}")
            is_valid = model in [m.get('id') for m in self.available_models.get('data', [])]
            if is_valid:
                logger.debug(f"Model {model} is valid")
            else:
                logger.warning(f"Model {model} is not available")
            return is_valid
        except Exception as e:
            logger.error(f"Error validating model: {str(e)}", exc_info=True)
            raise

    def get_model_info(self, model: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific model."""
        try:
            logger.debug(f"Retrieving information for model: {model}")
            for model_info in self.available_models.get('data', []):
                if model_info.get('id') == model:
                    logger.debug(f"Found information for model {model}")
                    return model_info
            logger.warning(f"No information found for model {model}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving model information: {str(e)}", exc_info=True)
            raise
