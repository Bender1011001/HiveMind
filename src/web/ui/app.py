"""Main entry point for the LangChain Multi-Agent System."""

import streamlit as st
import os
import sys
from pathlib import Path
from pymongo.errors import ConnectionFailure

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.memory.mongo_store import MongoMemoryStore
from src.communication.broker import MessageBroker
from src.roles.capability import CapabilityRegister
from src.roles.role_manager import RoleManager
from src.roles.master_agent import MasterAgent
from src.execution.code_executor import CodeExecutor
from src.settings.settings import Settings, settings
from src.communication.openrouter_client import OpenRouterClient
from src.utils.debug import get_logger
from src.utils.event_bus import EventBus
from src.ui.api_monitor import APIMonitor

# Import UI components
from src.ui.components.simple_mode import SimpleMode
from src.ui.components.task_management import TaskManagement
from src.ui.components.agent_management import AgentManagement
from src.ui.components.communication import Communication
from src.ui.components.code_execution import CodeExecution
from src.ui.components.system_status import SystemStatus
from src.ui.components.agent_activity import AgentActivity

# Initialize logger for this module
logger = get_logger('ui')

class MultiAgentUI:
    """Streamlit-based UI for the multi-agent system."""
    
    def __init__(self):
        """Initialize system components."""
        try:
            self.settings = settings
            
            # Initialize EventBus
            self.event_bus = EventBus()
            
            # Initialize MongoDB connection
            try:
                self.memory_store = MongoMemoryStore()
                self.mongodb_connected = True
            except (ConnectionFailure, ConnectionError) as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                self.memory_store = None
                self.mongodb_connected = False
            
            # Initialize RabbitMQ connection
            try:
                self.message_broker = MessageBroker()
                self.rabbitmq_connected = True
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                self.message_broker = None
                self.rabbitmq_connected = False
            
            # Initialize API monitoring
            self.api_monitor = APIMonitor(self.event_bus)
            
            # Initialize core components
            self.capability_register = CapabilityRegister()
            self.role_manager = RoleManager(self.capability_register)
            self.master_agent = MasterAgent(self.role_manager, self.capability_register)
            self.code_executor = CodeExecutor()
            
            # Initialize OpenRouterClient with event bus
            self.openrouter_client = OpenRouterClient(event_bus=self.event_bus)
            
            # Initialize UI components
            self.simple_mode = SimpleMode(self)
            self.task_management = TaskManagement(self)
            self.agent_management = AgentManagement(self)
            self.communication = Communication(self)
            self.code_execution = CodeExecution(self)
            self.system_status = SystemStatus(self)
            self.agent_activity = AgentActivity(self.event_bus)
            
            # Initialize session state
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            if 'tasks' not in st.session_state:
                st.session_state.tasks = []
            if 'show_welcome' not in st.session_state:
                st.session_state.show_welcome = True
            if 'interface_mode' not in st.session_state:
                st.session_state.interface_mode = 'simple'
            if 'active_tab' not in st.session_state:
                st.session_state.active_tab = 'task_management'
                
        except Exception as e:
            st.error(f"Error initializing system: {e}")
            raise
            
    def render(self):
        """Render the main UI."""
        # Mode toggle in sidebar
        with st.sidebar:
            st.title("Interface Mode")
            mode = st.radio(
                "Select Mode",
                options=['Simple', 'Advanced'],
                index=0 if st.session_state.interface_mode == 'simple' else 1,
                help="""
                Simple Mode: Just enter your request and let the system handle the details
                Advanced Mode: Full control over agents, tasks, and system settings
                """
            )
            st.session_state.interface_mode = mode.lower()
            
            # Model selection input in sidebar
            model_name = st.text_input(
                "Model Name",
                value=os.getenv("MODEL_NAME", "anthropic/claude-3-opus"),
                help="Enter the model name (e.g., anthropic/claude-3-opus, openai/gpt-4-turbo)",
                key="model_name_advanced"
            )
            settings.model_name = model_name
            
            st.markdown("---")
            
            # System status (shown in both modes)
            st.header("System Status")
            self.system_status.render()
        
        # Check if required services are available
        self.system_status.check_required_services()
        
        # Render appropriate interface based on mode
        if st.session_state.interface_mode == 'simple':
            self.simple_mode.render()
        else:
            self._render_advanced_mode()
    
    def _render_advanced_mode(self):
        """Render the advanced mode interface."""
        st.title("HiveMind Advanced Mode")
        
        # Welcome message for first-time users
        if st.session_state.show_welcome:
            with st.expander("👋 Welcome to Advanced Mode! Click here to get started", expanded=True):
                st.markdown("""
                ### Quick Start Guide
                1. First, go to **Agent Management** to register agents with specific capabilities
                2. Then, create tasks in **Task Management** - they'll be automatically assigned to agents
                3. Use **Communication** to see messages between agents
                4. **Code Execution** lets you run Python or JavaScript code
                5. **API Monitor** shows all API interactions and their status
                6. **Agent Activity** provides detailed monitoring of each agent's processes
                
                Click the ❌ in the top right to close this guide.
                """)
                if st.button("Don't show this again"):
                    st.session_state.show_welcome = False
                    st.rerun()

        # Create two columns for the tab sections
        col1, col2 = st.columns(2)

        # Core Functions in left column
        with col1:
            st.markdown("### Core Functions")
            tab_core1, tab_core2, tab_core3 = st.tabs([
                "Task Management",
                "Agent Management",
                "Communication"
            ])
            
            with tab_core1:
                self.task_management.render()
            with tab_core2:
                self.agent_management.render()
            with tab_core3:
                self.communication.render()

        # Monitoring & Execution in right column
        with col2:
            st.markdown("### Monitoring & Execution")
            tab_mon1, tab_mon2, tab_mon3 = st.tabs([
                "Code Execution",
                "API Monitor",
                "Agent Activity"
            ])
            
            with tab_mon1:
                self.code_execution.render()
            with tab_mon2:
                self.api_monitor.render()
            with tab_mon3:
                self.agent_activity.render()
                
    def cleanup(self):
        """Clean up resources."""
        try:
            if self.memory_store:
                self.memory_store.close()
            if self.message_broker:
                self.message_broker.close()
            self.code_executor.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up resources: {e}")

def main():
    """Main entry point for the UI."""
    try:
        ui = MultiAgentUI()
        ui.render()
    except Exception as e:
        st.error(f"Application error: {e}")
        raise
    finally:
        if 'ui' in locals():
            ui.cleanup()

if __name__ == "__main__":
    main()
