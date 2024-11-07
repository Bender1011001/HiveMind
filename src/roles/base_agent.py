"""Base agent class providing common functionality for all agents."""

import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import traceback
from ..memory.context_manager import SharedContext
from ..memory.mongo_store import MongoMemoryStore
from ..communication.broker import MessageBroker
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
        
    def _emit_thought_process(self, thought: str, context: Optional[Dict] = None):
        """Emit a thought process event."""
        self.event_bus.emit('agent_thought_process', {
            'agent_id': self.agent_id,
            'thought': thought,
            'context': context or {},
            'timestamp': datetime.utcnow().isoformat()
        })

    def _emit_action(self, action: str, result: Any = None):
        """Emit an action event."""
        self.event_bus.emit('agent_action', {
            'agent_id': self.agent_id,
            'action': action,
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        })

    def _emit_error(self, error: str, context: Optional[Dict] = None):
        """Emit an error event."""
        self.event_bus.emit('agent_error', {
            'agent_id': self.agent_id,
            'error': str(error),
            'stack_trace': traceback.format_exc(),
            'context': context or {},
            'timestamp': datetime.utcnow().isoformat()
        })

    def _emit_api_interaction(self, operation: str, request: Dict, response: Optional[Dict] = None, status: str = 'pending'):
        """Emit an API interaction event."""
        self.event_bus.emit('agent_api_interaction', {
            'agent_id': self.agent_id,
            'operation': operation,
            'request': request,
            'response': response,
            'status': status,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def _setup_workspace(self):
        """Set up agent's workspace directories."""
        try:
            for path in self.workspace.values():
                os.makedirs(path, exist_ok=True)
            self._emit_action("Setting up workspace directories", "Success")
        except Exception as e:
            self._emit_error(f"Failed to set up workspace: {str(e)}")
            raise
            
    def save_code(self, code: str, filename: str, language: str) -> str:
        """Save code to agent's workspace."""
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
        """Read code from agent's workspace."""
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
        """Save data to agent's workspace."""
        try:
            file_path = os.path.join(self.workspace['data'], filename)
            with open(file_path, 'w') as f:
                if isinstance(data, (dict, list)):
                    import json
                    json.dump(data, f, indent=2)
                else:
                    f.write(str(data))
            self._emit_action(f"Saving data to {filename}", "Success")
            return file_path
        except Exception as e:
            self._emit_error(f"Failed to save data: {str(e)}")
            raise
        
    def read_data(self, filename: str) -> Optional[str]:
        """Read data from agent's workspace."""
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
        """Execute code and save to workspace."""
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
        """Update progress on a task."""
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
        """Share knowledge with other agents."""
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
        """Get learnings shared by other agents."""
        try:
            self._emit_thought_process("Retrieving shared learnings", {"category": category})
            learnings = self.shared_context.get_agent_learnings(category=category)
            self._emit_action("Retrieved shared learnings", f"Found {len(learnings)} entries")
            return learnings
        except Exception as e:
            self._emit_error(f"Failed to get shared learnings: {str(e)}")
            raise
        
    def get_shared_knowledge(self, key: Optional[str] = None) -> Dict:
        """Get knowledge shared by other agents."""
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
        """Send a message to another agent."""
        try:
            self._emit_thought_process(
                f"Sending message to {receiver_id}",
                {"content_type": type(content).__name__, "task_id": task_id}
            )
            message = {
                'sender_id': self.agent_id,
                'receiver_id': receiver_id,
                'content': content,
                'task_id': task_id,
                'timestamp': datetime.utcnow().isoformat()
            }
            self.message_broker.send_message(message)
            self._emit_action("Sent message", "Success")
        except Exception as e:
            self._emit_error(f"Failed to send message: {str(e)}")
            raise
        
    def get_messages(self) -> List[Dict]:
        """Get messages sent to this agent."""
        try:
            self._emit_thought_process("Retrieving messages")
            messages = self.message_broker.get_messages(self.agent_id)
            self._emit_action("Retrieved messages", f"Found {len(messages)} messages")
            return messages
        except Exception as e:
            self._emit_error(f"Failed to get messages: {str(e)}")
            raise
        
    def cleanup(self):
        """Clean up resources."""
        try:
            self._emit_thought_process("Cleaning up resources")
            self.memory_store.close()
            self.message_broker.close()
            self.code_executor.cleanup()
            self._emit_action("Cleanup completed", "Success")
        except Exception as e:
            self._emit_error(f"Failed to cleanup: {str(e)}")
            raise
