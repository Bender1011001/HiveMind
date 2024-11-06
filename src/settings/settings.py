"""Configuration settings for the multi-agent system."""

import os
import json
from dataclasses import dataclass, asdict
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class ModelConfig:
    """Model configuration settings."""
    name: str
    provider: str
    description: str
    context_length: int
    cost_per_1k_tokens: float

@dataclass
class Settings:
    """System configuration settings."""
    
    # Model settings
    model_name: str = os.getenv("MODEL_NAME", "anthropic/claude-3-opus")
    api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    temperature: float = float(os.getenv("TEMPERATURE", "0.7"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "2048"))
    
    # Available models configuration
    available_models: List[ModelConfig] = None
    
    # MongoDB settings
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    
    # RabbitMQ settings
    rabbitmq_host: str = os.getenv("RABBITMQ_HOST", "localhost")
    rabbitmq_port: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    rabbitmq_user: str = os.getenv("RABBITMQ_USER", "guest")
    rabbitmq_password: str = os.getenv("RABBITMQ_PASSWORD", "guest")
    
    # Directory settings
    base_dir: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    shared_data_dir: str = os.path.join(base_dir, os.getenv("SHARED_DATA_DIR", "workspace/data"))
    shared_code_dir: str = os.path.join(base_dir, os.getenv("SHARED_CODE_DIR", "workspace/code"))
    shared_output_dir: str = os.path.join(base_dir, os.getenv("SHARED_OUTPUT_DIR", "workspace/output"))
    
    def __post_init__(self):
        """Create necessary directories after initialization."""
        os.makedirs(self.shared_data_dir, exist_ok=True)
        os.makedirs(self.shared_code_dir, exist_ok=True)
        os.makedirs(self.shared_output_dir, exist_ok=True)
        
        # Initialize default available models if none provided
        if self.available_models is None:
            self.available_models = [
                ModelConfig(
                    name="anthropic/claude-3-opus",
                    provider="Anthropic",
                    description="Most capable Claude model for complex tasks",
                    context_length=200000,
                    cost_per_1k_tokens=0.015
                ),
                ModelConfig(
                    name="anthropic/claude-3-sonnet",
                    provider="Anthropic",
                    description="Balanced Claude model for most tasks",
                    context_length=200000,
                    cost_per_1k_tokens=0.003
                ),
                ModelConfig(
                    name="google/gemini-pro",
                    provider="Google",
                    description="Advanced model for various tasks",
                    context_length=100000,
                    cost_per_1k_tokens=0.001
                ),
                ModelConfig(
                    name="openai/gpt-4-turbo",
                    provider="OpenAI",
                    description="Latest GPT-4 model with broad capabilities",
                    context_length=128000,
                    cost_per_1k_tokens=0.01
                )
            ]
    
    def save(self, config_file: Optional[str] = None):
        """Save settings to a JSON file."""
        if config_file is None:
            config_file = os.path.join(self.base_dir, "config.json")
            
        try:
            # Convert dataclass instances to dictionaries
            data = asdict(self)
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Failed to save settings: {e}")
    
    @classmethod
    def load(cls, config_file: Optional[str] = None) -> 'Settings':
        """Load settings from a JSON file."""
        if config_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_file = os.path.join(base_dir, "config.json")
            
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    
                # Convert model configs back to ModelConfig instances
                if 'available_models' in data and data['available_models']:
                    data['available_models'] = [
                        ModelConfig(**model_data)
                        for model_data in data['available_models']
                    ]
                    
                return cls(**data)
            return cls()
        except Exception as e:
            raise RuntimeError(f"Failed to load settings: {e}")

# Create global settings instance
settings = Settings.load()
