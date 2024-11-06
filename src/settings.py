from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class Settings:
    """Application settings."""
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "hivemind"
    rabbitmq_uri: str = "amqp://guest:guest@localhost:5672/"
    debug: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "mongo_uri": self.mongo_uri,
            "mongo_db": self.mongo_db,
            "rabbitmq_uri": self.rabbitmq_uri,
            "debug": self.debug
        }

settings = Settings()
