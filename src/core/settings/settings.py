"""Application settings management module."""

import os
from typing import Dict, Any
from dataclasses import dataclass, field
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

@dataclass
class Settings:
    """Application settings."""
    mongo_uri: str = field(default="mongodb://localhost:27017")
    mongo_db: str = field(default="hivemind")
    rabbitmq_uri: str = field(default="amqp://guest:guest@localhost:5672/")
    debug: bool = field(default=True)

    def __post_init__(self):
        """Initialize settings with environment variables and logging."""
        try:
            logger.info("Initializing application settings")

            # Load settings from environment variables if available
            self.mongo_uri = os.getenv('HIVEMIND_MONGO_URI', self.mongo_uri)
            self.mongo_db = os.getenv('HIVEMIND_MONGO_DB', self.mongo_db)
            self.rabbitmq_uri = os.getenv('HIVEMIND_RABBITMQ_URI', self.rabbitmq_uri)
            self.debug = os.getenv('HIVEMIND_DEBUG', str(self.debug)).lower() == 'true'

            # Log settings (with sensitive information masked)
            masked_settings = self._get_masked_settings()
            logger.info("Settings initialized with values:")
            for key, value in masked_settings.items():
                logger.info(f"  {key}: {value}")

        except Exception as e:
            logger.error(f"Error initializing settings: {str(e)}", exc_info=True)
            raise

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        try:
            logger.debug("Converting settings to dictionary")
            settings_dict = {
                "mongo_uri": self.mongo_uri,
                "mongo_db": self.mongo_db,
                "rabbitmq_uri": self.rabbitmq_uri,
                "debug": self.debug
            }
            logger.debug("Successfully converted settings to dictionary")
            return settings_dict
        except Exception as e:
            logger.error(f"Error converting settings to dictionary: {str(e)}", exc_info=True)
            raise

    def _get_masked_settings(self) -> Dict[str, str]:
        """Get settings with sensitive information masked for logging."""
        try:
            def mask_uri(uri: str) -> str:
                """Mask sensitive parts of URIs."""
                if '@' in uri:
                    # Mask username and password in URIs
                    parts = uri.split('@')
                    return f"***@{parts[1]}"
                return uri

            return {
                "mongo_uri": mask_uri(self.mongo_uri),
                "mongo_db": self.mongo_db,
                "rabbitmq_uri": mask_uri(self.rabbitmq_uri),
                "debug": self.debug
            }
        except Exception as e:
            logger.error(f"Error masking sensitive settings: {str(e)}", exc_info=True)
            raise

    def validate(self) -> bool:
        """Validate settings configuration."""
        try:
            logger.debug("Validating settings")

            # Validate MongoDB URI
            if not self.mongo_uri.startswith(('mongodb://', 'mongodb+srv://')):
                logger.error("Invalid MongoDB URI format")
                return False

            # Validate RabbitMQ URI
            if not self.rabbitmq_uri.startswith('amqp://'):
                logger.error("Invalid RabbitMQ URI format")
                return False

            # Validate MongoDB database name
            if not self.mongo_db or not isinstance(self.mongo_db, str):
                logger.error("Invalid MongoDB database name")
                return False

            logger.info("Settings validation successful")
            return True

        except Exception as e:
            logger.error(f"Error validating settings: {str(e)}", exc_info=True)
            raise

    def update(self, updates: Dict[str, Any]) -> None:
        """Update settings with new values."""
        try:
            logger.info("Updating settings")
            logger.debug(f"Update values: {self._get_masked_settings()}")

            for key, value in updates.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                    logger.debug(f"Updated setting: {key}")
                else:
                    logger.warning(f"Attempted to update unknown setting: {key}")

            if self.validate():
                logger.info("Settings updated successfully")
            else:
                logger.error("Settings update failed validation")
                raise ValueError("Invalid settings configuration")

        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}", exc_info=True)
            raise

# Create singleton instance
try:
    logger.info("Creating settings instance")
    settings = Settings()
    if settings.validate():
        logger.info("Settings instance created and validated successfully")
    else:
        logger.error("Settings validation failed during instance creation")
        raise ValueError("Invalid settings configuration")
except Exception as e:
    logger.error(f"Error creating settings instance: {str(e)}", exc_info=True)
    raise
