"""Task Planner for decomposing complex tasks and managing dependencies."""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from threading import Lock
from datetime import datetime
import re

from ..agents.role_manager import Task, RoleManager
from ..storage.context_manager import SharedContext
from ..agents.capability import Capability
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

@dataclass
class SubTask(Task):
    parent_task_id: str
    status: str = 'pending'  # Status can be 'pending', 'in_progress', 'completed'
    assigned_agent: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    step_number: int = 0
    estimated_complexity: float = 1.0  # 1.0 = baseline complexity

class TaskPlanner:
    """Handles intelligent task decomposition and assignment."""

    def __init__(self, shared_context: SharedContext, role_manager: RoleManager):
        logger.info("Initializing TaskPlanner")
        self.shared_context = shared_context
        self.role_manager = role_manager
        self.lock = Lock()
        self.subtasks: Dict[str, SubTask] = {}  # Maps subtask_id to SubTask
        logger.info("TaskPlanner initialized successfully")

    def _analyze_task_type(self, task: Task) -> str:
        """Determine the type of task based on required capabilities and metadata."""
        capabilities = set(cap.value for cap in task.required_capabilities)
        logger.debug(f"Analyzing task type for task {task.task_id} with capabilities: {capabilities}")

        # Check for code-related task
        code_capabilities = {'code_generation', 'code_review', 'code_optimization'}
        if any(cap in capabilities for cap in code_capabilities):
            logger.debug(f"Task {task.task_id} identified as code task")
            return 'code'

        # Check for writing/documentation task
        writing_capabilities = {'technical_writing', 'creative_writing', 'documentation'}
        if any(cap in capabilities for cap in writing_capabilities):
            logger.debug(f"Task {task.task_id} identified as writing task")
            return 'writing'

        # Check for analysis task
        analysis_capabilities = {'data_analysis', 'critical_analysis', 'research'}
        if any(cap in capabilities for cap in analysis_capabilities):
            logger.debug(f"Task {task.task_id} identified as analysis task")
            return 'analysis'

        logger.debug(f"Task {task.task_id} identified as general task")
        return 'general'

    def _estimate_complexity(self, subtask_desc: str, capabilities: List[Capability]) -> float:
        """Estimate relative complexity of a subtask."""
        logger.debug(f"Estimating complexity for subtask with {len(capabilities)} capabilities")

        # Base complexity
        complexity = 1.0

        # Adjust based on number of capabilities required
        complexity *= (1 + (len(capabilities) * 0.2))
        logger.debug(f"Complexity after capability adjustment: {complexity}")

        # Adjust based on description keywords
        complexity_keywords = {
            'optimize': 1.5,
            'improve': 1.3,
            'refactor': 1.4,
            'design': 1.3,
            'implement': 1.2,
            'test': 1.1,
            'debug': 1.3,
            'analyze': 1.2,
            'research': 1.3
        }

        for keyword, multiplier in complexity_keywords.items():
            if keyword in subtask_desc.lower():
                complexity *= multiplier
                logger.debug(f"Applied complexity multiplier {multiplier} for keyword '{keyword}'")

        final_complexity = min(complexity, 5.0)  # Cap at 5x baseline
        logger.debug(f"Final estimated complexity: {final_complexity}")
        return final_complexity

    def _create_code_subtasks(self, task: Task) -> List[SubTask]:
        """Create subtasks for code-related tasks."""
        logger.info(f"Creating code subtasks for task {task.task_id}")
        subtasks = []
        base_id = task.task_id

        # Analysis/Planning phase
        analysis_task = SubTask(
            task_id=f"{base_id}_analysis",
            parent_task_id=task.task_id,
            required_capabilities=[Capability.critical_analysis],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Analyze requirements and plan implementation approach"},
            step_number=1
        )
        subtasks.append(analysis_task)
        logger.debug(f"Created analysis subtask: {analysis_task.task_id}")

        # Implementation phase
        implement_task = SubTask(
            task_id=f"{base_id}_implement",
            parent_task_id=task.task_id,
            required_capabilities=[cap for cap in task.required_capabilities
                                 if 'code' in cap.value],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Implement the planned solution"},
            dependencies=[analysis_task.task_id],
            step_number=2
        )
        subtasks.append(implement_task)
        logger.debug(f"Created implementation subtask: {implement_task.task_id}")

        # Testing/Review phase
        test_task = SubTask(
            task_id=f"{base_id}_test",
            parent_task_id=task.task_id,
            required_capabilities=[Capability.code_review],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Test implementation and review code quality"},
            dependencies=[implement_task.task_id],
            step_number=3
        )
        subtasks.append(test_task)
        logger.debug(f"Created testing subtask: {test_task.task_id}")

        # Optional optimization phase if specifically requested
        if any('optimize' in cap.value for cap in task.required_capabilities):
            optimize_task = SubTask(
                task_id=f"{base_id}_optimize",
                parent_task_id=task.task_id,
                required_capabilities=[Capability.code_optimization],
                priority=task.priority,
                deadline=task.deadline,
                metadata={"description": "Optimize code for better performance"},
                dependencies=[test_task.task_id],
                step_number=4
            )
            subtasks.append(optimize_task)
            logger.debug(f"Created optimization subtask: {optimize_task.task_id}")

        logger.info(f"Created {len(subtasks)} code subtasks for task {task.task_id}")
        return subtasks

    def _create_writing_subtasks(self, task: Task) -> List[SubTask]:
        """Create subtasks for writing/documentation tasks."""
        logger.info(f"Creating writing subtasks for task {task.task_id}")
        subtasks = []
        base_id = task.task_id

        # Research phase
        research_task = SubTask(
            task_id=f"{base_id}_research",
            parent_task_id=task.task_id,
            required_capabilities=[Capability.research],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Research and gather information"},
            step_number=1
        )
        subtasks.append(research_task)
        logger.debug(f"Created research subtask: {research_task.task_id}")

        # Outline/Planning phase
        outline_task = SubTask(
            task_id=f"{base_id}_outline",
            parent_task_id=task.task_id,
            required_capabilities=[cap for cap in task.required_capabilities
                                 if 'writing' in cap.value],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Create detailed outline"},
            dependencies=[research_task.task_id],
            step_number=2
        )
        subtasks.append(outline_task)
        logger.debug(f"Created outline subtask: {outline_task.task_id}")

        # Writing phase
        write_task = SubTask(
            task_id=f"{base_id}_write",
            parent_task_id=task.task_id,
            required_capabilities=task.required_capabilities,
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Write initial content"},
            dependencies=[outline_task.task_id],
            step_number=3
        )
        subtasks.append(write_task)
        logger.debug(f"Created writing subtask: {write_task.task_id}")

        # Review/Edit phase
        review_task = SubTask(
            task_id=f"{base_id}_review",
            parent_task_id=task.task_id,
            required_capabilities=[Capability.critical_analysis],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Review and refine content"},
            dependencies=[write_task.task_id],
            step_number=4
        )
        subtasks.append(review_task)
        logger.debug(f"Created review subtask: {review_task.task_id}")

        logger.info(f"Created {len(subtasks)} writing subtasks for task {task.task_id}")
        return subtasks

    def _create_analysis_subtasks(self, task: Task) -> List[SubTask]:
        """Create subtasks for analysis/research tasks."""
        logger.info(f"Creating analysis subtasks for task {task.task_id}")
        subtasks = []
        base_id = task.task_id

        # Data gathering phase
        gather_task = SubTask(
            task_id=f"{base_id}_gather",
            parent_task_id=task.task_id,
            required_capabilities=[Capability.research],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Gather relevant data and information"},
            step_number=1
        )
        subtasks.append(gather_task)
        logger.debug(f"Created data gathering subtask: {gather_task.task_id}")

        # Analysis phase
        analyze_task = SubTask(
            task_id=f"{base_id}_analyze",
            parent_task_id=task.task_id,
            required_capabilities=[cap for cap in task.required_capabilities
                                 if 'analysis' in cap.value],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Analyze gathered information"},
            dependencies=[gather_task.task_id],
            step_number=2
        )
        subtasks.append(analyze_task)
        logger.debug(f"Created analysis subtask: {analyze_task.task_id}")

        # Synthesis phase
        synthesis_task = SubTask(
            task_id=f"{base_id}_synthesize",
            parent_task_id=task.task_id,
            required_capabilities=[Capability.critical_analysis],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Synthesize findings and draw conclusions"},
            dependencies=[analyze_task.task_id],
            step_number=3
        )
        subtasks.append(synthesis_task)
        logger.debug(f"Created synthesis subtask: {synthesis_task.task_id}")

        # Reporting phase
        report_task = SubTask(
            task_id=f"{base_id}_report",
            parent_task_id=task.task_id,
            required_capabilities=[Capability.technical_writing],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Create detailed report of findings"},
            dependencies=[synthesis_task.task_id],
            step_number=4
        )
        subtasks.append(report_task)
        logger.debug(f"Created reporting subtask: {report_task.task_id}")

        logger.info(f"Created {len(subtasks)} analysis subtasks for task {task.task_id}")
        return subtasks

    def _create_general_subtasks(self, task: Task) -> List[SubTask]:
        """Create subtasks for general tasks without specific type."""
        logger.info(f"Creating general subtasks for task {task.task_id}")
        subtasks = []
        base_id = task.task_id

        # Planning phase
        plan_task = SubTask(
            task_id=f"{base_id}_plan",
            parent_task_id=task.task_id,
            required_capabilities=[Capability.critical_analysis],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Plan approach and identify requirements"},
            step_number=1
        )
        subtasks.append(plan_task)
        logger.debug(f"Created planning subtask: {plan_task.task_id}")

        # Execution phase
        execute_task = SubTask(
            task_id=f"{base_id}_execute",
            parent_task_id=task.task_id,
            required_capabilities=task.required_capabilities,
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Execute planned approach"},
            dependencies=[plan_task.task_id],
            step_number=2
        )
        subtasks.append(execute_task)
        logger.debug(f"Created execution subtask: {execute_task.task_id}")

        # Review phase
        review_task = SubTask(
            task_id=f"{base_id}_review",
            parent_task_id=task.task_id,
            required_capabilities=[Capability.critical_analysis],
            priority=task.priority,
            deadline=task.deadline,
            metadata={"description": "Review results and ensure quality"},
            dependencies=[execute_task.task_id],
            step_number=3
        )
        subtasks.append(review_task)
        logger.debug(f"Created review subtask: {review_task.task_id}")

        logger.info(f"Created {len(subtasks)} general subtasks for task {task.task_id}")
        return subtasks

    def decompose_task(self, task: Task) -> List[SubTask]:
        """Decompose a complex task into sub-tasks based on type and requirements."""
        logger.info(f"Starting task decomposition for task {task.task_id}")
        task_type = self._analyze_task_type(task)
        logger.info(f"Task {task.task_id} identified as {task_type} type")

        # Select decomposition strategy based on task type
        if task_type == 'code':
            subtasks = self._create_code_subtasks(task)
        elif task_type == 'writing':
            subtasks = self._create_writing_subtasks(task)
        elif task_type == 'analysis':
            subtasks = self._create_analysis_subtasks(task)
        else:
            subtasks = self._create_general_subtasks(task)

        # Store subtasks and update shared context
        logger.info(f"Storing {len(subtasks)} subtasks and updating shared context")
        for subtask in subtasks:
            subtask.estimated_complexity = self._estimate_complexity(
                subtask.metadata.get('description', ''),
                subtask.required_capabilities
            )
            self.subtasks[subtask.task_id] = subtask
            logger.debug(f"Stored subtask {subtask.task_id} with complexity {subtask.estimated_complexity}")

            # Update shared context with new subtask
            self.shared_context.update_task_progress(
                subtask.task_id,
                None,
                {
                    "status": subtask.status,
                    "description": subtask.metadata.get("description", ""),
                    "step_number": subtask.step_number,
                    "complexity": subtask.estimated_complexity,
                    "dependencies": subtask.dependencies
                }
            )
            logger.debug(f"Updated shared context for subtask {subtask.task_id}")

        logger.info(f"Task {task.task_id} successfully decomposed into {len(subtasks)} sub-tasks")
        return subtasks

    def assign_subtasks(self, subtasks: List[SubTask]):
        """Assign sub-tasks to agents considering dependencies."""
        logger.info(f"Starting assignment of {len(subtasks)} subtasks")

        # Sort subtasks by step number to respect dependencies
        subtasks.sort(key=lambda x: x.step_number)
        logger.debug("Sorted subtasks by step number")

        for subtask in subtasks:
            # Check if dependencies are completed
            if subtask.dependencies:
                pending_deps = [dep_id for dep_id in subtask.dependencies
                              if self.subtasks[dep_id].status != 'completed']
                if pending_deps:
                    logger.info(f"Skipping assignment of {subtask.task_id}, "
                              f"waiting for dependencies: {pending_deps}")
                    continue

            logger.debug(f"Attempting to assign subtask {subtask.task_id}")
            agent_id = self.role_manager.assign_task(subtask)
            if agent_id:
                subtask.assigned_agent = agent_id
                subtask.status = 'in_progress'
                # Update shared context
                self.shared_context.update_task_progress(
                    subtask.task_id,
                    subtask.assigned_agent,
                    {
                        "status": subtask.status,
                        "assigned_agent": agent_id,
                        "assigned_at": datetime.utcnow().isoformat()
                    }
                )
                logger.info(f"Successfully assigned subtask {subtask.task_id} to agent {agent_id}")
            else:
                logger.warning(f"No suitable agent found for subtask {subtask.task_id}")

    def update_subtask_status(self, subtask_id: str, status: str):
        """Update the status of a sub-task and manage dependencies."""
        logger.info(f"Updating status of subtask {subtask_id} to {status}")

        with self.lock:
            subtask = self.subtasks.get(subtask_id)
            if subtask:
                old_status = subtask.status
                subtask.status = status

                # Update shared context
                self.shared_context.update_task_progress(
                    subtask.task_id,
                    subtask.assigned_agent,
                    {
                        "status": status,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )

                logger.info(f"Updated subtask {subtask_id} status: {old_status} -> {status}")

                # If completed, check if we can assign dependent tasks
                if status == 'completed':
                    dependent_tasks = [
                        st for st in self.subtasks.values()
                        if subtask_id in st.dependencies
                    ]
                    if dependent_tasks:
                        logger.info(f"Found {len(dependent_tasks)} dependent tasks to potentially assign")
                        self.assign_subtasks(dependent_tasks)
                    else:
                        logger.debug(f"No dependent tasks found for completed subtask {subtask_id}")
            else:
                logger.warning(f"Attempted to update status for non-existent subtask {subtask_id}")

    def get_subtasks_for_task(self, parent_task_id: str) -> List[SubTask]:
        """Get all sub-tasks for a given parent task."""
        logger.debug(f"Retrieving subtasks for parent task {parent_task_id}")

        subtasks = [
            subtask for subtask in self.subtasks.values()
            if subtask.parent_task_id == parent_task_id
        ]
        # Sort by step number for logical ordering
        subtasks.sort(key=lambda x: x.step_number)

        logger.info(f"Retrieved {len(subtasks)} subtasks for parent task {parent_task_id}")
        return subtasks
