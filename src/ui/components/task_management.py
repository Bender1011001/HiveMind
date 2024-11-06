"""Task management component for the HiveMind UI."""

import streamlit as st
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from src.roles.capability import Capability
from src.roles.role_manager import Task

if TYPE_CHECKING:
    from src.ui.app import MultiAgentUI

class TaskManagement:
    """Component for managing tasks in the advanced mode interface."""
    
    def __init__(self, parent_ui: 'MultiAgentUI'):
        """Initialize task management component."""
        self.parent = parent_ui
        
    def render(self):
        """Render the task management interface."""
        st.header("Task Management")
        
        # Create new task
        with st.expander("➕ Create New Task", expanded=not bool(st.session_state.tasks)):
            self._render_task_creation()
                    
        # View active tasks
        if st.session_state.tasks:
            self._render_active_tasks()
        else:
            st.info("No active tasks. Create a new task to get started!")
            
    def _render_task_creation(self):
        """Render the task creation interface."""
        # Show help if no agents
        if not self.parent.capability_register.agent_capabilities:
            st.warning("⚠️ Please register at least one agent before creating tasks.")
            st.markdown("Go to the **Agent Management** tab to register agents.")
            return
            
        task_id = st.text_input(
            "Task ID",
            key="new_task_id",
            help="A unique identifier for this task"
        )
        
        st.write("Required Capabilities:")
        st.caption("Select the capabilities needed to complete this task")
        capabilities = st.multiselect(
            "Required Capabilities",
            options=[cap.value for cap in Capability],
            key="new_task_capabilities",
            help="The task will be assigned to an agent with these capabilities"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            priority = st.slider(
                "Priority",
                1, 5, 3,
                key="new_task_priority",
                help="1=Low priority, 5=High priority"
            )
        with col2:
            hours_to_deadline = st.number_input(
                "Hours to Deadline",
                min_value=1,
                value=24,
                key="new_task_deadline",
                help="Number of hours until task deadline"
            )
        
        if st.button("Create Task"):
            try:
                if not task_id:
                    st.error("Please enter a Task ID")
                elif not capabilities:
                    st.error("Please select at least one capability")
                else:
                    task = Task(
                        task_id=task_id,
                        required_capabilities=[Capability(cap) for cap in capabilities],
                        priority=priority,
                        deadline=datetime.utcnow() + timedelta(hours=hours_to_deadline)
                    )
                    
                    assigned_agent = self.parent.role_manager.assign_task(task)
                    if assigned_agent:
                        st.success(f"✅ Task assigned to agent: {assigned_agent}")
                        st.session_state.tasks.append(task)
                        st.rerun()
                    else:
                        st.error("❌ No suitable agent found for the task")
                    
            except Exception as e:
                st.error(f"Error creating task: {e}")
                
    def _render_active_tasks(self):
        """Render the active tasks list."""
        st.subheader("Active Tasks")
        for task in st.session_state.tasks:
            with st.expander(f"📋 Task: {task.task_id}"):
                # Task details
                col1, col2 = st.columns(2)
                with col1:
                    st.write("Priority:", "🔥" * task.priority)
                    hours_left = (task.deadline - datetime.utcnow()).total_seconds() / 3600
                    if hours_left > 0:
                        st.write(f"Time left: {hours_left:.1f} hours")
                    else:
                        st.error("OVERDUE")
                
                with col2:
                    assigned_agent = self.parent.role_manager.get_task_agent(task.task_id)
                    if assigned_agent:
                        st.write("Assigned to:", assigned_agent)
                        
                # Required capabilities
                st.write("Required Capabilities:")
                for cap in task.required_capabilities:
                    st.write(f"• {cap.value}")
                
                # Complete task button
                if assigned_agent and st.button(f"✅ Complete Task {task.task_id}"):
                    if self.parent.role_manager.complete_task(assigned_agent, task.task_id):
                        st.session_state.tasks.remove(task)
                        st.success("Task marked as completed")
                        st.rerun()
