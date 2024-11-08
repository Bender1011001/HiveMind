"""System status component for the HiveMind UI."""

import streamlit as st
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.app import MultiAgentUI

class SystemStatus:
    """Component for displaying system status in the UI."""
    
    def __init__(self, parent_ui: 'MultiAgentUI'):
        """Initialize system status component."""
        self.parent = parent_ui
        
    def render(self):
        """Render the system status interface."""
        try:
            # MongoDB Status
            mongo_status = "🟢 Connected" if self.parent.mongodb_connected else "🔴 Disconnected"
            st.write("MongoDB:", mongo_status)
            
            # RabbitMQ Status
            rabbitmq_status = "🟢 Connected" if self.parent.rabbitmq_connected else "🔴 Disconnected"
            st.write("RabbitMQ:", rabbitmq_status)
            
            # API Stats
            st.write("---")
            st.write("API Stats:")
            recent_calls = len([call for call in self.parent.api_monitor.recent_calls 
                              if (datetime.fromisoformat(call['timestamp']) > 
                                  datetime.utcnow() - timedelta(minutes=5))])
            st.write("• Recent API Calls:", recent_calls)
            
            # Agent Stats
            st.write("---")
            st.write("System Stats:")
            st.write("• Registered Agents:", len(self.parent.capability_register.agent_capabilities))
            st.write("• Active Tasks:", len(st.session_state.tasks))
            st.write("• Messages:", len(st.session_state.messages))
            
            # System Load
            if st.session_state.tasks:
                avg_priority = sum(task.priority for task in st.session_state.tasks) / len(st.session_state.tasks)
                st.progress(avg_priority/5, "System Load")
            
        except Exception as e:
            st.error(f"Error displaying system status: {e}")
            
    def check_required_services(self):
        """Check if required services are available and show appropriate messages."""
        if not self.parent.mongodb_connected:
            st.error("⚠️ MongoDB is not available. Please install and start MongoDB before proceeding.")
            st.markdown("""
            To install MongoDB:
            1. Download from https://www.mongodb.com/try/download/community
            2. Install and start the MongoDB service
            3. Restart this application
            """)
            st.stop()
            
        if not self.parent.rabbitmq_connected:
            st.error("⚠️ RabbitMQ is not available. Please install and start RabbitMQ before proceeding.")
            st.markdown("""
            To install RabbitMQ:
            1. Download from https://www.rabbitmq.com/download.html
            2. Install and start the RabbitMQ service
            3. Restart this application
            """)
            st.stop()
