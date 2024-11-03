"""Task Planner for decomposing complex tasks and managing dependencies."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging
from threading import Lock
from datetime import datetime

from ..roles.role_manager import Task, RoleManager
from ..memory.context_manager import SharedContext

logger = logging.getLogger(__name__)

@dataclass
class SubTask(Task):
    parent_task_id: str
    status: str = 'pending'  # Status can be 'pending', 'in_progress', 'completed'
    assigned_agent: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

class TaskPlanner:
    """Handles task decomposition and assignment."""

    def __init__(self, shared_context: SharedContext, role_manager: RoleManager):
        self.shared_context = shared_context
        self.role_manager = role_manager
        self.lock = Lock()
        self.subtasks: Dict[str, SubTask] = {}  # Maps subtask_id to SubTask

    def decompose_task(self, task: Task) -> List[SubTask]:
        """Decompose a complex task into sub-tasks."""
        subtasks = []
        # Example decomposition logic (this should be customized per task)
        for i in range(1, 4):
            subtask_id = f"{task.task_id}_sub{i}"
            subtask = SubTask(
                task_id=subtask_id,
                parent_task_id=task.task_id,
                required_capabilities=task.required_capabilities,
                priority=task.priority,
                deadline=task.deadline,
                metadata={"description": f"Sub-task {i} of {task.task_id}"},
                dependencies=[],
            )
            subtasks.append(subtask)
            self.subtasks[subtask_id] = subtask
            
            # Update shared context with new subtask
            self.shared_context.update_task_progress(
                subtask.task_id,
                None,
                {"status": subtask.status, "description": subtask.metadata["description"]}
            )
        logger.info(f"Task {task.task_id} decomposed into {len(subtasks)} sub-tasks.")
        return subtasks

    def assign_subtasks(self, subtasks: List[SubTask]):
        """Assign sub-tasks to agents."""
        for subtask in subtasks:
            agent_id = self.role_manager.assign_task(subtask)
            if agent_id:
                subtask.assigned_agent = agent_id
                subtask.status = 'in_progress'
                # Update shared context
                self.shared_context.update_task_progress(
                    subtask.task_id,
                    subtask.assigned_agent,
                    {"status": subtask.status}
                )
                logger.info(f"Sub-task {subtask.task_id} assigned to agent {agent_id}.")
            else:
                logger.warning(f"No agent available to assign sub-task {subtask.task_id}")
                
    def update_subtask_status(self, subtask_id: str, status: str):
        """Update the status of a sub-task."""
        with self.lock:
            subtask = self.subtasks.get(subtask_id)
            if subtask:
                subtask.status = status
                # Update shared context
                self.shared_context.update_task_progress(
                    subtask.task_id,
                    subtask.assigned_agent,
                    {"status": status}
                )
                logger.info(f"Sub-task {subtask_id} status updated to {status}.")
            else:
                logger.warning(f"Sub-task {subtask_id} not found.")
    
    def get_subtasks_for_task(self, parent_task_id: str) -> List[SubTask]:
        """Get all sub-tasks for a given parent task."""
        return [
            subtask for subtask in self.subtasks.values() 
            if subtask.parent_task_id == parent_task_id
        ]
