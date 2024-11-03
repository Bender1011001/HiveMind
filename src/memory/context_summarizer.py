from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from ..communication.message import Message, MessageType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ContextSummary:
    """Represents a summary of context for a specific task or conversation."""
    summary_id: str
    task_id: str
    content: str
    timestamp: datetime = datetime.utcnow()
    source_message_ids: List[str] = None
    metadata: Optional[Dict] = None

class ContextSummarizer:
    """Manages the creation and retrieval of context summaries."""
    
    def __init__(self, summary_interval: int = 10, max_messages_per_summary: int = 50):
        """Initialize the context summarizer.
        
        Args:
            summary_interval: Number of messages before creating a new summary
            max_messages_per_summary: Maximum number of messages to include in one summary
        """
        self.summary_interval = summary_interval
        self.max_messages_per_summary = max_messages_per_summary
        self.message_buffer: Dict[str, List[Message]] = {}  # task_id -> messages
        self.summaries: Dict[str, List[ContextSummary]] = {}  # task_id -> summaries
        
    def add_message(self, message: Message) -> Optional[ContextSummary]:
        """Add a message to the buffer and create summary if needed."""
        if not isinstance(message, Message):
            raise ValueError("message must be an instance of Message")
            
        task_id = message.task_id
        
        # Initialize buffer for new tasks
        if task_id not in self.message_buffer:
            self.message_buffer[task_id] = []
            
        # Add message to buffer
        self.message_buffer[task_id].append(message)
        
        # Check if we need to create a summary
        if len(self.message_buffer[task_id]) >= self.summary_interval:
            return self._create_summary(task_id)
            
        return None
        
    def _create_summary(self, task_id: str) -> ContextSummary:
        """Create a summary from buffered messages."""
        messages = self.message_buffer[task_id]
        
        # Extract relevant content based on message types
        task_content = []
        clarifications = []
        context_updates = []
        
        for msg in messages:
            if msg.message_type == MessageType.TASK_REQUEST or msg.message_type == MessageType.TASK_RESPONSE:
                task_content.append(f"Task interaction: {msg.content.get('message', '')}")
            elif msg.message_type == MessageType.CLARIFICATION_REQUEST or msg.message_type == MessageType.CLARIFICATION_RESPONSE:
                clarifications.append(f"Clarification: {msg.content.get('message', '')}")
            elif msg.message_type == MessageType.CONTEXT_UPDATE:
                context_updates.append(f"Context update: {msg.content.get('update', '')}")
                
        # Combine all content into a structured summary
        summary_content = []
        if task_content:
            summary_content.append("Task Progress:\n" + "\n".join(task_content))
        if clarifications:
            summary_content.append("Clarifications:\n" + "\n".join(clarifications))
        if context_updates:
            summary_content.append("Context Updates:\n" + "\n".join(context_updates))
            
        summary = ContextSummary(
            summary_id=f"{task_id}_{datetime.utcnow().timestamp()}",
            task_id=task_id,
            content="\n\n".join(summary_content),
            source_message_ids=[msg.metadata.get('message_id', '') for msg in messages if msg.metadata],
            metadata={
                'message_count': len(messages),
                'time_span': {
                    'start': min(msg.timestamp for msg in messages).isoformat(),
                    'end': max(msg.timestamp for msg in messages).isoformat()
                }
            }
        )
        
        # Store the summary
        if task_id not in self.summaries:
            self.summaries[task_id] = []
        self.summaries[task_id].append(summary)
        
        # Clear the message buffer
        self.message_buffer[task_id] = []
        
        logger.info(f"Created new context summary for task {task_id}")
        return summary
        
    def get_latest_summary(self, task_id: str) -> Optional[ContextSummary]:
        """Get the most recent summary for a task."""
        if task_id in self.summaries and self.summaries[task_id]:
            return self.summaries[task_id][-1]
        return None
        
    def get_summaries_in_timeframe(self, task_id: str, start_time: datetime, 
                                 end_time: Optional[datetime] = None) -> List[ContextSummary]:
        """Get all summaries for a task within a specific timeframe."""
        if end_time is None:
            end_time = datetime.utcnow()
            
        if task_id not in self.summaries:
            return []
            
        return [
            summary for summary in self.summaries[task_id]
            if start_time <= summary.timestamp <= end_time
        ]
        
    def force_summarize(self, task_id: str) -> Optional[ContextSummary]:
        """Force create a summary for a task regardless of buffer size."""
        if task_id in self.message_buffer and self.message_buffer[task_id]:
            return self._create_summary(task_id)
        return None
