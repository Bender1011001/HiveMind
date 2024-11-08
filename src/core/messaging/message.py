from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

class MessageType(Enum):
    """Types of messages that can be exchanged between agents."""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    CLARIFICATION_REQUEST = "clarification_request"
    CLARIFICATION_RESPONSE = "clarification_response"
    CONTEXT_UPDATE = "context_update"
    CONTEXT_SUMMARY = "context_summary"
    QUALITY_FEEDBACK = "quality_feedback"
    QUALITY_RESPONSE = "quality_response"
    ERROR = "error"

@dataclass
class Message:
    """Represents a message exchanged between agents."""
    sender_id: str
    receiver_id: str
    message_type: MessageType
    content: Dict[str, Any]
    task_id: str
    timestamp: datetime = datetime.utcnow()
    metadata: Optional[Dict[str, Any]] = None
    quality_scores: Optional[Dict[str, float]] = None
    context_summary: Optional[str] = None
    related_messages: Optional[List[str]] = None

    def __post_init__(self):
        """Log message creation after initialization."""
        logger.debug(
            f"Created new message - Type: {self.message_type.value}, "
            f"Sender: {self.sender_id}, Receiver: {self.receiver_id}, "
            f"Task: {self.task_id}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        try:
            logger.debug(f"Converting message {self.task_id} to dictionary")
            result = {
                "sender_id": self.sender_id,
                "receiver_id": self.receiver_id,
                "message_type": self.message_type.value,
                "content": self.content,
                "task_id": self.task_id,
                "timestamp": self.timestamp.isoformat(),
                "metadata": self.metadata or {},
                "quality_scores": self.quality_scores or {},
                "context_summary": self.context_summary,
                "related_messages": self.related_messages or []
            }
            logger.debug(f"Successfully converted message {self.task_id} to dictionary")
            return result
        except Exception as e:
            logger.error(f"Error converting message {self.task_id} to dictionary: {str(e)}", exc_info=True)
            raise

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary format."""
        try:
            logger.debug(f"Creating message from dictionary - Task: {data.get('task_id')}")
            message = cls(
                sender_id=data["sender_id"],
                receiver_id=data["receiver_id"],
                message_type=MessageType(data["message_type"]),
                content=data["content"],
                task_id=data["task_id"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                metadata=data.get("metadata", {}),
                quality_scores=data.get("quality_scores", {}),
                context_summary=data.get("context_summary"),
                related_messages=data.get("related_messages", [])
            )
            logger.debug(f"Successfully created message from dictionary - Task: {message.task_id}")
            return message
        except KeyError as e:
            logger.error(f"Missing required field in message data: {str(e)}", exc_info=True)
            raise ValueError(f"Missing required field: {str(e)}")
        except ValueError as e:
            logger.error(f"Invalid message type in data: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error creating message from dictionary: {str(e)}", exc_info=True)
            raise

    def add_quality_score(self, metric: str, score: float) -> None:
        """Add a quality score for a specific metric."""
        try:
            logger.debug(f"Adding quality score for message {self.task_id} - Metric: {metric}, Score: {score}")
            if not self.quality_scores:
                self.quality_scores = {}
            self.quality_scores[metric] = score
            logger.info(f"Added quality score {score} for metric {metric} to message {self.task_id}")
        except Exception as e:
            logger.error(f"Error adding quality score to message {self.task_id}: {str(e)}", exc_info=True)
            raise

    def update_context_summary(self, summary: str) -> None:
        """Update the context summary for this message."""
        try:
            logger.debug(f"Updating context summary for message {self.task_id}")
            self.context_summary = summary
            logger.info(f"Updated context summary for message {self.task_id}")
        except Exception as e:
            logger.error(f"Error updating context summary for message {self.task_id}: {str(e)}", exc_info=True)
            raise

    def add_related_message(self, message_id: str) -> None:
        """Add a related message ID to track message relationships."""
        try:
            logger.debug(f"Adding related message {message_id} to message {self.task_id}")
            if not self.related_messages:
                self.related_messages = []
            self.related_messages.append(message_id)
            logger.info(f"Added related message {message_id} to message {self.task_id}")
        except Exception as e:
            logger.error(f"Error adding related message to message {self.task_id}: {str(e)}", exc_info=True)
            raise

    def get_average_quality_score(self) -> Optional[float]:
        """Calculate the average quality score across all metrics."""
        try:
            logger.debug(f"Calculating average quality score for message {self.task_id}")
            if not self.quality_scores:
                logger.debug(f"No quality scores found for message {self.task_id}")
                return None
            avg_score = sum(self.quality_scores.values()) / len(self.quality_scores)
            logger.debug(f"Average quality score for message {self.task_id}: {avg_score}")
            return avg_score
        except Exception as e:
            logger.error(f"Error calculating average quality score for message {self.task_id}: {str(e)}", exc_info=True)
            raise

    def has_feedback(self) -> bool:
        """Check if the message has received quality feedback."""
        try:
            logger.debug(f"Checking feedback status for message {self.task_id}")
            has_feedback = bool(self.quality_scores)
            logger.debug(f"Message {self.task_id} has feedback: {has_feedback}")
            return has_feedback
        except Exception as e:
            logger.error(f"Error checking feedback status for message {self.task_id}: {str(e)}", exc_info=True)
            raise

    def validate(self) -> bool:
        """Validate message structure and content."""
        try:
            logger.debug(f"Validating message {self.task_id}")

            # Check required fields
            if not all([self.sender_id, self.receiver_id, self.task_id]):
                logger.error(f"Message {self.task_id} missing required fields")
                return False

            # Validate content structure
            if not isinstance(self.content, dict):
                logger.error(f"Message {self.task_id} has invalid content type")
                return False

            # Validate timestamp
            if not isinstance(self.timestamp, datetime):
                logger.error(f"Message {self.task_id} has invalid timestamp")
                return False

            logger.info(f"Message {self.task_id} validation successful")
            return True

        except Exception as e:
            logger.error(f"Error validating message {self.task_id}: {str(e)}", exc_info=True)
            raise
