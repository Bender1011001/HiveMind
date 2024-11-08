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
from ..memory.context_manager import SharedContext
from ..memory.mongo_store import MongoMemoryStore
from ..communication.broker import MessageBroker
from ..communication.message import Message, MessageType
from ..execution.code_executor import CodeExecutor
from .capability import Capability, AgentCapability
from ..settings import settings
from ..utils.event_bus import EventBus

logger = logging.getLogger(__name__)

class BaseAgent:
    """Base class for all agents in the system."""
    
    def __init__(self, agent_id: str, capabilities: List[AgentCapability]):
        """Initialize base agent with core functionality."""
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.is_running = True
        self.lock = Lock()
        
        # Message handling
        self.message_queue = Queue()
        self.pending_messages: Dict[str, Tuple[Message, int, datetime]] = {}  # message_id -> (message, retry_count, last_attempt)
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
        # Initialize core services
        self.memory_store = MongoMemoryStore()
        self.message_broker = MessageBroker()
        self.code_executor = CodeExecutor()
        self.shared_context = SharedContext(self.memory_store)
        self.event_bus = EventBus()
        
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
        
        # Start health check thread
        self.health_thread = Thread(target=self._report_health_status, daemon=True)
        self.health_thread.start()
        
    def _emit_thought_process(self, thought: str, context: Optional[Dict] = None):
        """Emit a thought process event with error handling."""
        try:
            self.event_bus.emit('agent_thought_process', {
                'agent_id': self.agent_id,
                'thought': thought,
                'context': context or {},
                'timestamp': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to emit thought process: {e}")

    def _emit_action(self, action: str, result: Any = None):
        """Emit an action event with error handling."""
        try:
            self.event_bus.emit('agent_action', {
                'agent_id': self.agent_id,
                'action': action,
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to emit action: {e}")

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
            logger.error(f"Agent {self.agent_id} error: {error}", extra=error_context)
        except Exception as e:
            logger.error(f"Failed to emit error: {e}")

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
        except Exception as e:
            logger.error(f"Failed to emit API interaction: {e}")
            
    def _process_message_queue(self):
        """Process messages from the queue with retry mechanism."""
        while self.is_running:
            try:
                # Process pending retries
                self._handle_pending_retries()
                
                # Process new messages
                try:
                    message = self.message_queue.get(timeout=1)
                    self._handle_message(message)
                except Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
            except Exception as e:
                logger.error(f"Error in message processing loop: {e}")
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
                    logger.info(f"Retrying message {msg_id} (attempt {retry_count + 1})")
                    self.pending_messages[msg_id] = (message, retry_count + 1, current_time)
                    self._handle_message(message, is_retry=True)
                else:
                    logger.error(f"Message {msg_id} failed after {self.max_retries} attempts")
                    self._handle_message_failure(message, f"Failed after {self.max_retries} attempts")
                    del self.pending_messages[msg_id]
                    
    def _handle_message(self, message: Message, is_retry: bool = False):
        """Handle a single message with error recovery."""
        try:
            if not is_retry:
                self._emit_thought_process(f"Processing message: {message.message_type}")
                
            if message.message_type == MessageType.CONTROL:
                self._handle_control_message(message)
            elif message.message_type == MessageType.TEXT:
                self._handle_text_message(message)
            else:
                logger.warning(f"Unsupported message type: {message.message_type}")
                
            # Message processed successfully
            if message.message_id in self.pending_messages:
                del self.pending_messages[message.message_id]
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            if not is_retry:
                # Add to pending messages for retry
                self.pending_messages[message.message_id] = (message, 0, datetime.utcnow())
            self._emit_error(f"Message handling error: {e}", {"message_id": message.message_id})
            
    def _handle_message_failure(self, message: Message, reason: str):
        """Handle permanent message failure."""
        try:
            self._emit_error(f"Message permanently failed: {reason}", {
                "message_id": message.message_id,
                "message_type": message.message_type
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
        except Exception as e:
            logger.error(f"Error handling message failure: {e}")
            
    def _handle_control_message(self, message: Message):
        """Handle control messages."""
        try:
            command = message.content.get("command")
            if command == "pause":
                self.is_running = False
                self._emit_action("Agent paused")
            elif command == "resume":
                self.is_running = True
                self._emit_action("Agent resumed")
            elif command == "status":
                self._report_status(message.sender_id)
            else:
                logger.warning(f"Unknown control command: {command}")
        except Exception as e:
            logger.error(f"Error handling control message: {e}")
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
            response_content = self._process_text_content(message.content)
            
            # Send response if needed
            if response_content:
                self.send_message(
                    message.sender_id,
                    response_content,
                    message.task_id
                )
                
        except Exception as e:
            logger.error(f"Error handling text message: {e}")
            raise
            
    def _process_text_content(self, content: Dict) -> Optional[Dict]:
        """Process text message content. Override in subclasses."""
        return None
        
    def _report_health_status(self):
        """Periodically report agent health status."""
        while self.is_running:
            try:
                health_status = {
                    "agent_id": self.agent_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "healthy" if self.is_running else "paused",
                    "message_queue_size": self.message_queue.qsize(),
                    "pending_retries": len(self.pending_messages),
                    "memory_store_connected": bool(self.memory_store and getattr(self.memory_store, 'is_connected', False)),
                    "message_broker_connected": bool(self.message_broker and hasattr(self.message_broker, 'connection') and 
                                                   not self.message_broker.connection.is_closed)
                }
                
                if self.memory_store:
                    self.memory_store.store_memory(
                        agent_id=self.agent_id,
                        memory_type="health_status",
                        content=health_status
                    )
                    
                self._emit_action("Health status reported", health_status)
                
            except Exception as e:
                logger.error(f"Error reporting health status: {e}")
                
            time.sleep(60)  # Report every minute
            
    def _report_status(self, requester_id: str):
        """Report agent status on demand."""
        try:
            status = {
                "agent_id": self.agent_id,
                "status": "healthy" if self.is_running else "paused",
                "capabilities": [cap.capability.name for cap in self.capabilities],
                "message_queue_size": self.message_queue.qsize(),
                "pending_retries": len(self.pending_messages),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.send_message(
                requester_id,
                {"type": "status_report", "status": status},
                None
            )
            
        except Exception as e:
            logger.error(f"Error reporting status: {e}")
            
    def _setup_workspace(self):
        """Set up agent's workspace directories with error handling."""
        try:
            for path in self.workspace.values():
                os.makedirs(path, exist_ok=True)
            self._emit_action("Setting up workspace directories", "Success")
        except Exception as e:
            self._emit_error(f"Failed to set up workspace: {str(e)}")
            raise
            
    def save_code(self, code: str, filename: str, language: str) -> str:
        """Save code to agent's workspace with error handling."""
        try:
            file_path = os.path.join(self.workspace['code'], filename)
            with open(file_path, 'w') as f:
                f.write(code)
            self._emit_action(f"Saving code to {filename}", "Success")
            return file_path
        except Exception as e:
            self._emit_error(f"Failed to save code: {str(e)}")
            raise
        
    def read_code(self, filename: str) -> Optional[str]:
        """Read code from agent's workspace with error handling."""
        try:
            file_path = os.path.join(self.workspace['code'], filename)
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
                self._emit_action(f"Reading code from {filename}", "Success")
                return content
            self._emit_action(f"Reading code from {filename}", "File not found")
            return None
        except Exception as e:
            self._emit_error(f"Failed to read code: {str(e)}")
            raise
        
    def save_data(self, data: Any, filename: str) -> str:
        """Save data to agent's workspace with error handling."""
        try:
            file_path = os.path.join(self.workspace['data'], filename)
            with open(file_path, 'w') as f:
                if isinstance(data, (dict, list)):
                    json.dump(data, f, indent=2)
                else:
                    f.write(str(data))
            self._emit_action(f"Saving data to {filename}", "Success")
            return file_path
        except Exception as e:
            self._emit_error(f"Failed to save data: {str(e)}")
            raise
        
    def read_data(self, filename: str) -> Optional[str]:
        """Read data from agent's workspace with error handling."""
        try:
            file_path = os.path.join(self.workspace['data'], filename)
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
                self._emit_action(f"Reading data from {filename}", "Success")
                return content
            self._emit_action(f"Reading data from {filename}", "File not found")
            return None
        except Exception as e:
            self._emit_error(f"Failed to read data: {str(e)}")
            raise
        
    def execute_code(self, code: str, language: str, 
                    save_as: Optional[str] = None) -> tuple:
        """Execute code and save to workspace with error handling."""
        try:
            self._emit_thought_process(
                f"Executing {language} code",
                {"code_length": len(code), "save_as": save_as}
            )
            if save_as:
                self.save_code(code, save_as, language)
            result = self.code_executor.execute_code(
                code, language, filename=save_as
            )
            self._emit_action("Code execution", {"result": result[0], "error": result[1]})
            return result
        except Exception as e:
            self._emit_error(f"Failed to execute code: {str(e)}")
            raise
        
    def share_learning(self, learning: Dict[str, Any], 
                      category: Optional[str] = None):
        """Share a learning point with other agents."""
        try:
            self._emit_thought_process(
                "Sharing learning point",
                {"learning": learning, "category": category}
            )
            self.shared_context.add_agent_learning(
                self.agent_id, learning, category
            )
            self._emit_action("Shared learning point", "Success")
        except Exception as e:
            self._emit_error(f"Failed to share learning: {str(e)}")
            raise
        
    def update_task_progress(self, task_id: str, progress: Dict[str, Any]):
        """Update progress on a task with error handling."""
        try:
            self._emit_thought_process(
                f"Updating progress for task {task_id}",
                {"progress": progress}
            )
            self.shared_context.update_task_progress(
                task_id, self.agent_id, progress
            )
            self._emit_action("Updated task progress", "Success")
        except Exception as e:
            self._emit_error(f"Failed to update task progress: {str(e)}")
            raise
        
    def share_knowledge(self, key: str, value: Any):
        """Share knowledge with other agents with error handling."""
        try:
            self._emit_thought_process(
                f"Sharing knowledge: {key}",
                {"value": str(value)[:100] + "..." if isinstance(value, str) and len(str(value)) > 100 else value}
            )
            self.shared_context.update_shared_knowledge(
                key, value, self.agent_id
            )
            self._emit_action("Shared knowledge", "Success")
        except Exception as e:
            self._emit_error(f"Failed to share knowledge: {str(e)}")
            raise
        
    def get_shared_learnings(self, category: Optional[str] = None) -> List[Dict]:
        """Get learnings shared by other agents with error handling."""
        try:
            self._emit_thought_process("Retrieving shared learnings", {"category": category})
            learnings = self.shared_context.get_agent_learnings(category=category)
            self._emit_action("Retrieved shared learnings", f"Found {len(learnings)} entries")
            return learnings
        except Exception as e:
            self._emit_error(f"Failed to get shared learnings: {str(e)}")
            raise
        
    def get_shared_knowledge(self, key: Optional[str] = None) -> Dict:
        """Get knowledge shared by other agents with error handling."""
        try:
            self._emit_thought_process("Retrieving shared knowledge", {"key": key})
            knowledge = self.shared_context.get_shared_knowledge(key)
            self._emit_action("Retrieved shared knowledge", f"Found {len(knowledge)} entries")
            return knowledge
        except Exception as e:
            self._emit_error(f"Failed to get shared knowledge: {str(e)}")
            raise
        
    def send_message(self, receiver_id: str, content: Dict[str, Any], 
                    task_id: Optional[str] = None):
        """Send a message to another agent with retry mechanism."""
        try:
            self._emit_thought_process(
                f"Sending message to {receiver_id}",
                {"content_type": type(content).__name__, "task_id": task_id}
            )
            
            message = Message(
                sender_id=self.agent_id,
                receiver_id=receiver_id,
                message_type=MessageType.TEXT,
                content=content,
                task_id=task_id
            )
            
            success = self.message_broker.send_message(message)
            if not success:
                # Add to pending messages for retry
                self.pending_messages[message.message_id] = (message, 0, datetime.utcnow())
                logger.warning(f"Message send failed, queued for retry: {message.message_id}")
            else:
                self._emit_action("Sent message", "Success")
                
        except Exception as e:
            self._emit_error(f"Failed to send message: {str(e)}")
            raise
        
    def get_messages(self) -> List[Dict]:
        """Get messages sent to this agent with error handling."""
        try:
            self._emit_thought_process("Retrieving messages")
            messages = self.message_broker.get_messages(self.agent_id)
            self._emit_action("Retrieved messages", f"Found {len(messages)} messages")
            return messages
        except Exception as e:
            self._emit_error(f"Failed to get messages: {str(e)}")
            raise
        
    def cleanup(self):
        """Clean up resources with proper error handling."""
        try:
            self._emit_thought_process("Cleaning up resources")
            
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
            except Exception as e:
                cleanup_errors.append(f"Memory store cleanup error: {e}")
                
            try:
                if self.message_broker:
                    self.message_broker.close()
            except Exception as e:
                cleanup_errors.append(f"Message broker cleanup error: {e}")
                
            try:
                if self.code_executor:
                    self.code_executor.cleanup()
            except Exception as e:
                cleanup_errors.append(f"Code executor cleanup error: {e}")
                
            if cleanup_errors:
                raise Exception("; ".join(cleanup_errors))
                
            self._emit_action("Cleanup completed", "Success")
            
        except Exception as e:
            self._emit_error(f"Failed to cleanup: {str(e)}")
            raise
            
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with error handling."""
        try:
            self.cleanup()
        except Exception as e:
            logger.error(f"Error in context manager exit: {e}")
            raise
