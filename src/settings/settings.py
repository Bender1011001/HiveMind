"""Configuration settings for the multi-agent system."""

import os
import json
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Settings:
    """System configuration settings."""
    
    # Model settings
    model_name: str = "gpt-4"
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    
    # MongoDB settings
    mongodb_uri: str = "mongodb://localhost:27017/"
    
    # RabbitMQ settings
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    
    # Directory settings
    base_dir: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    shared_data_dir: str = os.path.join(base_dir, "workspace", "data")
    shared_code_dir: str = os.path.join(base_dir, "workspace", "code")
    shared_output_dir: str = os.path.join(base_dir, "workspace", "output")
    
    def __post_init__(self):
        """Create necessary directories after initialization."""
        os.makedirs(self.shared_data_dir, exist_ok=True)
        os.makedirs(self.shared_code_dir, exist_ok=True)
        os.makedirs(self.shared_output_dir, exist_ok=True)
    
    def save(self, config_file: Optional[str] = None):
        """Save settings to a JSON file."""
        if config_file is None:
            config_file = os.path.join(self.base_dir, "config.json")
            
        try:
            with open(config_file, 'w') as f:
                json.dump(asdict(self), f, indent=2)
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
                return cls(**data)
            return cls()
        except Exception as e:
            raise RuntimeError(f"Failed to load settings: {e}")

# Create global settings instance
settings = Settings.load()
