"""Agent activity monitoring component for the UI."""

import streamlit as st
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any
from src.utils.event_bus import EventBus

class AgentActivity:
    """Component for monitoring and visualizing agent activities."""
    
    def __init__(self, event_bus: EventBus):
        """Initialize agent activity monitor."""
        self.event_bus = event_bus
        self.activities: Dict[str, List[Dict[str, Any]]] = {}
        self.max_history_per_agent = 100
        self.detail_level = "normal"
        
        # Subscribe to agent events
        self.event_bus.subscribe('agent_thought_process', self._handle_thought_process)
        self.event_bus.subscribe('agent_action', self._handle_action)
        self.event_bus.subscribe('agent_error', self._handle_error)
        self.event_bus.subscribe('agent_api_interaction', self._handle_api_interaction)
        
    def _handle_thought_process(self, event_data: Dict[str, Any]) -> None:
        """Handle agent thought process events."""
        agent_id = event_data['agent_id']
        self._add_activity(agent_id, {
            'timestamp': datetime.now().isoformat(),
            'type': 'thought_process',
            'content': event_data.get('thought', ''),
            'context': event_data.get('context', {}),
            'status': 'info'
        })

    def _handle_action(self, event_data: Dict[str, Any]) -> None:
        """Handle agent action events."""
        agent_id = event_data['agent_id']
        self._add_activity(agent_id, {
            'timestamp': datetime.now().isoformat(),
            'type': 'action',
            'content': event_data.get('action', ''),
            'result': event_data.get('result', ''),
            'status': 'success'
        })

    def _handle_error(self, event_data: Dict[str, Any]) -> None:
        """Handle agent error events."""
        agent_id = event_data['agent_id']
        self._add_activity(agent_id, {
            'timestamp': datetime.now().isoformat(),
            'type': 'error',
            'content': event_data.get('error', 'Unknown error'),
            'stack_trace': event_data.get('stack_trace', ''),
            'status': 'error'
        })

    def _handle_api_interaction(self, event_data: Dict[str, Any]) -> None:
        """Handle agent API interaction events."""
        agent_id = event_data['agent_id']
        self._add_activity(agent_id, {
            'timestamp': datetime.now().isoformat(),
            'type': 'api_interaction',
            'content': event_data.get('operation', ''),
            'request': event_data.get('request', {}),
            'response': event_data.get('response', {}),
            'status': event_data.get('status', 'pending')
        })

    def _add_activity(self, agent_id: str, activity: Dict[str, Any]) -> None:
        """Add an activity to an agent's history."""
        if agent_id not in self.activities:
            self.activities[agent_id] = []
            
        self.activities[agent_id].append(activity)
        
        # Trim history if needed
        if len(self.activities[agent_id]) > self.max_history_per_agent:
            self.activities[agent_id] = self.activities[agent_id][-self.max_history_per_agent:]

    def render(self) -> None:
        """Render agent activity monitoring interface."""
        st.header("Agent Activity Monitor")

        # Detail level selector
        self.detail_level = st.select_slider(
            "Information Detail Level",
            options=["minimal", "normal", "detailed"],
            value=self.detail_level,
            help="Adjust the amount of information displayed"
        )

        # Agent selector
        if self.activities:
            selected_agent = st.selectbox(
                "Select Agent",
                options=list(self.activities.keys()),
                help="Choose an agent to view their activity"
            )

            if selected_agent:
                self._render_agent_activities(selected_agent)
        else:
            st.info("No agent activities recorded yet")

    def _render_agent_activities(self, agent_id: str) -> None:
        """Render activities for a specific agent."""
        activities = self.activities[agent_id]
        
        # Activity type filter
        activity_types = list(set(a['type'] for a in activities))
        selected_types = st.multiselect(
            "Filter by Activity Type",
            options=activity_types,
            default=activity_types
        )

        filtered_activities = [
            a for a in activities 
            if a['type'] in selected_types
        ]

        # Status summary
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Activities", len(filtered_activities))
        with col2:
            thought_count = len([a for a in filtered_activities if a['type'] == 'thought_process'])
            st.metric("Thought Processes", thought_count)
        with col3:
            action_count = len([a for a in filtered_activities if a['type'] == 'action'])
            st.metric("Actions", action_count)
        with col4:
            error_count = len([a for a in filtered_activities if a['status'] == 'error'])
            st.metric("Errors", error_count)

        # Activity stream
        st.subheader("Activity Stream")
        for activity in reversed(filtered_activities):
            self._render_activity_entry(activity)

    def _render_activity_entry(self, activity: Dict[str, Any]) -> None:
        """Render a single activity entry."""
        # Status indicators
        status_icons = {
            'success': '🟢',
            'error': '🔴',
            'info': 'ℹ️',
            'pending': '🟡'
        }
        icon = status_icons.get(activity['status'], '⚪')
        
        # Activity type icons
        type_icons = {
            'thought_process': '🤔',
            'action': '⚡',
            'error': '❌',
            'api_interaction': '🔄'
        }
        type_icon = type_icons.get(activity['type'], '📝')

        with st.expander(
            f"{icon} {type_icon} {activity['type'].replace('_', ' ').title()} - "
            f"{activity['timestamp'].split('T')[1].split('.')[0]}"
        ):
            # Basic information (shown in all detail levels)
            st.write(f"**Content:** {activity['content']}")
            
            # Additional details based on detail level
            if self.detail_level in ['normal', 'detailed']:
                if activity['type'] == 'action':
                    st.write(f"**Result:** {activity['result']}")
                elif activity['type'] == 'error':
                    st.error(f"Error: {activity['content']}")
                    
            if self.detail_level == 'detailed':
                if activity['type'] == 'thought_process':
                    st.json(activity.get('context', {}))
                elif activity['type'] == 'api_interaction':
                    with st.expander("Request Details"):
                        st.json(activity['request'])
                    with st.expander("Response Details"):
                        st.json(activity['response'])
                elif activity['type'] == 'error':
                    st.code(activity.get('stack_trace', 'No stack trace available'))
