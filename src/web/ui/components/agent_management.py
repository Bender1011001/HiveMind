"""Agent management component for the HiveMind UI."""

import streamlit as st
from typing import TYPE_CHECKING, List
from src.roles.capability import Capability, AgentCapability

if TYPE_CHECKING:
    from src.ui.app import MultiAgentUI

class AgentManagement:
    """Component for managing agents in the advanced mode interface."""
    
    def __init__(self, parent_ui: 'MultiAgentUI'):
        """Initialize agent management component."""
        self.parent = parent_ui
        self.capability_categories = {
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
        
    def render(self):
        """Render the agent management interface."""
        st.header("Agent Management")
        
        # Register new agent
        with st.expander("➕ Register New Agent", expanded=not bool(self.parent.capability_register.agent_capabilities)):
            self._render_agent_registration()
                    
        # View registered agents
        if self.parent.capability_register.agent_capabilities:
            self._render_registered_agents()
        else:
            st.info("No agents registered yet. Register a new agent to get started!")
            
    def _render_agent_registration(self):
        """Render the agent registration interface."""
        agent_id = st.text_input(
            "Agent ID",
            key="new_agent_id",
            help="A unique identifier for this agent"
        )
        
        st.subheader("Capabilities")
        st.caption("Set the strength of each capability (0.0 = not capable, 1.0 = expert)")
        
        capabilities = self._collect_capabilities()
                    
        if st.button("Register Agent"):
            try:
                if not agent_id:
                    st.error("Please enter an Agent ID")
                elif not capabilities:
                    st.error("Please select at least one capability")
                else:
                    self.parent.capability_register.register_agent(agent_id, capabilities)
                    st.success(f"✅ Agent {agent_id} registered successfully")
                    st.rerun()
            except Exception as e:
                st.error(f"Error registering agent: {e}")
                
    def _collect_capabilities(self) -> List[AgentCapability]:
        """Collect capabilities from the UI inputs."""
        capabilities = []
        
        # Create scrollable container for capabilities
        for category, cap_dict in self.capability_categories.items():
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
                
        return capabilities
            
    def _render_registered_agents(self):
        """Render the list of registered agents."""
        st.subheader("Registered Agents")
        for agent_id in self.parent.capability_register.agent_capabilities:
            with st.expander(f"🤖 Agent: {agent_id}"):
                # Show capabilities with progress bars
                capabilities = self.parent.capability_register.get_agent_capabilities(agent_id)
                for cap in capabilities:
                    st.progress(cap.strength, f"{cap.capability.value}: {cap.strength:.1f}")
                
                # Show active tasks
                active_tasks = self.parent.role_manager.get_agent_tasks(agent_id)
                if active_tasks:
                    st.write("Active Tasks:")
                    for task in active_tasks:
                        st.write(f"• {task.task_id}")
