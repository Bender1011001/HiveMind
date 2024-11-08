"""Metrics collection functionality for agents."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from threading import Lock
from statistics import mean, median, stdev
from ...utils.logging_setup import setup_logging
from ...utils.performance_monitor import PerformanceMonitor

# Set up centralized logging
logger = setup_logging(__name__)

class MetricsCollector:
    """Collects and manages performance metrics for agents."""

    def __init__(self, agent_id: str, retention_days: int = 30):
        """Initialize metrics collector."""
        try:
            logger.info(f"Initializing MetricsCollector for agent {agent_id}")
            self.agent_id = agent_id
            self.metrics: Dict[str, List[Tuple[datetime, float]]] = {}
            self.events: List[Dict[str, Any]] = []
            self.lock = Lock()
            self.retention_days = retention_days
            self.performance_monitor = PerformanceMonitor()
            logger.debug(f"MetricsCollector initialized for agent {agent_id} with {retention_days} days retention")
        except Exception as e:
            logger.error(f"Failed to initialize MetricsCollector for agent {agent_id}: {str(e)}", exc_info=True)
            raise

    def collect_system_metrics(self) -> None:
        """Collect current system performance metrics."""
        try:
            logger.debug(f"Collecting system metrics for agent {self.agent_id}")

            # Collect metrics using performance monitor
            self.performance_monitor.collect_metrics()
            current = self.performance_monitor.get_current_metrics()

            timestamp = datetime.utcnow()

            # Record CPU usage
            if 'cpu' in current:
                self.record_metric('system_cpu', current['cpu']['value'])

            # Record memory usage
            if 'memory' in current:
                self.record_metric('system_memory', current['memory']['percent'])

            # Record disk I/O if available
            if 'disk_io' in current:
                disk = current['disk_io']
                self.record_metric('system_disk_read', disk['read_bytes'])
                self.record_metric('system_disk_write', disk['write_bytes'])

            logger.info(f"System metrics collected for agent {self.agent_id}")
        except Exception as e:
            logger.error(f"Error collecting system metrics for agent {self.agent_id}: {str(e)}", exc_info=True)
            raise

    def get_system_performance_report(self) -> Dict[str, Any]:
        """Get a comprehensive system performance report."""
        try:
            logger.debug(f"Generating system performance report for agent {self.agent_id}")
            with self.lock:
                return self.performance_monitor.report()
        except Exception as e:
            logger.error(f"Error generating system performance report for agent {self.agent_id}: {str(e)}", exc_info=True)
            raise

    def record_metric(self, metric_name: str, value: float) -> None:
        """Record a numeric metric with timestamp."""
        try:
            logger.debug(f"Recording metric {metric_name} with value {value} for agent {self.agent_id}")

            if not isinstance(value, (int, float)):
                logger.error(f"Invalid metric value type: {type(value)}")
                raise ValueError("Metric value must be numeric")

            with self.lock:
                if metric_name not in self.metrics:
                    logger.debug(f"Creating new metric series for {metric_name}")
                    self.metrics[metric_name] = []

                self.metrics[metric_name].append((datetime.utcnow(), float(value)))
                self._cleanup_old_metrics(metric_name)

                logger.info(
                    f"Agent {self.agent_id} recorded metric {metric_name}: {value} "
                    f"(total records: {len(self.metrics[metric_name])})"
                )

        except Exception as e:
            logger.error(f"Error recording metric {metric_name} for agent {self.agent_id}: {str(e)}", exc_info=True)
            raise

    def record_event(self, event_name: str, details: Optional[Dict] = None, level: str = 'info') -> None:
        """Record a discrete event with optional details and importance level."""
        try:
            logger.debug(f"Recording {level} event {event_name} for agent {self.agent_id}")

            if not isinstance(event_name, str) or not event_name.strip():
                logger.error("Invalid event name")
                raise ValueError("Event name must be a non-empty string")

            with self.lock:
                event = {
                    'name': event_name,
                    'timestamp': datetime.utcnow().isoformat(),
                    'details': details or {},
                    'level': level
                }
                self.events.append(event)
                self._cleanup_old_events()

                logger.info(f"Agent {self.agent_id} recorded {level} event {event_name} with details: {details}")
                logger.debug(f"Total events recorded for agent {self.agent_id}: {len(self.events)}")

        except Exception as e:
            logger.error(f"Error recording event {event_name} for agent {self.agent_id}: {str(e)}", exc_info=True)
            raise

    def get_metric_stats(self, metric_name: str, time_window: Optional[timedelta] = None) -> Dict[str, float]:
        """Get statistical summary of a metric with optional time window."""
        try:
            logger.debug(f"Calculating statistics for metric {metric_name} for agent {self.agent_id}")

            with self.lock:
                if metric_name not in self.metrics or not self.metrics[metric_name]:
                    logger.info(f"No data found for metric {metric_name} for agent {self.agent_id}")
                    return {}

                # Filter values by time window if specified
                values = [v[1] for v in self.metrics[metric_name]]
                if time_window:
                    cutoff = datetime.utcnow() - time_window
                    values = [v[1] for v in self.metrics[metric_name] if v[0] >= cutoff]
                    logger.debug(f"Filtered to {len(values)} values within time window")

                if not values:
                    logger.info(f"No values found within specified time window for metric {metric_name}")
                    return {}

                try:
                    stats = {
                        'count': len(values),
                        'average': mean(values),
                        'median': median(values),
                        'min': min(values),
                        'max': max(values),
                        'std_dev': stdev(values) if len(values) > 1 else 0
                    }
                except Exception as e:
                    logger.error(f"Error calculating statistics: {str(e)}", exc_info=True)
                    stats = {
                        'count': len(values),
                        'average': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values)
                    }

                logger.info(f"Generated statistics for metric {metric_name} for agent {self.agent_id}: {stats}")
                return stats

        except Exception as e:
            logger.error(f"Error calculating statistics for metric {metric_name} for agent {self.agent_id}: {str(e)}", exc_info=True)
            raise

    def get_recent_events(self, limit: int = 100, level: Optional[str] = None,
                         start_time: Optional[datetime] = None) -> List[Dict]:
        """Get most recent events with filtering options."""
        try:
            logger.debug(f"Retrieving events for agent {self.agent_id} (limit: {limit}, level: {level})")

            with self.lock:
                filtered_events = self.events

                # Apply time filter
                if start_time:
                    filtered_events = [
                        e for e in filtered_events
                        if datetime.fromisoformat(e['timestamp']) >= start_time
                    ]
                    logger.debug(f"Filtered to {len(filtered_events)} events after time filter")

                # Apply level filter
                if level:
                    filtered_events = [
                        e for e in filtered_events
                        if e.get('level') == level
                    ]
                    logger.debug(f"Filtered to {len(filtered_events)} events after level filter")

                # Apply limit
                recent_events = filtered_events[-limit:]
                logger.info(f"Retrieved {len(recent_events)} events for agent {self.agent_id}")
                return recent_events

        except Exception as e:
            logger.error(f"Error retrieving recent events for agent {self.agent_id}: {str(e)}", exc_info=True)
            raise

    def _cleanup_old_metrics(self, metric_name: str) -> None:
        """Remove metrics older than retention period."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
            original_count = len(self.metrics[metric_name])

            self.metrics[metric_name] = [
                (ts, val) for ts, val in self.metrics[metric_name]
                if ts >= cutoff
            ]

            removed_count = original_count - len(self.metrics[metric_name])
            if removed_count > 0:
                logger.debug(f"Removed {removed_count} old records for metric {metric_name}")

        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {str(e)}", exc_info=True)
            raise

    def _cleanup_old_events(self) -> None:
        """Remove events older than retention period."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
            original_count = len(self.events)

            self.events = [
                event for event in self.events
                if datetime.fromisoformat(event['timestamp']) >= cutoff
            ]

            removed_count = original_count - len(self.events)
            if removed_count > 0:
                logger.debug(f"Removed {removed_count} old events")

        except Exception as e:
            logger.error(f"Error cleaning up old events: {str(e)}", exc_info=True)
            raise

    def clear(self) -> None:
        """Clear all collected metrics and events."""
        try:
            logger.debug(f"Clearing all metrics and events for agent {self.agent_id}")
            with self.lock:
                metrics_count = sum(len(values) for values in self.metrics.values())
                events_count = len(self.events)

                self.metrics.clear()
                self.events.clear()
                self.performance_monitor.clear_metrics()

                logger.info(f"Cleared {metrics_count} metrics and {events_count} events for agent {self.agent_id}")

        except Exception as e:
            logger.error(f"Error clearing metrics and events for agent {self.agent_id}: {str(e)}", exc_info=True)
            raise
