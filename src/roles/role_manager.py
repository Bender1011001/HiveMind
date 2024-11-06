from typing import Dict, List, Optional, Tuple
from .capability import Capability, CapabilityRegister
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from threading import Lock

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Task:
    """Represents a task that needs to be assigned to an agent."""
    task_id: str
    required_capabilities: List[Capability]
    priority: int  # 1 (lowest) to 5 (highest)
    deadline: Optional[datetime] = None
    metadata: Optional[Dict] = None
    created_at: datetime = datetime.utcnow()
    
    def validate(self):
        """Validate task parameters."""
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if not self.required_capabilities:
            raise ValueError("required_capabilities cannot be empty")
        if not all(isinstance(cap, Capability) for cap in self.required_capabilities):
            raise ValueError("All capabilities must be instances of Capability enum")
        if not isinstance(self.priority, int) or not 1 <= self.priority <= 5:
            raise ValueError("priority must be an integer between 1 and 5")
        if self.deadline and not isinstance(self.deadline, datetime):
            raise ValueError("deadline must be a datetime object")
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")

@dataclass
class TaskAssignment:
    """Represents a task assignment with additional metadata."""
    task: Task
    agent_id: str
    assigned_at: datetime = datetime.utcnow()
    capability_match_score: float = 0.0
    
class RoleManager:
    """Manages role assignment for tasks based on agent capabilities."""
    
    def __init__(self, capability_register: CapabilityRegister, max_tasks_per_agent: int = 3):
        """Initialize role manager with capability register."""
        if not isinstance(capability_register, CapabilityRegister):
            raise ValueError("capability_register must be an instance of CapabilityRegister")
        if not isinstance(max_tasks_per_agent, int) or max_tasks_per_agent < 1:
            raise ValueError("max_tasks_per_agent must be a positive integer")
            
        self.capability_register = capability_register
        self.max_tasks_per_agent = max_tasks_per_agent
        self.active_tasks: Dict[str, Dict[str, TaskAssignment]] = {}  # agent_id -> {task_id -> TaskAssignment}
        self.task_history: Dict[str, List[TaskAssignment]] = {}  # task_id -> List[TaskAssignment]
        self.lock = Lock()  # For thread safety
        
    def _calculate_agent_load(self, agent_id: str) -> float:
        """Calculate current load factor for an agent."""
        current_tasks = len(self.active_tasks.get(agent_id, {}))
        return current_tasks / self.max_tasks_per_agent
        
    def _calculate_capability_match(self, agent_id: str, task: Task) -> Tuple[float, int]:
        """Calculate capability match score and number of matching capabilities."""
        agent_capabilities = self.capability_register.get_agent_capabilities(agent_id)
        if not agent_capabilities:
            return 0.0, 0
            
        total_strength = 0.0
        capabilities_found = 0
        
        for required_cap in task.required_capabilities:
            for agent_cap in agent_capabilities:
                if agent_cap.capability == required_cap:
                    total_strength += agent_cap.strength
                    capabilities_found += 1
                    break
                    
        if capabilities_found != len(task.required_capabilities):
            return 0.0, capabilities_found
            
        return total_strength / len(task.required_capabilities), capabilities_found
        
    def assign_task(self, task: Task) -> Optional[str]:
        """Assign a task to the most suitable agent considering priority and deadlines."""
        try:
            task.validate()
            
            with self.lock:
                best_agent = None
                best_score = 0.0
                
                # Consider deadline in scoring
                deadline_factor = 1.0
                if task.deadline:
                    time_until_deadline = (task.deadline - datetime.utcnow()).total_seconds()
                    if time_until_deadline <= 0:
                        logger.warning(f"Task {task.task_id} is already past deadline")
                        return None
                    deadline_factor = min(2.0, 86400 / max(1, time_until_deadline))  # Higher score for closer deadlines
                
                for agent_id in self.capability_register.agent_capabilities:
                    # Skip overloaded agents
                    if len(self.active_tasks.get(agent_id, {})) >= self.max_tasks_per_agent:
                        continue
                        
                    # Calculate capability match
                    capability_score, capabilities_found = self._calculate_capability_match(agent_id, task)
                    if capabilities_found != len(task.required_capabilities):
                        continue
                        
                    # Calculate load factor (inverse, so less load = higher score)
                    load_factor = 1 - self._calculate_agent_load(agent_id)
                    
                    # Calculate final score considering all factors
                    final_score = (
                        capability_score * 0.4 +  # Capability match importance
                        load_factor * 0.3 +      # Load balancing importance
                        (task.priority / 5) * 0.2 +  # Task priority importance
                        deadline_factor * 0.1     # Deadline importance
                    )
                    
                    if final_score > best_score:
                        best_agent = agent_id
                        best_score = final_score
                
                if best_agent:
                    assignment = TaskAssignment(
                        task=task,
                        agent_id=best_agent,
                        capability_match_score=best_score
                    )
                    
                    # Update active tasks
                    if best_agent not in self.active_tasks:
                        self.active_tasks[best_agent] = {}
                    self.active_tasks[best_agent][task.task_id] = assignment
                    
                    # Update task history
                    if task.task_id not in self.task_history:
                        self.task_history[task.task_id] = []
                    self.task_history[task.task_id].append(assignment)
                    
                    logger.info(f"Task {task.task_id} assigned to agent {best_agent} with score {best_score}")
                else:
                    logger.warning(f"No suitable agent found for task {task.task_id}")
                    
                return best_agent
                
        except Exception as e:
            logger.error(f"Error assigning task: {e}")
            raise
        
    def complete_task(self, agent_id: str, task_id: str) -> bool:
        """Mark a task as completed and remove it from active tasks."""
        try:
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError("agent_id must be a non-empty string")
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("task_id must be a non-empty string")
                
            with self.lock:
                if agent_id in self.active_tasks and task_id in self.active_tasks[agent_id]:
                    # Update task history with completion time
                    assignment = self.active_tasks[agent_id][task_id]
                    assignment.completed_at = datetime.utcnow()
                    
                    # Remove from active tasks
                    del self.active_tasks[agent_id][task_id]
                    if not self.active_tasks[agent_id]:
                        del self.active_tasks[agent_id]
                        
                    logger.info(f"Task {task_id} completed by agent {agent_id}")
                    return True
                    
                logger.warning(f"Task {task_id} not found for agent {agent_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            raise
        
    def get_agent_tasks(self, agent_id: str) -> List[Task]:
        """Get all active tasks for an agent."""
        try:
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError("agent_id must be a non-empty string")
                
            with self.lock:
                return [
                    assignment.task 
                    for assignment in self.active_tasks.get(agent_id, {}).values()
                ]
        except Exception as e:
            logger.error(f"Error getting agent tasks: {e}")
            raise
        
    def get_task_agent(self, task_id: str) -> Optional[str]:
        """Find which agent is assigned to a specific task."""
        try:
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("task_id must be a non-empty string")
                
            with self.lock:
                for agent_id, tasks in self.active_tasks.items():
                    if task_id in tasks:
                        return agent_id
                return None
        except Exception as e:
            logger.error(f"Error getting task agent: {e}")
            raise
            
    def get_task_history(self, task_id: str) -> List[TaskAssignment]:
        """Get the assignment history for a specific task."""
        try:
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("task_id must be a non-empty string")
                
            with self.lock:
                return self.task_history.get(task_id, [])
        except Exception as e:
            logger.error(f"Error getting task history: {e}")
            raise
