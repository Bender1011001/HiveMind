"""Configuration management for the HiveMind system."""

import os
from typing import Dict, Optional
from dataclasses import dataclass, asdict
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class Settings:
    """System settings with default values."""
    model_name: str = "gpt-3.5-turbo"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 1000
    mongodb_uri: str = "mongodb://localhost:27017/"
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    enable_computer_use: bool = False
    
    # Add shared workspace configuration
    workspace_root: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'workspace')
    shared_code_dir: str = os.path.join(workspace_root, 'code')
    shared_data_dir: str = os.path.join(workspace_root, 'data')
    shared_output_dir: str = os.path.join(workspace_root, 'output')
    
    @classmethod
    def load(cls) -> 'Settings':
        """Load settings from config file or environment variables."""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        settings = cls()
        
        # Create workspace directories
        os.makedirs(settings.workspace_root, exist_ok=True)
        os.makedirs(settings.shared_code_dir, exist_ok=True)
        os.makedirs(settings.shared_data_dir, exist_ok=True)
        os.makedirs(settings.shared_output_dir, exist_ok=True)
        
        # Try to load from config file
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                for key, value in config_data.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
        
        # Override with environment variables if present
        env_mapping = {
            'OPENAI_API_KEY': 'api_key',
            'MODEL_NAME': 'model_name',
            'TEMPERATURE': 'temperature',
            'MAX_TOKENS': 'max_tokens',
            'MONGODB_URI': 'mongodb_uri',
            'RABBITMQ_HOST': 'rabbitmq_host',
            'RABBITMQ_PORT': 'rabbitmq_port',
            'WORKSPACE_ROOT': 'workspace_root',
            'SHARED_CODE_DIR': 'shared_code_dir',
            'SHARED_DATA_DIR': 'shared_data_dir',
            'SHARED_OUTPUT_DIR': 'shared_output_dir'
        }
        
        for env_var, setting_name in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    # Convert value to appropriate type
                    field_type = type(getattr(settings, setting_name))
                    if field_type == bool:
                        value = value.lower() in ('true', '1', 'yes')
                    elif field_type == int:
                        value = int(value)
                    elif field_type == float:
                        value = float(value)
                    setattr(settings, setting_name, value)
                except Exception as e:
                    logger.error(f"Error setting {setting_name} from environment: {e}")
        
        # Enable computer use for Claude 3.5 Sonnet
        settings.enable_computer_use = settings.model_name == "anthropic/claude-3.5-sonnet:beta"
        
        return settings
    
    def save(self) -> None:
        """Save settings to config file."""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            # Save settings
            with open(config_path, 'w') as f:
                json.dump(asdict(self), f, indent=4)
                
            logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            raise

# Global settings instance
settings = Settings.load()
