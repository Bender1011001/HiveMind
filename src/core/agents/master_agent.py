from typing import List, Dict, Optional, Any
from .capability import Capability, AgentCapability, CapabilityRegister
from .role_manager import Task, RoleManager
from datetime import datetime, timedelta
import json
from ..messaging.message import Message, MessageType
from ..storage.mongo_store import MongoMemoryStore
from ..messaging.broker import MessageBroker
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

class MasterAgent:
    """Master Agent that analyzes tasks and delegates them appropriately."""

    def __init__(self, role_manager: RoleManager, capability_register: CapabilityRegister,
                 memory_store: MongoMemoryStore, message_broker: MessageBroker):
        """Initialize Master Agent with full capabilities and communication handlers."""
        try:
            logger.info("Initializing Master Agent")
            self.role_manager = role_manager
            self.capability_register = capability_register
            self.memory_store = memory_store
            self.message_broker = message_broker
            self.agent_id = "master_agent"
            self.is_paused = False

            # Register master agent with all capabilities at maximum strength
            logger.debug("Registering master agent capabilities")
            capabilities = [
                AgentCapability(capability=cap, strength=1.0)
                for cap in Capability
            ]
            self.capability_register.register_agent(self.agent_id, capabilities)
            logger.info(f"Registered {len(capabilities)} capabilities for master agent")

            # Set up message handling
            self._setup_message_handling()
            logger.info("Master Agent initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Master Agent: {str(e)}", exc_info=True)
            raise

    def _setup_message_handling(self):
        """Set up message broker subscription and handlers."""
        try:
            logger.debug("Setting up message handling")
            if self.message_broker:
                self.message_broker.subscribe(self.agent_id, self._handle_message)
                logger.info("Successfully set up message handling for master agent")
            else:
                logger.warning("No message broker available, message handling disabled")
        except Exception as e:
            logger.error(f"Failed to set up message handling: {str(e)}", exc_info=True)
            raise

    def _handle_message(self, message: Message):
        """Handle incoming messages based on type."""
        try:
            logger.debug(f"Handling message of type {message.message_type} from {message.sender_id}")

            if self.is_paused and message.message_type != MessageType.CONTROL:
                logger.info("Agent is paused, ignoring non-control message")
                return

            if message.message_type == MessageType.CONTROL:
                self._handle_control_message(message)
            elif message.message_type == MessageType.TEXT:
                self._handle_text_message(message)
            else:
                logger.warning(f"Unsupported message type: {message.message_type}")

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            self._store_error_response(message, str(e))

    def _handle_control_message(self, message: Message):
        """Handle control messages for agent management."""
        try:
            command = message.content.get("command")
            logger.info(f"Processing control command: {command}")

            if command == "pause":
                self.is_paused = True
                logger.info("Agent paused")
            elif command == "resume":
                self.is_paused = False
                logger.info("Agent resumed")
            else:
                logger.warning(f"Unknown control command: {command}")

        except Exception as e:
            logger.error(f"Error handling control message: {str(e)}", exc_info=True)

    def _handle_text_message(self, message: Message):
        """Process text messages and delegate tasks."""
        try:
            logger.info(f"Processing text message from {message.sender_id}")

            # Store message receipt
            self._store_message_receipt(message)

            # Analyze message and create task
            text_content = message.content.get("text", "")
            logger.debug(f"Analyzing request: {text_content[:100]}...")
            required_capabilities = self.analyze_request(text_content)
            logger.debug(f"Required capabilities: {[cap.name for cap in required_capabilities]}")

            task = Task(
                task_id=message.task_id or f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                required_capabilities=required_capabilities,
                priority=self._determine_priority(message),
                deadline=datetime.utcnow() + timedelta(hours=24),
                metadata={
                    "original_message": message.to_dict(),
                    "sender_id": message.sender_id
                }
            )
            logger.info(f"Created task {task.task_id} with priority {task.priority}")

            # Assign task and get response
            assigned_agent = self.role_manager.assign_task(task)
            if assigned_agent:
                logger.info(f"Task {task.task_id} assigned to agent {assigned_agent}")
                response = self._create_success_response(message, assigned_agent, task)
            else:
                logger.warning(f"No suitable agent found for task {task.task_id}")
                response = self._create_error_response(message, "No suitable agent available")

            # Store and send response
            self._store_and_send_response(response)

        except Exception as e:
            logger.error(f"Error handling text message: {str(e)}", exc_info=True)
            self._store_error_response(message, str(e))

    def _determine_priority(self, message: Message) -> int:
        """Determine task priority based on message content and metadata."""
        try:
            logger.debug("Determining message priority")
            # Default priority is 3 (medium)
            priority = 3

            # Check for urgent keywords
            urgent_keywords = ['urgent', 'asap', 'emergency', 'critical']
            text_content = message.content.get("text", "").lower()
            if any(keyword in text_content for keyword in urgent_keywords):
                priority = 1  # High priority
                logger.debug(f"Found urgent keyword, setting priority to {priority}")

            # Check message metadata for priority hints
            metadata = message.metadata or {}
            if 'priority' in metadata:
                try:
                    priority = int(metadata['priority'])
                    priority = max(1, min(5, priority))  # Ensure priority is between 1-5
                    logger.debug(f"Using metadata priority: {priority}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid priority in metadata: {e}")

            logger.info(f"Determined priority: {priority}")
            return priority

        except Exception as e:
            logger.error(f"Error determining priority: {str(e)}", exc_info=True)
            return 3  # Return default priority on error

    def _store_message_receipt(self, message: Message):
        """Store received message in memory store."""
        try:
            logger.debug(f"Storing message receipt for message {message.message_id}")
            if self.memory_store:
                self.memory_store.store_memory(
                    agent_id=self.agent_id,
                    memory_type="message_receipt",
                    content={
                        "message_id": message.message_id,
                        "sender_id": message.sender_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "content": message.content
                    }
                )
                logger.debug("Message receipt stored successfully")
            else:
                logger.warning("No memory store available, skipping message receipt storage")
        except Exception as e:
            logger.error(f"Failed to store message receipt: {str(e)}", exc_info=True)

    def _create_success_response(self, original_message: Message, assigned_agent: str, task: Task) -> Message:
        """Create success response message."""
        try:
            logger.debug(f"Creating success response for task {task.task_id}")
            return Message(
                sender_id=self.agent_id,
                receiver_id=original_message.sender_id,
                message_type=MessageType.TEXT,
                content={
                    "type": "system",
                    "text": f"Message received and task assigned to {assigned_agent}",
                    "task_id": task.task_id,
                    "assigned_agent": assigned_agent
                },
                task_id=original_message.task_id,
                metadata={"status": "success"}
            )
        except Exception as e:
            logger.error(f"Error creating success response: {str(e)}", exc_info=True)
            raise

    def _create_error_response(self, original_message: Message, error: str) -> Message:
        """Create error response message."""
        try:
            logger.debug(f"Creating error response: {error}")
            return Message(
                sender_id=self.agent_id,
                receiver_id=original_message.sender_id,
                message_type=MessageType.TEXT,
                content={
                    "type": "error",
                    "text": f"Error processing message: {error}",
                    "error": error
                },
                task_id=original_message.task_id,
                metadata={"status": "error"}
            )
        except Exception as e:
            logger.error(f"Error creating error response: {str(e)}", exc_info=True)
            raise

    def _store_and_send_response(self, response: Message):
        """Store and send response message."""
        try:
            logger.debug(f"Storing and sending response for task {response.task_id}")

            # Store response
            if self.memory_store:
                self.memory_store.store_memory(
                    agent_id=self.agent_id,
                    memory_type="message_response",
                    content=response.to_dict()
                )
                logger.debug("Response stored successfully")
            else:
                logger.warning("No memory store available, skipping response storage")

            # Send response
            if self.message_broker:
                self.message_broker.send_message(response)
                logger.debug("Response sent successfully")
            else:
                logger.warning("No message broker available, skipping response sending")

        except Exception as e:
            logger.error(f"Error storing/sending response: {str(e)}", exc_info=True)

    def _store_error_response(self, original_message: Message, error: str):
        """Store error response in case of processing failure."""
        try:
            logger.debug(f"Storing error response: {error}")
            if self.memory_store:
                self.memory_store.store_memory(
                    agent_id=self.agent_id,
                    memory_type="error",
                    content={
                        "error": str(error),
                        "original_message": original_message.to_dict(),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                logger.debug("Error response stored successfully")
            else:
                logger.warning("No memory store available, skipping error response storage")
        except Exception as e:
            logger.error(f"Failed to store error response: {str(e)}", exc_info=True)

    def analyze_request(self, request: str) -> List[Capability]:
        """Analyze user request to determine required capabilities."""
        try:
            logger.debug(f"Analyzing request: {request[:100]}...")
            required_capabilities = set()

            # Language processing needs
            if any(kw in request.lower() for kw in ['write', 'summarize', 'explain', 'translate']):
                required_capabilities.add(Capability.TECHNICAL_WRITING)
                required_capabilities.add(Capability.CREATIVE_WRITING)
                logger.debug("Added language processing capabilities")

            # Code related needs
            if any(kw in request.lower() for kw in ['code', 'program', 'function', 'class', 'implement']):
                required_capabilities.add(Capability.CODE_GENERATION)
                required_capabilities.add(Capability.CODE_REVIEW)
                logger.debug("Added code-related capabilities")

            # Analysis needs
            if any(kw in request.lower() for kw in ['analyze', 'evaluate', 'assess']):
                required_capabilities.add(Capability.CRITICAL_ANALYSIS)
                required_capabilities.add(Capability.DATA_ANALYSIS)
                logger.debug("Added analysis capabilities")

            # Research needs
            if any(kw in request.lower() for kw in ['research', 'find', 'search']):
                required_capabilities.add(Capability.RESEARCH)
                required_capabilities.add(Capability.FACT_CHECKING)
                logger.debug("Added research capabilities")

            # Task management needs
            if any(kw in request.lower() for kw in ['plan', 'organize', 'manage']):
                required_capabilities.add(Capability.TASK_PLANNING)
                required_capabilities.add(Capability.TASK_PRIORITIZATION)
                logger.debug("Added task management capabilities")

            # If no specific capabilities detected, add basic ones
            if not required_capabilities:
                required_capabilities.add(Capability.LOGICAL_REASONING)
                required_capabilities.add(Capability.CRITICAL_ANALYSIS)
                logger.debug("Added default capabilities")

            logger.info(f"Identified {len(required_capabilities)} required capabilities")
            return list(required_capabilities)

        except Exception as e:
            logger.error(f"Error analyzing request: {str(e)}", exc_info=True)
            raise

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get detailed status of a specific task."""
        try:
            logger.info(f"Getting status for task {task_id}")

            assigned_agent = self.role_manager.get_task_agent(task_id)
            if not assigned_agent:
                logger.debug(f"Task {task_id} not found")
                return {"status": "not_found"}

            task_history = self.role_manager.get_task_history(task_id)
            if not task_history:
                logger.debug(f"No history found for task {task_id}")
                return {"status": "unknown"}

            latest_assignment = task_history[-1]
            logger.debug(f"Found latest assignment for task {task_id}")

            # Get task messages from memory store
            task_messages = []
            if self.memory_store:
                memories = self.memory_store.retrieve_memories(
                    memory_type="message_response",
                    limit=100
                )
                task_messages = [
                    m for m in memories
                    if m.get('content', {}).get('task_id') == task_id
                ]
                logger.debug(f"Found {len(task_messages)} messages for task {task_id}")

            status = {
                "status": "active" if assigned_agent else "completed",
                "assigned_agent": assigned_agent,
                "assigned_at": latest_assignment.assigned_at.isoformat(),
                "completed_at": getattr(latest_assignment, 'completed_at', None),
                "capability_match_score": latest_assignment.capability_match_score,
                "message_count": len(task_messages),
                "last_update": task_messages[-1]['timestamp'] if task_messages else None
            }

            logger.info(f"Task {task_id} status: {status['status']}")
            return status

        except Exception as e:
            logger.error(f"Error getting task status: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}
