"""
Main entry point for the LangChain Multi-Agent System.
"""

import streamlit as st
from typing import Dict, List
from datetime import datetime, timedelta
import logging

# Update imports to use absolute paths
from src.memory.mongo_store import MongoMemoryStore
from src.communication.broker import MessageBroker
from src.communication.message import Message, MessageType
from src.roles.capability import Capability, AgentCapability, CapabilityRegister
from src.roles.role_manager import Task, RoleManager
from src.execution.code_executor import CodeExecutor
from src.settings import Settings, settings

# Rest of the file remains unchanged...
logger = logging.getLogger(__name__)

class SimpleMode:
    """Simple mode interface for the multi-agent system."""
    
    def __init__(self, parent_ui):
        """Initialize simple mode with reference to parent UI."""
        self.parent = parent_ui
        
    def render(self):
        """Render the simple mode interface."""
        st.title("LangChain Multi-Agent System")
        
        # Simple description
        st.markdown("""
        Enter your request below and the system will automatically:
        - Select the most appropriate agent(s)
        - Configure necessary settings
        - Execute your task efficiently
        """)
        
        # Large input field for user request
        user_request = st.text_area(
            "What would you like help with?",
            placeholder="Enter your request, question, or task...",
            height=150
        )
        
        # Submit button
        if st.button("Submit Request", type="primary"):
            if not user_request:
                st.error("Please enter a request")
                return
                
            try:
                # Create task with automatic configuration
                task_id = f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                
                # Analyze request to determine required capabilities
                # For now, we'll assign all capabilities with medium priority
                required_capabilities = [cap for cap in Capability]
                
                task = Task(
                    task_id=task_id,
                    required_capabilities=required_capabilities,
                    priority=3,
                    deadline=datetime.utcnow() + timedelta(hours=24)
                )
                
                # Auto-assign to best available agent
                assigned_agent = self.parent.role_manager.assign_task(task)
                
                if assigned_agent:
                    st.success("✅ Request submitted successfully")
                    st.info(f"Assigned to agent: {assigned_agent}")
                    
                    # Create system message for the request
                    message = Message(
                        sender_id="system",
                        receiver_id=assigned_agent,
                        message_type=MessageType.TASK,
                        content={"text": user_request},
                        task_id=task_id
                    )
                    
                    self.parent.message_broker.send_message(message)
                    st.session_state.messages.append(message)
                    st.session_state.tasks.append(task)
                else:
                    st.error("❌ No suitable agent available. Please try again later.")
                    
            except Exception as e:
                st.error(f"Error processing request: {e}")
        
        # Show active requests if any exist
        active_tasks = [task for task in st.session_state.tasks 
                       if (task.deadline - datetime.utcnow()).total_seconds() > 0]
        
        if active_tasks:
            st.markdown("---")
            st.subheader("Active Requests")
            
            for task in active_tasks:
                with st.expander(f"📋 Request {task.task_id}"):
                    # Find associated message
                    task_message = next(
                        (msg for msg in st.session_state.messages 
                         if msg.task_id == task.task_id),
                        None
                    )
                    
                    if task_message:
                        st.write("Request:", task_message.content.get('text', 'N/A'))
                    
                    assigned_agent = self.parent.role_manager.get_task_agent(task.task_id)
                    if assigned_agent:
                        st.write("Assigned to:", assigned_agent)
                    
                    hours_left = (task.deadline - datetime.utcnow()).total_seconds() / 3600
                    if hours_left > 0:
                        st.write(f"Time remaining: {hours_left:.1f} hours")
                    else:
                        st.error("OVERDUE")

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
            self.simple_mode = SimpleMode(self)
            
            # Initialize session state
            if 'messages' not in st.session_state:
                st.session_state.messages = []
            if 'tasks' not in st.session_state:
                st.session_state.tasks = []
            if 'show_welcome' not in st.session_state:
                st.session_state.show_welcome = True
            if 'interface_mode' not in st.session_state:
                st.session_state.interface_mode = 'simple'
                
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
            
            st.markdown("---")
            
            # System status (shown in both modes)
            st.header("System Status")
            self._render_system_status()
        
        # Render appropriate interface based on mode
        if st.session_state.interface_mode == 'simple':
            self.simple_mode.render()
        else:
            self._render_advanced_mode()
    
    def _render_advanced_mode(self):
        """Render the advanced mode interface."""
        st.title("LangChain Multi-Agent System")
        
        # Welcome message for first-time users
        if st.session_state.show_welcome:
            with st.expander("👋 Welcome! Click here to get started", expanded=True):
                st.markdown("""
                ### Quick Start Guide
                1. First, go to **Agent Management** to register agents with specific capabilities
                2. Then, create tasks in **Task Management** - they'll be automatically assigned to agents
                3. Use **Communication** to see messages between agents
                4. **Code Execution** lets you run Python or JavaScript code
                
                Click the ❌ in the top right to close this guide.
                """)
                if st.button("Don't show this again"):
                    st.session_state.show_welcome = False
                    st.rerun()
        
        # Main tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "Task Management",
            "Agent Management",
            "Communication",
            "Code Execution"
        ])
        
        with tab1:
            self._render_task_management()
            
        with tab2:
            self._render_agent_management()
            
        with tab3:
            self._render_communication()
            
        with tab4:
            self._render_code_execution()

    def _render_system_status(self):
        """Render system status information in the sidebar."""
        try:
            # MongoDB Status
            mongo_status = "🟢 Connected" if self.memory_store else "🔴 Disconnected"
            st.write("MongoDB:", mongo_status)
            
            # RabbitMQ Status
            rabbitmq_status = "🟢 Connected" if self.message_broker else "🔴 Disconnected"
            st.write("RabbitMQ:", rabbitmq_status)
            
            # Agent Stats
            st.write("---")
            st.write("System Stats:")
            st.write("• Registered Agents:", len(self.capability_register.agent_capabilities))
            st.write("• Active Tasks:", len(st.session_state.tasks))
            st.write("• Messages:", len(st.session_state.messages))
            
            # System Load
            if st.session_state.tasks:
                avg_priority = sum(task.priority for task in st.session_state.tasks) / len(st.session_state.tasks)
                st.progress(avg_priority/5, "System Load")
            
        except Exception as e:
            st.error(f"Error displaying system status: {e}")
            
    def _render_agent_management(self):
        """Render agent management interface."""
        st.header("Agent Management")
        
        # Register new agent
        with st.expander("➕ Register New Agent", expanded=not bool(self.capability_register.agent_capabilities)):
            agent_id = st.text_input(
                "Agent ID",
                key="new_agent_id",
                help="A unique identifier for this agent"
            )
            
            st.subheader("Capabilities")
            st.caption("Set the strength of each capability (0.0 = not capable, 1.0 = expert)")
            
            # Group capabilities by category
            capabilities = []
            categories = {
                'CODE': {
                    'code_generation': 'Generate code from descriptions',
                    'code_review': 'Review and improve existing code',
                    'code_optimization': 'Optimize code for better performance',
                    'code_documentation': 'Write clear code documentation'
                },
                'LANGUAGE': {
                    'creative_writing': 'Generate creative content',
                    'technical_writing': 'Write technical documentation',
                    'translation': 'Translate between languages',
                    'summarization': 'Summarize long content'
                },
                'REASONING': {
                    'math_reasoning': 'Solve mathematical problems',
                    'logical_reasoning': 'Apply logical problem solving',
                    'critical_analysis': 'Analyze and evaluate information'
                },
                'DATA': {
                    'data_analysis': 'Analyze and interpret data',
                    'data_visualization': 'Create data visualizations',
                    'research': 'Conduct research and analysis',
                    'fact_checking': 'Verify information accuracy'
                }
            }
            
            # Create scrollable container for capabilities
            for category, cap_dict in categories.items():
                st.markdown(f"### {category}")
                for cap_name, description in cap_dict.items():
                    st.write(cap_name)
                    st.caption(description)
                    strength = st.slider(
                        "Capability Strength",
                        min_value=0.0,
                        max_value=1.0,
                        value=0.0,
                        step=0.1,
                        key=f"strength_{cap_name}",
                        help=f"Set the agent's proficiency in {cap_name}"
                    )
                    if strength > 0:
                        capabilities.append(AgentCapability(Capability(cap_name), strength))
                    st.markdown("---")
                        
            if st.button("Register Agent"):
                try:
                    if not agent_id:
                        st.error("Please enter an Agent ID")
                    elif not capabilities:
                        st.error("Please set at least one capability")
                    else:
                        self.capability_register.register_agent(agent_id, capabilities)
                        st.success(f"✅ Agent {agent_id} registered successfully")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error registering agent: {e}")
                    
        # View registered agents
        if self.capability_register.agent_capabilities:
            st.subheader("Registered Agents")
            for agent_id in self.capability_register.agent_capabilities:
                with st.expander(f"🤖 Agent: {agent_id}"):
                    # Show capabilities with progress bars
                    capabilities = self.capability_register.get_agent_capabilities(agent_id)
                    for cap in capabilities:
                        st.progress(cap.strength, f"{cap.capability.value}: {cap.strength:.1f}")
                    
                    # Show active tasks
                    active_tasks = self.role_manager.get_agent_tasks(agent_id)
                    if active_tasks:
                        st.write("Active Tasks:")
                        for task in active_tasks:
                            st.write(f"• {task.task_id}")
        else:
            st.info("No agents registered yet. Register a new agent to get started!")
            
    def _render_task_management(self):
        """Render task management interface."""
        st.header("Task Management")
        
        # Create new task
        with st.expander("➕ Create New Task", expanded=not bool(st.session_state.tasks)):
            # Show help if no agents
            if not self.capability_register.agent_capabilities:
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
                        
                        assigned_agent = self.role_manager.assign_task(task)
                        if assigned_agent:
                            st.success(f"✅ Task assigned to agent: {assigned_agent}")
                            st.session_state.tasks.append(task)
                            st.rerun()
                        else:
                            st.error("❌ No suitable agent found for the task")
                        
                except Exception as e:
                    st.error(f"Error creating task: {e}")
                    
        # View active tasks
        if st.session_state.tasks:
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
                        assigned_agent = self.role_manager.get_task_agent(task.task_id)
                        if assigned_agent:
                            st.write("Assigned to:", assigned_agent)
                            
                    # Required capabilities
                    st.write("Required Capabilities:")
                    for cap in task.required_capabilities:
                        st.write(f"• {cap.value}")
                    
                    # Complete task button
                    if assigned_agent and st.button(f"✅ Complete Task {task.task_id}"):
                        if self.role_manager.complete_task(assigned_agent, task.task_id):
                            st.session_state.tasks.remove(task)
                            st.success("Task marked as completed")
                            st.rerun()
        else:
            st.info("No active tasks. Create a new task to get started!")
            
    def _render_communication(self):
        """Render communication interface."""
        st.header("Communication")
        
        # Send message
        with st.expander("✉️ Send Message"):
            # Show help if no agents
            if not self.capability_register.agent_capabilities:
                st.warning("⚠️ Please register at least one agent before sending messages.")
                st.markdown("Go to the **Agent Management** tab to register agents.")
                return
                
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
            
            content = st.text_area(
                "Message Content",
                key="message_content",
                height=100
            )
            
            if st.button("Send Message"):
                try:
                    if not content:
                        st.error("Please enter a message")
                    else:
                        message = Message(
                            sender_id=sender,
                            receiver_id=receiver,
                            message_type=MessageType(message_type),
                            content={"text": content},
                            task_id="system_message"
                        )
                        
                        if self.message_broker.send_message(message):
                            st.session_state.messages.append(message)
                            st.success("✅ Message sent successfully")
                            st.rerun()
                        else:
                            st.error("❌ Failed to send message")
                        
                except Exception as e:
                    st.error(f"Error sending message: {e}")
                    
        # View message history
        if st.session_state.messages:
            st.subheader("Message History")
            
            # Message filters
            col1, col2 = st.columns(2)
            with col1:
                filter_agent = st.selectbox(
                    "Filter by Agent",
                    options=["All"] + list(self.capability_register.agent_capabilities.keys())
                )
            with col2:
                filter_type = st.selectbox(
                    "Filter by Type",
                    options=["All"] + [t.value for t in MessageType]
                )
            
            # Display filtered messages
            for msg in reversed(st.session_state.messages):
                if (filter_agent == "All" or filter_agent in [msg.sender_id, msg.receiver_id]) and \
                   (filter_type == "All" or filter_type == msg.message_type.value):
                    with st.expander(f"📨 {msg.sender_id} → {msg.receiver_id}"):
                        st.write(f"Type: {msg.message_type.value}")
                        st.text_area("Content", value=msg.content.get('text', ''), disabled=True)
                        st.caption(f"Time: {msg.timestamp}")
        else:
            st.info("No messages yet. Send a message to get started!")
            
    def _render_code_execution(self):
        """Render code execution interface."""
        st.header("Code Execution")
        
        # Code editor
        language = st.selectbox(
            "Programming Language",
            options=["python", "javascript"],
            key="code_language"
        )
        
        # Example code templates
        examples = {
            "python": {
                "Hello World": 'print("Hello, World!")',
                "List Operations": """# Create and manipulate a list
numbers = [1, 2, 3, 4, 5]
squared = [x**2 for x in numbers]
print(f"Original: {numbers}")
print(f"Squared: {squared}")""",
                "Function Example": """def greet(name):
    return f"Hello, {name}!"
    
print(greet("User"))"""
            },
            "javascript": {
                "Hello World": 'console.log("Hello, World!");',
                "Array Operations": """// Create and manipulate an array
const numbers = [1, 2, 3, 4, 5];
const squared = numbers.map(x => x**2);
console.log("Original:", numbers);
console.log("Squared:", squared);""",
                "Function Example": """function greet(name) {
    return `Hello, ${name}!`;
}

console.log(greet("User"));"""
            }
        }
        
        example = st.selectbox(
            "Load Example",
            options=["Custom Code"] + list(examples[language].keys())
        )
        
        if example != "Custom Code":
            code = st.text_area(
                "Code",
                value=examples[language][example],
                height=200,
                key="code_input"
            )
        else:
            code = st.text_area(
                "Code",
                height=200,
                key="code_input",
                help="Enter your code here"
            )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            run = st.button("▶️ Run")
        with col2:
            st.caption("Press Ctrl+Enter in the code editor to run")
            
        if run or st.session_state.get('run_code', False):
            st.session_state.run_code = False
            if not code.strip():
                st.warning("Please enter some code to execute")
            else:
                try:
                    with st.spinner("Executing code..."):
                        success, output, error = self.code_executor.execute_code(
                            code,
                            language
                        )
                    
                    if success:
                        st.success("✅ Code executed successfully")
                        if output.strip():
                            st.code(output, language=language)
                        else:
                            st.info("(No output)")
                    else:
                        st.error("❌ Code execution failed")
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
