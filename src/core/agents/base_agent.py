"""Base agent class providing common functionality for all agents."""

import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
import traceback
import json
import time
from threading import Lock, Thread
from queue import Queue, Empty
from ..storage.context_manager import SharedContext
from ..storage.mongo_store import MongoMemoryStore
from ..messaging.broker import MessageBroker
from ..messaging.message import Message, MessageType
from ..execution.code_executor import CodeExecutor
from .capability import Capability, AgentCapability
from ..settings import settings
from ..utils.event_bus import EventBus
from .metrics_collector import MetricsCollector
from ...utils.logging_setup import setup_logging

# Set up centralized logging for the base agent
logger = setup_logging(__name__)

class BaseAgent:
    """Base class for all agents in the system."""

    def __init__(self, agent_id: str, capabilities: List[AgentCapability]):
        """Initialize base agent with core functionality."""
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.is_running = True
        self.lock = Lock()

        # Set up agent-specific logger
        self.logger = setup_logging(f"agent.{agent_id}")
        self.logger.info(f"Initializing agent {agent_id}")

        # Initialize metrics collector
        self.metrics = MetricsCollector(agent_id)

        # Message handling
        self.message_queue = Queue()
        self.pending_messages: Dict[str, Tuple[Message, int, datetime]] = {}  # message_id -> (message, retry_count, last_attempt)
        self.max_retries = 3
        self.retry_delay = 5  # seconds

        try:
            # Initialize core services
            self.memory_store = MongoMemoryStore()
            self.message_broker = MessageBroker()
            self.code_executor = CodeExecutor()
            self.shared_context = SharedContext(self.memory_store)
            self.event_bus = EventBus()

            # Record initialization time
            self.metrics.record_metric('initialization_time', 0.0)  # Placeholder for actual timing
            self.metrics.record_event('agent_initialized')
            self.logger.info("Core services initialized successfully")

            # Set up agent workspace
            self.workspace = {
                'code': os.path.join(settings.shared_code_dir, agent_id),
                'data': os.path.join(settings.shared_data_dir, agent_id),
                'output': os.path.join(settings.shared_output_dir, agent_id)
            }
            self._setup_workspace()

            # Start message processing thread
            self.message_thread = Thread(target=self._process_message_queue, daemon=True)
            self.message_thread.start()
            self.logger.info("Message processing thread started")

            # Start health check thread
            self.health_thread = Thread(target=self._report_health_status, daemon=True)
            self.health_thread.start()
            self.logger.info("Health check thread started")

        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {str(e)}", exc_info=True)
            raise

    def _emit_thought_process(self, thought: str, context: Optional[Dict] = None):
        """Emit a thought process event with error handling."""
        try:
            self.event_bus.emit('agent_thought_process', {
                'agent_id': self.agent_id,
                'thought': thought,
                'context': context or {},
                'timestamp': datetime.utcnow().isoformat()
            })
            self.logger.debug(f"Thought process: {thought}")
        except Exception as e:
            self.logger.error(f"Failed to emit thought process: {e}", exc_info=True)

    def _emit_action(self, action: str, result: Any = None):
        """Emit an action event with error handling."""
        try:
            self.event_bus.emit('agent_action', {
                'agent_id': self.agent_id,
                'action': action,
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            })
            self.logger.info(f"Action performed: {action}, Result: {result}")
        except Exception as e:
            self.logger.error(f"Failed to emit action: {e}", exc_info=True)

    def _emit_error(self, error: str, context: Optional[Dict] = None):
        """Emit an error event with full context."""
        try:
            error_context = {
                'agent_id': self.agent_id,
                'error': str(error),
                'stack_trace': traceback.format_exc(),
                'context': context or {},
                'timestamp': datetime.utcnow().isoformat(),
                'memory_store_connected': bool(self.memory_store and getattr(self.memory_store, 'is_connected', False)),
                'message_broker_connected': bool(self.message_broker and hasattr(self.message_broker, 'connection') and
                                               not self.message_broker.connection.is_closed)
            }
            self.event_bus.emit('agent_error', error_context)
            self.metrics.record_event('error_occurred', error_context)
            self.logger.error(f"Agent {self.agent_id} error: {error}", extra=error_context, exc_info=True)
        except Exception as e:
            self.logger.error(f"Failed to emit error: {e}", exc_info=True)

    def _emit_api_interaction(self, operation: str, request: Dict, response: Optional[Dict] = None, status: str = 'pending'):
        """Emit an API interaction event with error handling."""
        try:
            self.event_bus.emit('agent_api_interaction', {
                'agent_id': self.agent_id,
                'operation': operation,
                'request': request,
                'response': response,
                'status': status,
                'timestamp': datetime.utcnow().isoformat()
            })
            self.logger.debug(f"API Interaction - Operation: {operation}, Status: {status}")
        except Exception as e:
            self.logger.error(f"Failed to emit API interaction: {e}", exc_info=True)

    def _process_message_queue(self):
        """Process messages from the queue with retry mechanism."""
        while self.is_running:
            try:
                # Process pending retries
                self._handle_pending_retries()

                # Process new messages
                try:
                    message = self.message_queue.get(timeout=1)
                    start_time = datetime.now()
                    self._handle_message(message)
                    processing_time = (datetime.now() - start_time).total_seconds()
                    self.metrics.record_metric('message_processing_time', processing_time)
                    self.logger.debug(f"Message processed in {processing_time:.2f} seconds")
                except Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}", exc_info=True)
                    self.metrics.record_event('message_processing_error', {'error': str(e)})

            except Exception as e:
                self.logger.error(f"Error in message processing loop: {e}", exc_info=True)
                self.metrics.record_event('message_queue_error', {'error': str(e)})
                time.sleep(1)  # Prevent tight loop on error

    def _handle_pending_retries(self):
        """Handle pending message retries."""
        with self.lock:
            current_time = datetime.utcnow()
            retry_messages = []

            for msg_id, (message, retry_count, last_attempt) in self.pending_messages.items():
                if current_time - last_attempt >= timedelta(seconds=self.retry_delay):
                    retry_messages.append(msg_id)

            for msg_id in retry_messages:
                message, retry_count, _ = self.pending_messages[msg_id]
                if retry_count < self.max_retries:
                    self.logger.info(f"Retrying message {msg_id} (attempt {retry_count + 1})")
                    self.pending_messages[msg_id] = (message, retry_count + 1, current_time)
                    self._handle_message(message, is_retry=True)
                else:
                    self.logger.error(f"Message {msg_id} failed after {self.max_retries} attempts")
                    self._handle_message_failure(message, f"Failed after {self.max_retries} attempts")
                    del self.pending_messages[msg_id]

    def _handle_message(self, message: Message, is_retry: bool = False):
        """Handle a single message with error recovery."""
        start_time = datetime.now()
        try:
            if not is_retry:
                self._emit_thought_process(f"Processing message: {message.message_type}")

            if message.message_type == MessageType.CONTROL:
                self._handle_control_message(message)
            elif message.message_type == MessageType.TEXT:
                self._handle_text_message(message)
            else:
                self.logger.warning(f"Unsupported message type: {message.message_type}")

            # Message processed successfully
            if message.message_id in self.pending_messages:
                del self.pending_messages[message.message_id]

            # Record successful processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            self.metrics.record_metric('message_processing_time', processing_time)
            self.metrics.record_event('message_processed', {
                'message_type': message.message_type,
                'processing_time': processing_time
            })
            self.logger.info(f"Message {message.message_id} processed successfully")

        except Exception as e:
            self.logger.error(f"Error handling message: {e}", exc_info=True)
            if not is_retry:
                # Add to pending messages for retry
                self.pending_messages[message.message_id] = (message, 0, datetime.utcnow())
            self._emit_error(f"Message handling error: {e}", {"message_id": message.message_id})
            self.metrics.record_event('message_processing_error', {
                'error': str(e),
                'message_id': message.message_id
            })

    def _handle_message_failure(self, message: Message, reason: str):
        """Handle permanent message failure."""
        try:
            self._emit_error(f"Message permanently failed: {reason}", {
                "message_id": message.message_id,
                "message_type": message.message_type
            })

            self.metrics.record_event('message_permanent_failure', {
                'message_id': message.message_id,
                'reason': reason
            })

            # Store failure in memory store
            if self.memory_store:
                self.memory_store.store_memory(
                    agent_id=self.agent_id,
                    memory_type="message_failure",
                    content={
                        "message_id": message.message_id,
                        "reason": reason,
                        "timestamp": datetime.utcnow().isoformat(),
                        "message": message.to_dict()
                    }
                )
            self.logger.error(f"Message {message.message_id} permanently failed: {reason}")
        except Exception as e:
            self.logger.error(f"Error handling message failure: {e}", exc_info=True)

    def _handle_control_message(self, message: Message):
        """Handle control messages."""
        try:
            command = message.content.get("command")
            if command == "pause":
                self.is_running = False
                self._emit_action("Agent paused")
                self.metrics.record_event('agent_paused')
                self.logger.info("Agent paused")
            elif command == "resume":
                self.is_running = True
                self._emit_action("Agent resumed")
                self.metrics.record_event('agent_resumed')
                self.logger.info("Agent resumed")
            elif command == "status":
                self._report_status(message.sender_id)
            else:
                self.logger.warning(f"Unknown control command: {command}")
        except Exception as e:
            self.logger.error(f"Error handling control message: {e}", exc_info=True)
            self.metrics.record_event('control_message_error', {'error': str(e)})
            raise

    def _handle_text_message(self, message: Message):
        """Handle text messages."""
        try:
            # Store message receipt
            if self.memory_store:
                self.memory_store.store_memory(
                    agent_id=self.agent_id,
                    memory_type="message_receipt",
                    content=message.to_dict()
                )

            # Process message content
            start_time = datetime.now()
            response_content = self._process_text_content(message.content)
            processing_time = (datetime.now() - start_time).total_seconds()
            self.metrics.record_metric('text_processing_time', processing_time)
            self.logger.debug(f"Text message processed in {processing_time:.2f} seconds")

            # Send response if needed
            if response_content:
                self.send_message(
                    message.sender_id,
                    response_content,
                    message.task_id
                )

        except Exception as e:
            self.logger.error(f"Error handling text message: {e}", exc_info=True)
            self.metrics.record_event('text_message_error', {'error': str(e)})
            raise

    def _process_text_content(self, content: Dict) -> Optional[Dict]:
        """Process text message content. Override in subclasses."""
        return None

    def _report_health_status(self):
        """Periodically report agent health status."""
        while self.is_running:
            try:
                # Get metrics for the health report
                processing_stats = self.metrics.get_metric_stats('message_processing_time')
                recent_events = self.metrics.get_recent_events(10)

                health_status = {
                    "agent_id": self.agent_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "healthy" if self.is_running else "paused",
                    "message_queue_size": self.message_queue.qsize(),
                    "pending_retries": len(self.pending_messages),
                    "memory_store_connected": bool(self.memory_store and getattr(self.memory_store, 'is_connected', False)),
                    "message_broker_connected": bool(self.message_broker and hasattr(self.message_broker, 'connection') and
                                                   not self.message_broker.connection.is_closed),
                    "performance_metrics": processing_stats,
                    "recent_events": recent_events
                }

                if self.memory_store:
                    self.memory_store.store_memory(
                        agent_id=self.agent_id,
                        memory_type="health_status",
                        content=health_status
                    )

                self._emit_action("Health status reported", health_status)
                self.metrics.record_event('health_status_reported', health_status)
                self.logger.info("Health status reported successfully")

            except Exception as e:
                self.logger.error(f"Error reporting health status: {e}", exc_info=True)
                self.metrics.record_event('health_status_error', {'error': str(e)})

            time.sleep(60)  # Report every minute

    def _report_status(self, requester_id: str):
        """Report agent status on demand."""
        try:
            # Get metrics for the status report
            processing_stats = self.metrics.get_metric_stats('message_processing_time')
            recent_events = self.metrics.get_recent_events(5)

            status = {
                "agent_id": self.agent_id,
                "status": "healthy" if self.is_running else "paused",
                "capabilities": [cap.capability.name for cap in self.capabilities],
                "message_queue_size": self.message_queue.qsize(),
                "pending_retries": len(self.pending_messages),
                "performance_metrics": processing_stats,
                "recent_events": recent_events,
                "timestamp": datetime.utcnow().isoformat()
            }

            self.send_message(
                requester_id,
                {"type": "status_report", "status": status},
                None
            )

            self.metrics.record_event('status_reported', {'requester': requester_id})
            self.logger.info(f"Status report sent to {requester_id}")

        except Exception as e:
            self.logger.error(f"Error reporting status: {e}", exc_info=True)
            self.metrics.record_event('status_report_error', {'error': str(e)})

    def _setup_workspace(self):
        """Set up agent's workspace directories with error handling."""
        try:
            start_time = datetime.now()
            for path in self.workspace.values():
                os.makedirs(path, exist_ok=True)
            setup_time = (datetime.now() - start_time).total_seconds()
            self.metrics.record_metric('workspace_setup_time', setup_time)
            self._emit_action("Setting up workspace directories", "Success")
            self.logger.info("Workspace directories set up successfully")
        except Exception as e:
            self._emit_error(f"Failed to set up workspace: {str(e)}")
            self.metrics.record_event('workspace_setup_error', {'error': str(e)})
            self.logger.error(f"Failed to set up workspace: {e}", exc_info=True)
            raise

    def cleanup(self):
        """Clean up resources with proper error handling."""
        try:
            self._emit_thought_process("Cleaning up resources")
            self.logger.info("Starting cleanup process")
            start_time = datetime.now()

            # Stop processing threads
            self.is_running = False
            if hasattr(self, 'message_thread'):
                self.message_thread.join(timeout=5)
            if hasattr(self, 'health_thread'):
                self.health_thread.join(timeout=5)

            # Clean up core services
            cleanup_errors = []

            try:
                if self.memory_store:
                    self.memory_store.close()
                    self.logger.info("Memory store closed")
            except Exception as e:
                cleanup_errors.append(f"Memory store cleanup error: {e}")
                self.logger.error("Failed to close memory store", exc_info=True)

            try:
                if self.message_broker:
                    self.message_broker.close()
                    self.logger.info("Message broker closed")
            except Exception as e:
                cleanup_errors.append(f"Message broker cleanup error: {e}")
                self.logger.error("Failed to close message broker", exc_info=True)

            try:
                if self.code_executor:
                    self.code_executor.cleanup()
                    self.logger.info("Code executor cleaned up")
            except Exception as e:
                cleanup_errors.append(f"Code executor cleanup error: {e}")
                self.logger.error("Failed to cleanup code executor", exc_info=True)

            cleanup_time = (datetime.now() - start_time).total_seconds()
            self.metrics.record_metric('cleanup_time', cleanup_time)

            if cleanup_errors:
                raise Exception("; ".join(cleanup_errors))

            self._emit_action("Cleanup completed", "Success")
            self.metrics.record_event('cleanup_completed')
            self.logger.info("Cleanup completed successfully")

        except Exception as e:
            self._emit_error(f"Failed to cleanup: {str(e)}")
            self.metrics.record_event('cleanup_error', {'error': str(e)})
            self.logger.error(f"Failed to cleanup: {e}", exc_info=True)
            raise

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with error handling."""
        try:
            self.cleanup()
        except Exception as e:
            self.logger.error(f"Error in context manager exit: {e}", exc_info=True)
            self.metrics.record_event('context_manager_error', {'error': str(e)})
            raise
