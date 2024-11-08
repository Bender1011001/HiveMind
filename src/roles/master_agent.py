from typing import List, Dict, Optional, Any
from .capability import Capability, AgentCapability, CapabilityRegister
from .role_manager import Task, RoleManager
from datetime import datetime, timedelta
import logging
import json
from src.communication.message import Message, MessageType
from src.memory.mongo_store import MongoMemoryStore
from src.communication.broker import MessageBroker

logger = logging.getLogger(__name__)

class MasterAgent:
    """Master Agent that analyzes tasks and delegates them appropriately."""
    
    def __init__(self, role_manager: RoleManager, capability_register: CapabilityRegister,
                 memory_store: MongoMemoryStore, message_broker: MessageBroker):
        """Initialize Master Agent with full capabilities and communication handlers."""
        self.role_manager = role_manager
        self.capability_register = capability_register
        self.memory_store = memory_store
        self.message_broker = message_broker
        self.agent_id = "master_agent"
        self.is_paused = False
        
        # Register master agent with all capabilities at maximum strength
        capabilities = [
            AgentCapability(capability=cap, strength=1.0)
            for cap in Capability
        ]
        self.capability_register.register_agent(self.agent_id, capabilities)
        
        # Set up message handling
        self._setup_message_handling()
        
    def _setup_message_handling(self):
        """Set up message broker subscription and handlers."""
        try:
            if self.message_broker:
                self.message_broker.subscribe(self.agent_id, self._handle_message)
                logger.info("Successfully set up message handling for master agent")
        except Exception as e:
            logger.error(f"Failed to set up message handling: {e}")
            raise
            
    def _handle_message(self, message: Message):
        """Handle incoming messages based on type."""
        try:
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
            logger.error(f"Error handling message: {e}")
            self._store_error_response(message, str(e))
            
    def _handle_control_message(self, message: Message):
        """Handle control messages for agent management."""
        try:
            command = message.content.get("command")
            if command == "pause":
                self.is_paused = True
                logger.info("Agent paused")
            elif command == "resume":
                self.is_paused = False
                logger.info("Agent resumed")
            else:
                logger.warning(f"Unknown control command: {command}")
                
        except Exception as e:
            logger.error(f"Error handling control message: {e}")
            
    def _handle_text_message(self, message: Message):
        """Process text messages and delegate tasks."""
        try:
            # Store message receipt
            self._store_message_receipt(message)
            
            # Analyze message and create task
            text_content = message.content.get("text", "")
            required_capabilities = self.analyze_request(text_content)
            
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
            
            # Assign task and get response
            assigned_agent = self.role_manager.assign_task(task)
            if assigned_agent:
                response = self._create_success_response(message, assigned_agent, task)
            else:
                response = self._create_error_response(message, "No suitable agent available")
                
            # Store and send response
            self._store_and_send_response(response)
            
        except Exception as e:
            logger.error(f"Error handling text message: {e}")
            self._store_error_response(message, str(e))
            
    def _determine_priority(self, message: Message) -> int:
        """Determine task priority based on message content and metadata."""
        try:
            # Default priority is 3 (medium)
            priority = 3
            
            # Check for urgent keywords
            urgent_keywords = ['urgent', 'asap', 'emergency', 'critical']
            text_content = message.content.get("text", "").lower()
            if any(keyword in text_content for keyword in urgent_keywords):
                priority = 1  # High priority
                
            # Check message metadata for priority hints
            metadata = message.metadata or {}
            if 'priority' in metadata:
                try:
                    priority = int(metadata['priority'])
                    priority = max(1, min(5, priority))  # Ensure priority is between 1-5
                except (ValueError, TypeError):
                    pass
                    
            return priority
            
        except Exception as e:
            logger.error(f"Error determining priority: {e}")
            return 3  # Return default priority on error
            
    def _store_message_receipt(self, message: Message):
        """Store received message in memory store."""
        try:
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
        except Exception as e:
            logger.error(f"Failed to store message receipt: {e}")
            
    def _create_success_response(self, original_message: Message, assigned_agent: str, task: Task) -> Message:
        """Create success response message."""
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
        
    def _create_error_response(self, original_message: Message, error: str) -> Message:
        """Create error response message."""
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
        
    def _store_and_send_response(self, response: Message):
        """Store and send response message."""
        try:
            # Store response
            if self.memory_store:
                self.memory_store.store_memory(
                    agent_id=self.agent_id,
                    memory_type="message_response",
                    content=response.to_dict()
                )
                
            # Send response
            if self.message_broker:
                self.message_broker.send_message(response)
                
        except Exception as e:
            logger.error(f"Error storing/sending response: {e}")
            
    def _store_error_response(self, original_message: Message, error: str):
        """Store error response in case of processing failure."""
        try:
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
        except Exception as e:
            logger.error(f"Failed to store error response: {e}")
            
    def analyze_request(self, request: str) -> List[Capability]:
        """Analyze user request to determine required capabilities."""
        required_capabilities = set()
        
        # Language processing needs
        if any(kw in request.lower() for kw in ['write', 'summarize', 'explain', 'translate']):
            required_capabilities.add(Capability.TECHNICAL_WRITING)
            required_capabilities.add(Capability.CREATIVE_WRITING)
            
        # Code related needs
        if any(kw in request.lower() for kw in ['code', 'program', 'function', 'class', 'implement']):
            required_capabilities.add(Capability.CODE_GENERATION)
            required_capabilities.add(Capability.CODE_REVIEW)
            
        # Analysis needs
        if any(kw in request.lower() for kw in ['analyze', 'evaluate', 'assess']):
            required_capabilities.add(Capability.CRITICAL_ANALYSIS)
            required_capabilities.add(Capability.DATA_ANALYSIS)
            
        # Research needs
        if any(kw in request.lower() for kw in ['research', 'find', 'search']):
            required_capabilities.add(Capability.RESEARCH)
            required_capabilities.add(Capability.FACT_CHECKING)
            
        # Task management needs
        if any(kw in request.lower() for kw in ['plan', 'organize', 'manage']):
            required_capabilities.add(Capability.TASK_PLANNING)
            required_capabilities.add(Capability.TASK_PRIORITIZATION)
            
        # Chat/communication needs
        if any(kw in request.lower() for kw in ['chat', 'talk', 'discuss', 'converse']):
            required_capabilities.add(Capability.CONVERSATION)
            required_capabilities.add(Capability.EMOTIONAL_INTELLIGENCE)
            
        # If no specific capabilities detected, add basic ones
        if not required_capabilities:
            required_capabilities.add(Capability.LOGICAL_REASONING)
            required_capabilities.add(Capability.CRITICAL_ANALYSIS)
            required_capabilities.add(Capability.CONVERSATION)
            
        return list(required_capabilities)
        
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get detailed status of a specific task."""
        try:
            assigned_agent = self.role_manager.get_task_agent(task_id)
            if not assigned_agent:
                return {"status": "not_found"}
                
            task_history = self.role_manager.get_task_history(task_id)
            if not task_history:
                return {"status": "unknown"}
                
            latest_assignment = task_history[-1]
            
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
                
            return {
                "status": "active" if assigned_agent else "completed",
                "assigned_agent": assigned_agent,
                "assigned_at": latest_assignment.assigned_at.isoformat(),
                "completed_at": getattr(latest_assignment, 'completed_at', None),
                "capability_match_score": latest_assignment.capability_match_score,
                "message_count": len(task_messages),
                "last_update": task_messages[-1]['timestamp'] if task_messages else None
            }
            
        except Exception as e:
            logger.error(f"Error getting task status: {e}")
            return {"status": "error", "error": str(e)}
