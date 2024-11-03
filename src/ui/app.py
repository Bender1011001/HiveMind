import streamlit as st
import logging
from datetime import datetime, timedelta
from typing import Dict, List

from ..memory.mongo_store import MongoMemoryStore
from ..communication.broker import MessageBroker
from ..communication.message import Message, MessageType
from ..roles.capability import Capability, AgentCapability, CapabilityRegister
from ..roles.role_manager import Task, RoleManager
from ..execution.code_executor import CodeExecutor
from ..settings import Settings, settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultiAgentUI:
    """Streamlit-based UI for the multi-agent system."""
    
    def __init__(self):
        """Initialize system components."""
        try:
            self.settings = settings
            self.memory_store = MongoMemoryStore()
            self.message_broker = MessageBroker()
            self.capability_register = CapabilityRegister()
            self.role_manager = RoleManager(self.capability_register)
            self.code_executor = CodeExecutor()
            
            # Initialize session state
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            if 'tasks' not in st.session_state:
                st.session_state.tasks = []
                
        except Exception as e:
            st.error(f"Error initializing system: {e}")
            raise
            
    def render(self):
        """Render the main UI."""
        st.title("LangChain Multi-Agent System")
        
        # Sidebar for system status
        with st.sidebar:
            st.header("System Status")
            self._render_system_status()
            
        # Main tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Task Management",
            "Agent Management",
            "Communication",
            "Code Execution",
            "Settings"
        ])
        
        with tab1:
            self._render_task_management()
            
        with tab2:
            self._render_agent_management()
            
        with tab3:
            self._render_communication()
            
        with tab4:
            self._render_code_execution()
            
        with tab5:
            self._render_settings()
            
    def _render_system_status(self):
        """Render system status in sidebar."""
        try:
            # Check MongoDB connection
            try:
                self.memory_store.client.admin.command('ping')
                st.success("MongoDB: Connected")
            except Exception as e:
                st.error(f"MongoDB: Disconnected ({str(e)})")
                
            # Check RabbitMQ connection
            if not self.message_broker.connection.is_closed:
                st.success("RabbitMQ: Connected")
            else:
                st.error("RabbitMQ: Disconnected")
                
            # Show registered agents
            st.subheader("Registered Agents")
            for agent_id in self.capability_register.agent_capabilities:
                st.write(f"• {agent_id}")
                
        except Exception as e:
            st.error(f"Error checking system status: {e}")
            
    def _render_settings(self):
        """Render settings interface."""
        st.header("Settings")
        
        # Create three columns for better space utilization
        col1, col2, col3 = st.columns([1, 1, 1])
        
        # Model settings in first column
        with col1:
            st.subheader("Model")
            model_name = st.text_input(
                "Model Name",
                value=self.settings.model_name,
                help="Name of the language model"
            )
            
            api_key = st.text_input(
                "API Key",
                value=self.settings.api_key,
                type="password",
                help="API key for the model"
            )
        
        # Generation settings in second column
        with col2:
            st.subheader("Generation")
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=self.settings.temperature,
                step=0.1,
                help="Controls randomness"
            )
            
            max_tokens = st.number_input(
                "Max Tokens",
                min_value=1,
                max_value=4096,
                value=self.settings.max_tokens,
                help="Max response length"
            )
        
        # Connection settings in third column
        with col3:
            st.subheader("Connection")
            mongodb_uri = st.text_input(
                "MongoDB URI",
                value=self.settings.mongodb_uri,
                help="MongoDB connection URI"
            )
            
            rabbitmq_host = st.text_input(
                "RabbitMQ Host",
                value=self.settings.rabbitmq_host,
                help="RabbitMQ hostname"
            )
            
            rabbitmq_port = st.number_input(
                "RabbitMQ Port",
                min_value=1,
                max_value=65535,
                value=self.settings.rabbitmq_port,
                help="RabbitMQ port"
            )
        
        # Save button centered below all settings
        st.markdown("---")
        col_left, col_center, col_right = st.columns([1, 2, 1])
        with col_center:
            if st.button("💾 Save Settings", type="primary", use_container_width=True):
                try:
                    # Update settings
                    self.settings.model_name = model_name
                    self.settings.api_key = api_key
                    self.settings.temperature = temperature
                    self.settings.max_tokens = max_tokens
                    self.settings.mongodb_uri = mongodb_uri
                    self.settings.rabbitmq_host = rabbitmq_host
                    self.settings.rabbitmq_port = rabbitmq_port
                    
                    # Save to file
                    self.settings.save()
                    
                    st.success("✅ Settings saved successfully!")
                    st.info("ℹ️ Please restart the application for changes to take effect")
                except Exception as e:
                    st.error(f"❌ Error saving settings: {e}")
            
    def _render_task_management(self):
        """Render task management interface."""
        st.header("Task Management")
        
        # Create new task
        with st.expander("Create New Task"):
            task_id = st.text_input("Task ID", key="new_task_id")
            capabilities = st.multiselect(
                "Required Capabilities",
                options=[cap.value for cap in Capability],
                key="new_task_capabilities"
            )
            priority = st.slider("Priority", 1, 5, 3, key="new_task_priority")
            hours_to_deadline = st.number_input(
                "Hours to Deadline",
                min_value=1,
                value=24,
                key="new_task_deadline"
            )
            
            if st.button("Create Task"):
                try:
                    task = Task(
                        task_id=task_id,
                        required_capabilities=[Capability(cap) for cap in capabilities],
                        priority=priority,
                        deadline=datetime.utcnow() + timedelta(hours=hours_to_deadline)
                    )
                    
                    assigned_agent = self.role_manager.assign_task(task)
                    if assigned_agent:
                        st.success(f"Task assigned to agent: {assigned_agent}")
                        st.session_state.tasks.append(task)
                    else:
                        st.error("No suitable agent found for the task")
                        
                except Exception as e:
                    st.error(f"Error creating task: {e}")
                    
        # View active tasks
        st.subheader("Active Tasks")
        for task in st.session_state.tasks:
            with st.expander(f"Task: {task.task_id}"):
                st.write(f"Priority: {task.priority}")
                st.write(f"Deadline: {task.deadline}")
                st.write("Required Capabilities:")
                for cap in task.required_capabilities:
                    st.write(f"• {cap.value}")
                    
                assigned_agent = self.role_manager.get_task_agent(task.task_id)
                if assigned_agent:
                    st.write(f"Assigned to: {assigned_agent}")
                    
                if st.button(f"Complete Task {task.task_id}"):
                    if assigned_agent:
                        if self.role_manager.complete_task(assigned_agent, task.task_id):
                            st.session_state.tasks.remove(task)
                            st.success("Task marked as completed")
                            st.rerun()
                            
    def _render_agent_management(self):
        """Render agent management interface."""
        st.header("Agent Management")
        
        # Register new agent
        with st.expander("Register New Agent"):
            agent_id = st.text_input("Agent ID", key="new_agent_id")
            st.subheader("Capabilities")
            
            capabilities = []
            for cap in Capability:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(cap.value)
                with col2:
                    strength = st.slider(
                        "Strength",
                        0.0,
                        1.0,
                        0.5,
                        0.1,
                        key=f"strength_{cap.value}"
                    )
                    if strength > 0:
                        capabilities.append(AgentCapability(cap, strength))
                        
            if st.button("Register Agent"):
                try:
                    self.capability_register.register_agent(agent_id, capabilities)
                    st.success(f"Agent {agent_id} registered successfully")
                except Exception as e:
                    st.error(f"Error registering agent: {e}")
                    
        # View registered agents
        st.subheader("Registered Agents")
        for agent_id in self.capability_register.agent_capabilities:
            with st.expander(f"Agent: {agent_id}"):
                capabilities = self.capability_register.get_agent_capabilities(agent_id)
                for cap in capabilities:
                    st.write(f"• {cap.capability.value}: {cap.strength:.1f}")
                    
                active_tasks = self.role_manager.get_agent_tasks(agent_id)
                if active_tasks:
                    st.write("Active Tasks:")
                    for task in active_tasks:
                        st.write(f"• {task.task_id}")
                        
    def _render_communication(self):
        """Render communication interface."""
        st.header("Communication")
        
        # Send message
        with st.expander("Send Message"):
            sender = st.selectbox(
                "From Agent",
                options=list(self.capability_register.agent_capabilities.keys()),
                key="message_sender"
            )
            
            receiver = st.selectbox(
                "To Agent",
                options=list(self.capability_register.agent_capabilities.keys()),
                key="message_receiver"
            )
            
            message_type = st.selectbox(
                "Message Type",
                options=[t.value for t in MessageType],
                key="message_type"
            )
            
            content = st.text_area("Message Content", key="message_content")
            
            if st.button("Send Message"):
                try:
                    message = Message(
                        sender_id=sender,
                        receiver_id=receiver,
                        message_type=MessageType(message_type),
                        content={"text": content},
                        task_id="system_message"
                    )
                    
                    if self.message_broker.send_message(message):
                        st.session_state.messages.append(message)
                        st.success("Message sent successfully")
                    else:
                        st.error("Failed to send message")
                        
                except Exception as e:
                    st.error(f"Error sending message: {e}")
                    
        # View message history
        st.subheader("Message History")
        for msg in reversed(st.session_state.messages):
            with st.expander(f"Message: {msg.sender_id} → {msg.receiver_id}"):
                st.write(f"Type: {msg.message_type.value}")
                st.write(f"Content: {msg.content.get('text', '')}")
                st.write(f"Time: {msg.timestamp}")
                
    def _render_code_execution(self):
        """Render code execution interface."""
        st.header("Code Execution")
        
        language = st.selectbox(
            "Programming Language",
            options=["python", "javascript"],
            key="code_language"
        )
        
        code = st.text_area(
            "Code",
            height=200,
            key="code_input"
        )
        
        if st.button("Execute Code"):
            try:
                success, output, error = self.code_executor.execute_code(
                    code,
                    language
                )
                
                if success:
                    st.success("Code executed successfully")
                    st.code(output, language=language)
                else:
                    st.error("Code execution failed")
                    st.code(error, language=language)
                    
            except Exception as e:
                st.error(f"Error executing code: {e}")
                
    def cleanup(self):
        """Clean up resources."""
        try:
            self.memory_store.close()
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
