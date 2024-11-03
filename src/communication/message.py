from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

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

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        return {
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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary format."""
        return cls(
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

    def add_quality_score(self, metric: str, score: float) -> None:
        """Add a quality score for a specific metric."""
        if not self.quality_scores:
            self.quality_scores = {}
        self.quality_scores[metric] = score

    def update_context_summary(self, summary: str) -> None:
        """Update the context summary for this message."""
        self.context_summary = summary

    def add_related_message(self, message_id: str) -> None:
        """Add a related message ID to track message relationships."""
        if not self.related_messages:
            self.related_messages = []
        self.related_messages.append(message_id)

    def get_average_quality_score(self) -> Optional[float]:
        """Calculate the average quality score across all metrics."""
        if not self.quality_scores:
            return None
        return sum(self.quality_scores.values()) / len(self.quality_scores)

    def has_feedback(self) -> bool:
        """Check if the message has received quality feedback."""
        return bool(self.quality_scores)
