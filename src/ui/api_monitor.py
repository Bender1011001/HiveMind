"""API monitoring component for the UI."""

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Any
from ..utils.event_bus import EventBus

class APIMonitor:
    """Component for monitoring and visualizing API calls."""
    
    def __init__(self, event_bus: EventBus):
        """Initialize API monitor with event bus connection."""
        self.event_bus = event_bus
        self.recent_calls: List[Dict[str, Any]] = []
        self.max_history = 100
        
        # Subscribe to API events
        self.event_bus.subscribe('api_call_start', self._handle_call_start)
        self.event_bus.subscribe('api_call_complete', self._handle_call_complete)
        self.event_bus.subscribe('api_call_error', self._handle_call_error)
        
    def _handle_call_start(self, event_data: Dict[str, Any]) -> None:
        """Handle API call start events."""
        self.recent_calls.append({
            'timestamp': event_data['timestamp'],
            'operation': event_data['operation'],
            'status': 'in_progress',
            'model': event_data.get('model', 'N/A'),
            'duration': None,
            'token_usage': None
        })
        self._trim_history()
        
    def _handle_call_complete(self, event_data: Dict[str, Any]) -> None:
        """Handle API call completion events."""
        self.recent_calls.append({
            'timestamp': event_data['timestamp'],
            'operation': event_data['operation'],
            'status': 'success',
            'model': event_data.get('model', 'N/A'),
            'duration': event_data.get('duration', 0),
            'token_usage': event_data.get('token_usage', {})
        })
        self._trim_history()
        
    def _handle_call_error(self, event_data: Dict[str, Any]) -> None:
        """Handle API call error events."""
        self.recent_calls.append({
            'timestamp': event_data['timestamp'],
            'operation': event_data['operation'],
            'status': 'error',
            'model': event_data.get('model', 'N/A'),
            'error': event_data.get('error', 'Unknown error'),
            'duration': event_data.get('duration', 0),
            'retry_count': event_data.get('retry_count', 0)
        })
        self._trim_history()
        
    def _trim_history(self) -> None:
        """Trim history to maximum size."""
        if len(self.recent_calls) > self.max_history:
            self.recent_calls = self.recent_calls[-self.max_history:]
            
    def render(self) -> None:
        """Render API monitoring interface."""
        st.subheader("API Monitor")
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        
        total_calls = len(self.recent_calls)
        success_calls = len([c for c in self.recent_calls if c['status'] == 'success'])
        error_calls = len([c for c in self.recent_calls if c['status'] == 'error'])
        
        with col1:
            st.metric("Total Calls", total_calls)
        with col2:
            st.metric("Successful", success_calls)
        with col3:
            st.metric("Errors", error_calls)
            
        # Recent calls table
        st.subheader("Recent API Calls")
        if self.recent_calls:
            df = pd.DataFrame(self.recent_calls)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp', ascending=False)
            
            # Format duration
            df['duration'] = df['duration'].apply(
                lambda x: f"{x:.2f}s" if x is not None else "N/A"
            )
            
            # Format token usage
            df['token_usage'] = df['token_usage'].apply(
                lambda x: f"{x.get('total_tokens', 'N/A')} tokens" if x else "N/A"
            )
            
            # Status indicators
            status_colors = {
                'success': '🟢',
                'error': '🔴',
                'in_progress': '🟡'
            }
            df['status'] = df['status'].apply(lambda x: f"{status_colors.get(x, '⚪')} {x}")
            
            st.dataframe(
                df[['timestamp', 'operation', 'status', 'model', 'duration', 'token_usage']],
                hide_index=True
            )
        else:
            st.info("No API calls recorded yet")
            
        # Error details
        errors = [c for c in self.recent_calls if c['status'] == 'error']
        if errors:
            st.subheader("Recent Errors")
            for error in errors[:5]:  # Show last 5 errors
                with st.expander(
                    f"Error in {error['operation']} at {error['timestamp']}"
                ):
                    st.write(f"**Error:** {error.get('error', 'Unknown error')}")
                    st.write(f"**Model:** {error.get('model', 'N/A')}")
                    st.write(f"**Retry Count:** {error.get('retry_count', 0)}")
