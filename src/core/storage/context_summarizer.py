from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from threading import Lock
from ..messaging.message import Message, MessageType
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

@dataclass
class ContextSummary:
    """Represents a summary of context for a specific task or conversation."""
    summary_id: str
    task_id: str
    content: str
    timestamp: datetime = datetime.utcnow()
    source_message_ids: List[str] = None
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary format."""
        try:
            data = asdict(self)
            data['timestamp'] = self.timestamp.isoformat()
            return data
        except Exception as e:
            logger.error(f"Error converting summary to dict: {str(e)}", exc_info=True)
            raise

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get statistical information about the summary."""
        try:
            return {
                'summary_id': self.summary_id,
                'task_id': self.task_id,
                'content_length': len(self.content),
                'source_message_count': len(self.source_message_ids) if self.source_message_ids else 0,
                'timestamp': self.timestamp.isoformat(),
                'metadata': self.metadata or {}
            }
        except Exception as e:
            logger.error(f"Error getting summary stats: {str(e)}", exc_info=True)
            raise

class ContextSummarizer:
    """Manages the creation and retrieval of context summaries."""

    def __init__(self, summary_interval: int = 10, max_messages_per_summary: int = 50,
                 retention_days: int = 30):
        """Initialize the context summarizer."""
        try:
            logger.info(
                f"Initializing ContextSummarizer (interval: {summary_interval}, "
                f"max_messages: {max_messages_per_summary}, retention: {retention_days} days)"
            )
            self.summary_interval = summary_interval
            self.max_messages_per_summary = max_messages_per_summary
            self.retention_days = retention_days
            self.message_buffer: Dict[str, List[Message]] = {}  # task_id -> messages
            self.summaries: Dict[str, List[ContextSummary]] = {}  # task_id -> summaries
            self.lock = Lock()  # Thread safety
            self.stats = {
                'total_summaries_created': 0,
                'total_messages_processed': 0,
                'last_cleanup': datetime.utcnow()
            }
            logger.debug("ContextSummarizer initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ContextSummarizer: {str(e)}", exc_info=True)
            raise

    def add_message(self, message: Message) -> Optional[ContextSummary]:
        """Add a message to the buffer and create summary if needed."""
        try:
            if not isinstance(message, Message):
                logger.error("Invalid message type provided")
                raise ValueError("message must be an instance of Message")

            task_id = message.task_id
            logger.debug(f"Adding message to buffer for task {task_id}")

            with self.lock:
                # Initialize buffer for new tasks
                if task_id not in self.message_buffer:
                    logger.debug(f"Initializing new message buffer for task {task_id}")
                    self.message_buffer[task_id] = []

                # Add message to buffer
                self.message_buffer[task_id].append(message)
                self.stats['total_messages_processed'] += 1
                buffer_size = len(self.message_buffer[task_id])
                logger.debug(f"Message added to buffer. Current buffer size for task {task_id}: {buffer_size}")

                # Check if we need to create a summary
                if buffer_size >= self.summary_interval:
                    logger.info(f"Buffer reached summary interval for task {task_id}, creating summary")
                    return self._create_summary(task_id)

                return None
        except Exception as e:
            logger.error(f"Error adding message to buffer: {str(e)}", exc_info=True)
            raise

    def _create_summary(self, task_id: str) -> ContextSummary:
        """Create a summary from buffered messages."""
        try:
            logger.info(f"Creating summary for task {task_id}")
            with self.lock:
                messages = self.message_buffer[task_id]
                logger.debug(f"Processing {len(messages)} messages for summary")

                # Extract relevant content based on message types
                content_by_type = {
                    'task_content': [],
                    'clarifications': [],
                    'context_updates': [],
                    'other': []
                }

                for msg in messages:
                    if msg.message_type in [MessageType.TASK_REQUEST, MessageType.TASK_RESPONSE]:
                        content_by_type['task_content'].append(f"Task interaction: {msg.content.get('message', '')}")
                    elif msg.message_type in [MessageType.CLARIFICATION_REQUEST, MessageType.CLARIFICATION_RESPONSE]:
                        content_by_type['clarifications'].append(f"Clarification: {msg.content.get('message', '')}")
                    elif msg.message_type == MessageType.CONTEXT_UPDATE:
                        content_by_type['context_updates'].append(f"Context update: {msg.content.get('update', '')}")
                    else:
                        content_by_type['other'].append(f"{msg.message_type.value}: {msg.content.get('message', '')}")

                logger.debug(
                    f"Content distribution - Tasks: {len(content_by_type['task_content'])}, "
                    f"Clarifications: {len(content_by_type['clarifications'])}, "
                    f"Updates: {len(content_by_type['context_updates'])}, "
                    f"Other: {len(content_by_type['other'])}"
                )

                # Combine all content into a structured summary
                summary_sections = []
                for section_name, content_list in content_by_type.items():
                    if content_list:
                        section_title = section_name.replace('_', ' ').title()
                        summary_sections.append(f"{section_title}:\n" + "\n".join(content_list))

                summary_id = f"{task_id}_{datetime.utcnow().timestamp()}"
                logger.debug(f"Creating summary with ID: {summary_id}")

                summary = ContextSummary(
                    summary_id=summary_id,
                    task_id=task_id,
                    content="\n\n".join(summary_sections),
                    source_message_ids=[msg.metadata.get('message_id', '') for msg in messages if msg.metadata],
                    metadata={
                        'message_count': len(messages),
                        'content_distribution': {k: len(v) for k, v in content_by_type.items()},
                        'time_span': {
                            'start': min(msg.timestamp for msg in messages).isoformat(),
                            'end': max(msg.timestamp for msg in messages).isoformat()
                        }
                    }
                )

                # Store the summary
                if task_id not in self.summaries:
                    logger.debug(f"Initializing summaries list for task {task_id}")
                    self.summaries[task_id] = []
                self.summaries[task_id].append(summary)
                self.stats['total_summaries_created'] += 1
                logger.debug(f"Summary stored. Total summaries for task {task_id}: {len(self.summaries[task_id])}")

                # Clear the message buffer
                self.message_buffer[task_id] = []
                logger.debug(f"Message buffer cleared for task {task_id}")

                # Check if cleanup is needed
                self._check_cleanup()

                logger.info(f"Successfully created new context summary for task {task_id}")
                return summary
        except Exception as e:
            logger.error(f"Error creating summary for task {task_id}: {str(e)}", exc_info=True)
            raise

    def get_latest_summary(self, task_id: str) -> Optional[ContextSummary]:
        """Get the most recent summary for a task."""
        try:
            logger.debug(f"Retrieving latest summary for task {task_id}")
            with self.lock:
                if task_id in self.summaries and self.summaries[task_id]:
                    summary = self.summaries[task_id][-1]
                    logger.info(f"Retrieved latest summary {summary.summary_id} for task {task_id}")
                    return summary
                logger.info(f"No summaries found for task {task_id}")
                return None
        except Exception as e:
            logger.error(f"Error retrieving latest summary for task {task_id}: {str(e)}", exc_info=True)
            raise

    def get_summaries_in_timeframe(self, task_id: str, start_time: datetime,
                                 end_time: Optional[datetime] = None) -> List[ContextSummary]:
        """Get all summaries for a task within a specific timeframe."""
        try:
            if end_time is None:
                end_time = datetime.utcnow()

            logger.debug(f"Retrieving summaries for task {task_id} between {start_time} and {end_time}")

            with self.lock:
                if task_id not in self.summaries:
                    logger.info(f"No summaries found for task {task_id}")
                    return []

                summaries = [
                    summary for summary in self.summaries[task_id]
                    if start_time <= summary.timestamp <= end_time
                ]

                logger.info(f"Retrieved {len(summaries)} summaries for task {task_id} in timeframe")
                return summaries
        except Exception as e:
            logger.error(f"Error retrieving summaries in timeframe for task {task_id}: {str(e)}", exc_info=True)
            raise

    def force_summarize(self, task_id: str) -> Optional[ContextSummary]:
        """Force create a summary for a task regardless of buffer size."""
        try:
            logger.info(f"Force summarizing task {task_id}")
            with self.lock:
                if task_id in self.message_buffer and self.message_buffer[task_id]:
                    logger.debug(f"Found {len(self.message_buffer[task_id])} messages to summarize")
                    return self._create_summary(task_id)
                logger.info(f"No messages in buffer for task {task_id}, skipping summary creation")
                return None
        except Exception as e:
            logger.error(f"Error force summarizing task {task_id}: {str(e)}", exc_info=True)
            raise

    def _check_cleanup(self):
        """Check if cleanup is needed based on last cleanup time."""
        try:
            now = datetime.utcnow()
            if (now - self.stats['last_cleanup']) >= timedelta(days=1):
                logger.info("Starting daily cleanup")
                self._cleanup_old_summaries()
                self.stats['last_cleanup'] = now
        except Exception as e:
            logger.error(f"Error checking cleanup: {str(e)}", exc_info=True)

    def _cleanup_old_summaries(self):
        """Remove summaries older than retention period."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
            logger.info(f"Cleaning up summaries older than {cutoff}")

            with self.lock:
                total_removed = 0
                for task_id in list(self.summaries.keys()):
                    original_count = len(self.summaries[task_id])
                    self.summaries[task_id] = [
                        summary for summary in self.summaries[task_id]
                        if summary.timestamp >= cutoff
                    ]
                    removed = original_count - len(self.summaries[task_id])
                    if removed > 0:
                        logger.debug(f"Removed {removed} old summaries for task {task_id}")
                        total_removed += removed

                    # Remove empty task entries
                    if not self.summaries[task_id]:
                        del self.summaries[task_id]
                        logger.debug(f"Removed empty summaries list for task {task_id}")

                logger.info(f"Cleanup complete. Removed {total_removed} old summaries")
        except Exception as e:
            logger.error(f"Error cleaning up old summaries: {str(e)}", exc_info=True)
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get summarizer statistics."""
        try:
            with self.lock:
                stats = {
                    **self.stats,
                    'active_tasks': len(self.message_buffer),
                    'total_tasks_with_summaries': len(self.summaries),
                    'buffer_sizes': {
                        task_id: len(messages)
                        for task_id, messages in self.message_buffer.items()
                    },
                    'summaries_per_task': {
                        task_id: len(summaries)
                        for task_id, summaries in self.summaries.items()
                    }
                }
                logger.debug("Retrieved summarizer statistics")
                return stats
        except Exception as e:
            logger.error(f"Error getting summarizer stats: {str(e)}", exc_info=True)
            raise
