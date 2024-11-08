"""Simple mode interface component for the HiveMind UI."""

import streamlit as st
from datetime import datetime
from typing import TYPE_CHECKING
from src.utils.debug import get_logger, debug, info, error, log_request

if TYPE_CHECKING:
    from src.ui.app import MultiAgentUI

logger = get_logger('ui.simple_mode')

class SimpleMode:
    """Simple mode interface for the multi-agent system."""
    
    def __init__(self, parent_ui: 'MultiAgentUI'):
        """Initialize simple mode with reference to parent UI."""
        self.parent = parent_ui
        self.logger = get_logger('ui.simple_mode')
        
        if not self.parent.memory_store or not self.parent.message_broker:
            self.logger.error("Required services unavailable")
            st.error("⚠️ Required services (MongoDB and/or RabbitMQ) are not available. Please install and start these services before proceeding.")
            st.stop()
            
        self.master_agent = self.parent.master_agent
        
        # Initialize tasks in session state if not present
        if 'tasks' not in st.session_state:
            st.session_state.tasks = []
        
    @log_request
    def render(self):
        """Render the simple mode interface."""
        st.title("HiveMind AI Assistant")
        
        # Simple description
        st.markdown("""
        Welcome to HiveMind! Just tell me what you need help with, and I'll:
        - Analyze your request
        - Select the most appropriate AI agents
        - Get your task done efficiently
        """)

        # Model selection input
        model_name = st.text_input(
            "Model Name",
            value=self.parent.settings.model_name,
            help="Enter the model name (e.g., anthropic/claude-3-opus, openai/gpt-4-turbo)",
            key="model_name_simple"
        )
        
        # Large input field for user request
        user_request = st.text_area(
            "What would you like help with?",
            placeholder="Enter your request, question, or task...",
            height=150
        )
        
        # Priority selector
        priority = st.select_slider(
            "Task Priority",
            options=[1, 2, 3, 4, 5],
            value=3,
            format_func=lambda x: {1: "Low", 2: "Medium-Low", 3: "Medium", 4: "Medium-High", 5: "High"}[x],
            help="Select the priority level for your request"
        )
        
        # Submit button
        if st.button("Submit Request", type="primary"):
            if not user_request:
                self.logger.warning("Empty request submitted")
                st.error("Please enter a request")
                return
                
            try:
                # Update model name in settings
                self.parent.settings.model_name = model_name
                
                with st.spinner("Analyzing your request..."):
                    debug("Processing request", request=user_request, priority=priority)
                    # Process request through master agent
                    assigned_agent = self.master_agent.process_request(user_request, priority)
                    
                    if assigned_agent:
                        info(f"Request assigned to agent", agent=assigned_agent)
                        st.success("✅ Request submitted successfully")
                        st.info(f"Your request is being handled by {assigned_agent}")
                        
                        # Show detected capabilities
                        capabilities = self.master_agent.analyze_request(user_request)
                        debug("Detected capabilities", capabilities=[cap.value for cap in capabilities])
                        st.write("Detected needs:")
                        for cap in capabilities:
                            st.write(f"• {cap.value.replace('_', ' ').title()}")
                    else:
                        error("No suitable agent available")
                        st.error("❌ No suitable agent available. Please try again later.")
                    
            except Exception as e:
                error(f"Error processing request", error=str(e))
                st.error(f"Error processing request: {e}")

        self._render_active_tasks()

    def _render_active_tasks(self):
        """Render the active tasks section."""
        if hasattr(st.session_state, 'tasks') and st.session_state.tasks:
            active_tasks = [task for task in st.session_state.tasks
                          if (task.deadline - datetime.utcnow()).total_seconds() > 0]
            
            if active_tasks:
                st.markdown("---")
                st.subheader("Active Requests")
                
                for task in active_tasks:
                    with st.expander(f"📋 Request {task.task_id}"):
                        # Get task status from master agent
                        status = self.master_agent.get_task_status(task.task_id)
                        
                        # Find associated message
                        task_message = next(
                            (msg for msg in st.session_state.messages
                             if msg.task_id == task.task_id),
                            None
                        )
                        
                        if task_message:
                            st.write("Request:", task_message.content.get('text', 'N/A'))
                        
                        st.write("Status:", status['status'].title())
                        if status.get('assigned_agent'):
                            st.write("Assigned to:", status['assigned_agent'])
                        
                        hours_left = (task.deadline - datetime.utcnow()).total_seconds() / 3600
                        if hours_left > 0:
                            st.write(f"Time remaining: {hours_left:.1f} hours")
                        else:
                            st.error("OVERDUE")
