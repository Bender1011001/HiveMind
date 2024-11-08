"""Central event bus for system-wide event handling and monitoring."""

from typing import Dict, List, Callable, Optional, Any
from datetime import datetime
from .logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

class EventBus:
    """
    Central event bus for system-wide event handling and monitoring.
    Implements a publish-subscribe pattern for decoupled communication.
    """

    def __init__(self):
        """Initialize the event bus."""
        logger.info("Initializing EventBus")
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history: List[Dict] = []
        logger.debug("EventBus initialized successfully")

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """
        Subscribe a callback function to a specific event type.

        Args:
            event_type: The type of event to subscribe to
            callback: Function to be called when event occurs
        """
        try:
            logger.debug(f"Adding subscriber for event type: {event_type}")
            if not callable(callback):
                logger.error("Callback must be callable")
                raise ValueError("Callback must be callable")

            if event_type not in self.subscribers:
                logger.debug(f"Creating new subscriber list for event type: {event_type}")
                self.subscribers[event_type] = []

            self.subscribers[event_type].append(callback)
            logger.info(f"New subscriber added for event type: {event_type} (Total subscribers: {len(self.subscribers[event_type])})")

        except Exception as e:
            logger.error(f"Error adding subscriber for event type {event_type}: {str(e)}", exc_info=True)
            raise

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """
        Remove a callback subscription for an event type.

        Args:
            event_type: The type of event to unsubscribe from
            callback: Function to be removed from subscribers
        """
        try:
            logger.debug(f"Removing subscriber for event type: {event_type}")
            if event_type in self.subscribers:
                if callback in self.subscribers[event_type]:
                    self.subscribers[event_type].remove(callback)
                    logger.info(f"Subscriber removed for event type: {event_type} (Remaining subscribers: {len(self.subscribers[event_type])})")
                else:
                    logger.warning(f"Callback not found for event type: {event_type}")
            else:
                logger.warning(f"No subscribers found for event type: {event_type}")

        except Exception as e:
            logger.error(f"Error removing subscriber for event type {event_type}: {str(e)}", exc_info=True)
            raise

    def emit(self, event_type: str, data: dict) -> None:
        """
        Emit an event to all subscribers.

        Args:
            event_type: The type of event being emitted
            data: Event data to be passed to subscribers
        """
        try:
            logger.debug(f"Emitting event of type: {event_type}")

            # Add timestamp and event type to data
            event_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                **data
            }

            # Store in history
            self.event_history.append(event_data)
            logger.debug(f"Event added to history (Total events: {len(self.event_history)})")

            # Notify subscribers
            if event_type in self.subscribers:
                subscriber_count = len(self.subscribers[event_type])
                logger.debug(f"Notifying {subscriber_count} subscribers for event type: {event_type}")

                for callback in self.subscribers[event_type]:
                    try:
                        callback(event_data)
                        logger.debug(f"Successfully called subscriber for event type: {event_type}")
                    except Exception as e:
                        logger.error(f"Error in event subscriber for {event_type}: {str(e)}", exc_info=True)
            else:
                logger.debug(f"No subscribers found for event type: {event_type}")

        except Exception as e:
            logger.error(f"Error emitting event of type {event_type}: {str(e)}", exc_info=True)
            raise

    def get_recent_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent events, optionally filtered by type.

        Args:
            event_type: Optional event type to filter by
            limit: Maximum number of events to return

        Returns:
            List of recent events
        """
        try:
            logger.debug(f"Retrieving recent events (Type: {event_type}, Limit: {limit})")

            if limit <= 0:
                logger.error("Limit must be positive")
                raise ValueError("Limit must be positive")

            if event_type:
                logger.debug(f"Filtering events by type: {event_type}")
                filtered_events = [e for e in self.event_history if e["event_type"] == event_type]
                result = filtered_events[-limit:]
                logger.info(f"Retrieved {len(result)} events of type {event_type}")
                return result

            result = self.event_history[-limit:]
            logger.info(f"Retrieved {len(result)} recent events")
            return result

        except Exception as e:
            logger.error(f"Error retrieving recent events: {str(e)}", exc_info=True)
            raise

    def clear_history(self) -> None:
        """Clear the event history."""
        try:
            logger.debug(f"Clearing event history (Current size: {len(self.event_history)})")
            self.event_history = []
            logger.info("Event history cleared successfully")

        except Exception as e:
            logger.error(f"Error clearing event history: {str(e)}", exc_info=True)
            raise

    def get_subscriber_count(self, event_type: Optional[str] = None) -> Dict[str, int]:
        """
        Get the number of subscribers for each event type or a specific type.

        Args:
            event_type: Optional specific event type to get count for

        Returns:
            Dictionary mapping event types to subscriber counts
        """
        try:
            logger.debug("Getting subscriber counts")

            if event_type:
                count = len(self.subscribers.get(event_type, []))
                logger.info(f"Subscriber count for {event_type}: {count}")
                return {event_type: count}

            counts = {event_type: len(subscribers)
                     for event_type, subscribers in self.subscribers.items()}
            logger.info(f"Retrieved subscriber counts for {len(counts)} event types")
            return counts

        except Exception as e:
            logger.error(f"Error getting subscriber counts: {str(e)}", exc_info=True)
            raise

    def validate_event_data(self, event_type: str, data: Dict[str, Any]) -> bool:
        """
        Validate event data before emission.

        Args:
            event_type: The type of event
            data: Event data to validate

        Returns:
            True if data is valid, False otherwise
        """
        try:
            logger.debug(f"Validating event data for type: {event_type}")

            # Check required fields
            if not isinstance(data, dict):
                logger.error("Event data must be a dictionary")
                return False

            # Validate event type
            if not isinstance(event_type, str) or not event_type.strip():
                logger.error("Event type must be a non-empty string")
                return False

            logger.debug("Event data validation successful")
            return True

        except Exception as e:
            logger.error(f"Error validating event data: {str(e)}", exc_info=True)
            return False
