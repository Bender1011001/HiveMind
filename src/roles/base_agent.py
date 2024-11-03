"""Base agent class providing common functionality for all agents."""

import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from ..memory.context_manager import SharedContext
from ..memory.mongo_store import MongoMemoryStore
from ..communication.broker import MessageBroker
from ..execution.code_executor import CodeExecutor
from .capability import Capability, AgentCapability
from ..settings import settings

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
        
        # Set up agent workspace
        self.workspace = {
            'code': os.path.join(settings.shared_code_dir, agent_id),
            'data': os.path.join(settings.shared_data_dir, agent_id),
            'output': os.path.join(settings.shared_output_dir, agent_id)
        }
        self._setup_workspace()
        
    def _setup_workspace(self):
        """Set up agent's workspace directories."""
        for path in self.workspace.values():
            os.makedirs(path, exist_ok=True)
            
    def save_code(self, code: str, filename: str, language: str) -> str:
        """Save code to agent's workspace."""
        file_path = os.path.join(self.workspace['code'], filename)
        with open(file_path, 'w') as f:
            f.write(code)
        return file_path
        
    def read_code(self, filename: str) -> Optional[str]:
        """Read code from agent's workspace."""
        file_path = os.path.join(self.workspace['code'], filename)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return f.read()
        return None
        
    def save_data(self, data: Any, filename: str) -> str:
        """Save data to agent's workspace."""
        file_path = os.path.join(self.workspace['data'], filename)
        with open(file_path, 'w') as f:
            if isinstance(data, (dict, list)):
                import json
                json.dump(data, f, indent=2)
            else:
                f.write(str(data))
        return file_path
        
    def read_data(self, filename: str) -> Optional[str]:
        """Read data from agent's workspace."""
        file_path = os.path.join(self.workspace['data'], filename)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return f.read()
        return None
        
    def execute_code(self, code: str, language: str, 
                    save_as: Optional[str] = None) -> tuple:
        """Execute code and save to workspace."""
        if save_as:
            self.save_code(code, save_as, language)
        return self.code_executor.execute_code(
            code, language, filename=save_as
        )
        
    def share_learning(self, learning: Dict[str, Any], 
                      category: Optional[str] = None):
        """Share a learning point with other agents."""
        self.shared_context.add_agent_learning(
            self.agent_id, learning, category
        )
        
    def update_task_progress(self, task_id: str, progress: Dict[str, Any]):
        """Update progress on a task."""
        self.shared_context.update_task_progress(
            task_id, self.agent_id, progress
        )
        
    def share_knowledge(self, key: str, value: Any):
        """Share knowledge with other agents."""
        self.shared_context.update_shared_knowledge(
            key, value, self.agent_id
        )
        
    def get_shared_learnings(self, category: Optional[str] = None) -> List[Dict]:
        """Get learnings shared by other agents."""
        return self.shared_context.get_agent_learnings(category=category)
        
    def get_shared_knowledge(self, key: Optional[str] = None) -> Dict:
        """Get knowledge shared by other agents."""
        return self.shared_context.get_shared_knowledge(key)
        
    def send_message(self, receiver_id: str, content: Dict[str, Any], 
                    task_id: Optional[str] = None):
        """Send a message to another agent."""
        self.message_broker.send_message({
            'sender_id': self.agent_id,
            'receiver_id': receiver_id,
            'content': content,
            'task_id': task_id,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    def get_messages(self) -> List[Dict]:
        """Get messages sent to this agent."""
        return self.message_broker.get_messages(self.agent_id)
        
    def cleanup(self):
        """Clean up resources."""
        self.memory_store.close()
        self.message_broker.close()
        self.code_executor.cleanup()
