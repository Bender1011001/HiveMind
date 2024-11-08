from typing import Dict, List, Optional, Tuple, Set
from .capability import Capability, CapabilityRegister
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from threading import Lock
import heapq

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Task:
    """Represents a task that needs to be assigned to an agent."""
    task_id: str
    required_capabilities: List[Capability]
    priority: int  # 1 (highest) to 5 (lowest)
    deadline: Optional[datetime] = None
    metadata: Optional[Dict] = None
    created_at: datetime = datetime.utcnow()
    timeout: Optional[timedelta] = timedelta(hours=1)  # Default timeout
    retry_count: int = 0
    max_retries: int = 3
    
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
        if self.timeout and not isinstance(self.timeout, timedelta):
            raise ValueError("timeout must be a timedelta object")
        if not isinstance(self.retry_count, int) or self.retry_count < 0:
            raise ValueError("retry_count must be a non-negative integer")
        if not isinstance(self.max_retries, int) or self.max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")

@dataclass
class TaskAssignment:
    """Represents a task assignment with additional metadata."""
    task: Task
    agent_id: str
    assigned_at: datetime = datetime.utcnow()
    capability_match_score: float = 0.0
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    
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
        self.task_queue: List[Tuple[int, datetime, Task]] = []  # Priority queue for unassigned tasks
        self.failed_tasks: Dict[str, TaskAssignment] = {}  # task_id -> TaskAssignment
        self.lock = Lock()  # For thread safety
        self.agent_health: Dict[str, datetime] = {}  # agent_id -> last_heartbeat
        
    def _calculate_agent_load(self, agent_id: str) -> float:
        """Calculate current load factor for an agent with task priority weighting."""
        if agent_id not in self.active_tasks:
            return 0.0
            
        # Weight tasks by priority (higher priority = higher load)
        weighted_load = sum(
            (6 - task.priority) / 5  # Convert priority 1-5 to weight 1.0-0.2
            for task in self.active_tasks[agent_id].values()
        )
        return weighted_load / self.max_tasks_per_agent
        
    def _calculate_capability_match(self, agent_id: str, task: Task) -> Tuple[float, int]:
        """Calculate capability match score and number of matching capabilities."""
        agent_capabilities = self.capability_register.get_agent_capabilities(agent_id)
        if not agent_capabilities:
            return 0.0, 0
            
        total_strength = 0.0
        capabilities_found = 0
        
        # Consider capability importance weights
        capability_weights = {
            cap: 1 + (0.2 * idx)  # Higher weight for first capabilities in list
            for idx, cap in enumerate(reversed(task.required_capabilities))
        }
        
        for required_cap in task.required_capabilities:
            for agent_cap in agent_capabilities:
                if agent_cap.capability == required_cap:
                    weight = capability_weights[required_cap]
                    total_strength += agent_cap.strength * weight
                    capabilities_found += 1
                    break
                    
        if capabilities_found != len(task.required_capabilities):
            return 0.0, capabilities_found
            
        return total_strength / sum(capability_weights.values()), capabilities_found
        
    def _check_task_timeouts(self):
        """Check for and handle timed out tasks."""
        now = datetime.utcnow()
        timed_out_tasks: List[Tuple[str, str]] = []  # List of (agent_id, task_id)
        
        with self.lock:
            for agent_id, tasks in self.active_tasks.items():
                for task_id, assignment in tasks.items():
                    if assignment.task.timeout:
                        timeout_time = assignment.assigned_at + assignment.task.timeout
                        if now > timeout_time:
                            timed_out_tasks.append((agent_id, task_id))
                            
            # Handle timed out tasks
            for agent_id, task_id in timed_out_tasks:
                self._handle_task_failure(
                    agent_id, task_id,
                    "Task timed out",
                    retry=True
                )
                
    def _handle_task_failure(self, agent_id: str, task_id: str, reason: str, retry: bool = True):
        """Handle a failed task, optionally retrying it."""
        with self.lock:
            if agent_id in self.active_tasks and task_id in self.active_tasks[agent_id]:
                assignment = self.active_tasks[agent_id][task_id]
                assignment.failed_at = datetime.utcnow()
                assignment.failure_reason = reason
                
                # Update task history
                if task_id not in self.task_history:
                    self.task_history[task_id] = []
                self.task_history[task_id].append(assignment)
                
                # Remove from active tasks
                del self.active_tasks[agent_id][task_id]
                if not self.active_tasks[agent_id]:
                    del self.active_tasks[agent_id]
                    
                # Handle retry if needed
                task = assignment.task
                if retry and task.retry_count < task.max_retries:
                    task.retry_count += 1
                    # Add back to queue with higher priority
                    task.priority = max(1, task.priority - 1)  # Increase priority
                    heapq.heappush(
                        self.task_queue,
                        (task.priority, datetime.utcnow(), task)
                    )
                else:
                    # Mark as permanently failed
                    self.failed_tasks[task_id] = assignment
                    
                logger.warning(f"Task {task_id} failed: {reason}")
                
    def update_agent_health(self, agent_id: str):
        """Update agent's last heartbeat time."""
        with self.lock:
            self.agent_health[agent_id] = datetime.utcnow()
            
    def _is_agent_healthy(self, agent_id: str) -> bool:
        """Check if an agent is healthy based on heartbeat."""
        if agent_id not in self.agent_health:
            return False
        return (datetime.utcnow() - self.agent_health[agent_id]) <= timedelta(minutes=5)
        
    def assign_task(self, task: Task) -> Optional[str]:
        """Assign a task to the most suitable agent considering priority and deadlines."""
        try:
            task.validate()
            self._check_task_timeouts()  # Check for timed out tasks first
            
            with self.lock:
                best_agent = None
                best_score = 0.0
                
                # Calculate deadline factor
                deadline_factor = 1.0
                if task.deadline:
                    time_until_deadline = (task.deadline - datetime.utcnow()).total_seconds()
                    if time_until_deadline <= 0:
                        logger.warning(f"Task {task.task_id} is already past deadline")
                        return None
                    deadline_factor = min(2.0, 86400 / max(1, time_until_deadline))
                    
                # Get healthy agents
                healthy_agents = {
                    agent_id for agent_id in self.capability_register.agent_capabilities
                    if self._is_agent_healthy(agent_id)
                }
                
                for agent_id in healthy_agents:
                    # Skip overloaded agents
                    if len(self.active_tasks.get(agent_id, {})) >= self.max_tasks_per_agent:
                        continue
                        
                    # Calculate scores
                    capability_score, capabilities_found = self._calculate_capability_match(agent_id, task)
                    if capabilities_found != len(task.required_capabilities):
                        continue
                        
                    load_factor = 1 - self._calculate_agent_load(agent_id)
                    priority_factor = (6 - task.priority) / 5  # Convert priority 1-5 to 1.0-0.2
                    
                    # Calculate final score with adjusted weights
                    final_score = (
                        capability_score * 0.35 +    # Capability match importance
                        load_factor * 0.25 +         # Load balancing importance
                        priority_factor * 0.25 +     # Task priority importance
                        deadline_factor * 0.15       # Deadline importance
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
                    # Queue task for later assignment
                    heapq.heappush(
                        self.task_queue,
                        (task.priority, datetime.utcnow(), task)
                    )
                    logger.warning(f"No suitable agent found for task {task.task_id}, queued for later")
                    
                return best_agent
                
        except Exception as e:
            logger.error(f"Error assigning task: {e}")
            raise
            
    def retry_failed_tasks(self):
        """Attempt to retry failed tasks."""
        with self.lock:
            failed_task_ids = list(self.failed_tasks.keys())
            for task_id in failed_task_ids:
                assignment = self.failed_tasks[task_id]
                if assignment.task.retry_count < assignment.task.max_retries:
                    # Remove from failed tasks
                    del self.failed_tasks[task_id]
                    # Attempt to reassign
                    self.assign_task(assignment.task)
                    
    def complete_task(self, agent_id: str, task_id: str, result: Optional[Dict] = None) -> bool:
        """Mark a task as completed with optional result data."""
        try:
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError("agent_id must be a non-empty string")
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("task_id must be a non-empty string")
                
            with self.lock:
                if agent_id in self.active_tasks and task_id in self.active_tasks[agent_id]:
                    # Update task history with completion time and result
                    assignment = self.active_tasks[agent_id][task_id]
                    assignment.completed_at = datetime.utcnow()
                    if result:
                        assignment.task.metadata = assignment.task.metadata or {}
                        assignment.task.metadata['result'] = result
                        
                    # Remove from active tasks
                    del self.active_tasks[agent_id][task_id]
                    if not self.active_tasks[agent_id]:
                        del self.active_tasks[agent_id]
                        
                    logger.info(f"Task {task_id} completed by agent {agent_id}")
                    
                    # Try to assign queued tasks
                    self._assign_queued_tasks()
                    return True
                    
                logger.warning(f"Task {task_id} not found for agent {agent_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            raise
            
    def _assign_queued_tasks(self):
        """Attempt to assign tasks from the queue."""
        with self.lock:
            while self.task_queue:
                # Get highest priority task
                _, _, task = heapq.heappop(self.task_queue)
                if self.assign_task(task):
                    logger.info(f"Successfully assigned queued task {task.task_id}")
                else:
                    # Put back in queue if assignment failed
                    heapq.heappush(
                        self.task_queue,
                        (task.priority, datetime.utcnow(), task)
                    )
                    break
                    
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
            
    def get_queued_tasks(self) -> List[Task]:
        """Get all tasks currently in the queue."""
        with self.lock:
            return [task for _, _, task in sorted(self.task_queue)]
            
    def get_failed_tasks(self) -> Dict[str, TaskAssignment]:
        """Get all permanently failed tasks."""
        with self.lock:
            return self.failed_tasks.copy()
