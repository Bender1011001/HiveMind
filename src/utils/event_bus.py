from typing import Dict, List, Callable
from datetime import datetime
import logging

class EventBus:
    """
    Central event bus for system-wide event handling and monitoring.
    Implements a publish-subscribe pattern for decoupled communication.
    """
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history: List[Dict] = []
        self.logger = logging.getLogger(__name__)

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """
        Subscribe a callback function to a specific event type.
        
        Args:
            event_type: The type of event to subscribe to
            callback: Function to be called when event occurs
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        self.logger.debug(f"New subscriber added for event type: {event_type}")

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """
        Remove a callback subscription for an event type.
        
        Args:
            event_type: The type of event to unsubscribe from
            callback: Function to be removed from subscribers
        """
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(callback)
            self.logger.debug(f"Subscriber removed for event type: {event_type}")

    def emit(self, event_type: str, data: dict) -> None:
        """
        Emit an event to all subscribers.
        
        Args:
            event_type: The type of event being emitted
            data: Event data to be passed to subscribers
        """
        # Add timestamp and event type to data
        event_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            **data
        }
        
        # Store in history
        self.event_history.append(event_data)
        
        # Notify subscribers
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(event_data)
                except Exception as e:
                    self.logger.error(f"Error in event subscriber: {str(e)}")

    def get_recent_events(self, event_type: str = None, limit: int = 100) -> List[Dict]:
        """
        Get recent events, optionally filtered by type.
        
        Args:
            event_type: Optional event type to filter by
            limit: Maximum number of events to return
            
        Returns:
            List of recent events
        """
        if event_type:
            filtered_events = [e for e in self.event_history if e["event_type"] == event_type]
            return filtered_events[-limit:]
        return self.event_history[-limit:]

    def clear_history(self) -> None:
        """Clear the event history."""
        self.event_history = []
        self.logger.debug("Event history cleared")
