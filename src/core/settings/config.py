"""Configuration management for the HiveMind system."""

import os
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
import json
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

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

    def __post_init__(self):
        """Initialize settings and validate paths."""
        logger.debug("Initializing settings")
        self._validate_paths()
        logger.info("Settings initialized successfully")

    def _validate_paths(self) -> None:
        """Validate and normalize all path settings."""
        try:
            logger.debug("Validating workspace paths")
            paths = {
                'workspace_root': self.workspace_root,
                'shared_code_dir': self.shared_code_dir,
                'shared_data_dir': self.shared_data_dir,
                'shared_output_dir': self.shared_output_dir
            }

            for name, path in paths.items():
                abs_path = os.path.abspath(path)
                setattr(self, name, abs_path)
                logger.debug(f"Normalized {name}: {abs_path}")

            logger.info("Path validation completed successfully")
        except Exception as e:
            logger.error(f"Error validating paths: {str(e)}", exc_info=True)
            raise

    @classmethod
    def load(cls) -> 'Settings':
        """Load settings from config file or environment variables."""
        logger.info("Loading settings")
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        settings = cls()

        try:
            # Create workspace directories
            logger.debug("Creating workspace directories")
            for path_name in ['workspace_root', 'shared_code_dir', 'shared_data_dir', 'shared_output_dir']:
                path = getattr(settings, path_name)
                os.makedirs(path, exist_ok=True)
                logger.debug(f"Created directory: {path}")

            # Try to load from config file
            if os.path.exists(config_path):
                logger.debug(f"Loading settings from config file: {config_path}")
                try:
                    with open(config_path, 'r') as f:
                        config_data = json.load(f)
                    for key, value in config_data.items():
                        if hasattr(settings, key):
                            setattr(settings, key, value)
                            if key != 'api_key':  # Don't log sensitive data
                                logger.debug(f"Loaded setting from file: {key}={value}")
                    logger.info("Successfully loaded settings from config file")
                except Exception as e:
                    logger.error(f"Error loading config file: {str(e)}", exc_info=True)
            else:
                logger.info("No config file found, using default values")

            # Override with environment variables if present
            logger.debug("Checking environment variables")
            env_mapping = {
                'OPENROUTER_API_KEY': 'api_key',  # Changed from OPENAI_API_KEY to OPENROUTER_API_KEY
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
                        if setting_name != 'api_key':  # Don't log sensitive data
                            logger.debug(f"Loaded setting from environment: {setting_name}={value}")
                    except Exception as e:
                        logger.error(f"Error setting {setting_name} from environment: {str(e)}", exc_info=True)

            # Enable computer use for Claude 3.5 Sonnet
            settings.enable_computer_use = settings.model_name == "anthropic/claude-3.5-sonnet:beta"
            logger.debug(f"Computer use enabled: {settings.enable_computer_use}")

            logger.info("Settings loaded successfully")
            return settings

        except Exception as e:
            logger.error(f"Error loading settings: {str(e)}", exc_info=True)
            raise

    def save(self) -> None:
        """Save settings to config file."""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            logger.debug(f"Saving settings to: {config_path}")

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            # Create a copy of settings without sensitive data for logging
            safe_settings = {k: v for k, v in asdict(self).items() if k != 'api_key'}
            logger.debug(f"Settings to save: {safe_settings}")

            # Save settings
            with open(config_path, 'w') as f:
                json.dump(asdict(self), f, indent=4)

            logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {str(e)}", exc_info=True)
            raise

    def validate(self) -> bool:
        """Validate settings configuration."""
        try:
            logger.debug("Validating settings")

            # Validate model name
            if not self.model_name:
                logger.error("Model name is required")
                return False

            # Validate temperature
            if not 0 <= self.temperature <= 1:
                logger.error(f"Invalid temperature value: {self.temperature}")
                return False

            # Validate max tokens
            if self.max_tokens <= 0:
                logger.error(f"Invalid max_tokens value: {self.max_tokens}")
                return False

            # Validate MongoDB URI
            if not self.mongodb_uri.startswith(('mongodb://', 'mongodb+srv://')):
                logger.error(f"Invalid MongoDB URI: {self.mongodb_uri}")
                return False

            # Validate RabbitMQ port
            if not 1 <= self.rabbitmq_port <= 65535:
                logger.error(f"Invalid RabbitMQ port: {self.rabbitmq_port}")
                return False

            logger.info("Settings validation successful")
            return True

        except Exception as e:
            logger.error(f"Error validating settings: {str(e)}", exc_info=True)
            return False

    def get_masked_settings(self) -> Dict[str, Any]:
        """Get settings with sensitive information masked for logging."""
        try:
            settings_dict = asdict(self)
            # Mask sensitive information
            if 'api_key' in settings_dict:
                settings_dict['api_key'] = '***'
            if 'mongodb_uri' in settings_dict:
                uri = settings_dict['mongodb_uri']
                if '@' in uri:
                    parts = uri.split('@')
                    settings_dict['mongodb_uri'] = f"***@{parts[1]}"
            return settings_dict
        except Exception as e:
            logger.error(f"Error masking settings: {str(e)}", exc_info=True)
            raise

# Create global settings instance
try:
    logger.info("Creating global settings instance")
    settings = Settings.load()
    if settings.validate():
        logger.info("Global settings instance created and validated successfully")
        logger.debug(f"Current settings: {settings.get_masked_settings()}")
    else:
        logger.error("Settings validation failed")
        raise ValueError("Invalid settings configuration")
except Exception as e:
    logger.error(f"Error creating global settings instance: {str(e)}", exc_info=True)
    raise
