"""Communication component for the HiveMind UI."""

import streamlit as st
from typing import TYPE_CHECKING
from src.communication.message import Message, MessageType

if TYPE_CHECKING:
    from src.ui.app import MultiAgentUI

class Communication:
    """Component for handling inter-agent communication in the advanced mode interface."""
    
    def __init__(self, parent_ui: 'MultiAgentUI'):
        """Initialize communication component."""
        self.parent = parent_ui
        
    def render(self):
        """Render the communication interface."""
        st.header("Communication")
        
        # Send message
        with st.expander("✉️ Send Message"):
            self._render_message_sender()
                    
        # View message history
        if st.session_state.messages:
            self._render_message_history()
        else:
            st.info("No messages yet. Send a message to get started!")
            
    def _render_message_sender(self):
        """Render the message sending interface."""
        # Show help if no agents
        if not self.parent.capability_register.agent_capabilities:
            st.warning("⚠️ Please register at least one agent before sending messages.")
            st.markdown("Go to the **Agent Management** tab to register agents.")
            return
            
        sender = st.selectbox(
            "From Agent",
            options=list(self.parent.capability_register.agent_capabilities.keys()),
            key="message_sender"
        )
        
        receiver = st.selectbox(
            "To Agent",
            options=list(self.parent.capability_register.agent_capabilities.keys()),
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
                    
                    if self.parent.message_broker.send_message(message):
                        st.session_state.messages.append(message)
                        st.success("✅ Message sent successfully")
                        st.rerun()
                    else:
                        st.error("❌ Failed to send message")
                    
            except Exception as e:
                st.error(f"Error sending message: {e}")
                
    def _render_message_history(self):
        """Render the message history interface."""
        st.subheader("Message History")
        
        # Message filters
        col1, col2 = st.columns(2)
        with col1:
            filter_agent = st.selectbox(
                "Filter by Agent",
                options=["All"] + list(self.parent.capability_register.agent_capabilities.keys())
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
