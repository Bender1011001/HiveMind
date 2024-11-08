"""Performance monitoring utilities for tracking system metrics."""

import time
import psutil
from collections import defaultdict
from typing import Dict, List, Any

class PerformanceMonitor:
    """Monitor and track system performance metrics."""

    def __init__(self):
        """Initialize the performance monitor with empty metrics storage."""
        self.metrics = {
            'cpu': [],
            'memory': [],
            'disk_io': []
        }
        self.start_time = time.time()

    def collect_metrics(self) -> None:
        """Collect current system metrics and store them with timestamps."""
        timestamp = time.time()

        # CPU metrics
        self.metrics['cpu'].append({
            'timestamp': timestamp,
            'value': psutil.cpu_percent(interval=1),
            'per_cpu': psutil.cpu_percent(interval=1, percpu=True)
        })

        # Memory metrics
        mem = psutil.virtual_memory()
        self.metrics['memory'].append({
            'timestamp': timestamp,
            'total': mem.total,
            'available': mem.available,
            'percent': mem.percent,
            'used': mem.used
        })

        # Disk I/O metrics
        disk_io = psutil.disk_io_counters()
        if disk_io:
            self.metrics['disk_io'].append({
                'timestamp': timestamp,
                'read_bytes': disk_io.read_bytes,
                'write_bytes': disk_io.write_bytes,
                'read_count': disk_io.read_count,
                'write_count': disk_io.write_count
            })

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get the most recent metrics for all monitored resources."""
        current = {}

        for metric_type, values in self.metrics.items():
            if values:
                current[metric_type] = values[-1]

        return current

    def get_peak_metrics(self) -> Dict[str, float]:
        """Get peak values for each metric type."""
        peaks = {}

        if self.metrics['cpu']:
            peaks['cpu'] = max(m['value'] for m in self.metrics['cpu'])

        if self.metrics['memory']:
            peaks['memory'] = max(m['percent'] for m in self.metrics['memory'])

        return peaks

    def get_average_metrics(self) -> Dict[str, float]:
        """Calculate average values for each metric type."""
        averages = {}

        if self.metrics['cpu']:
            averages['cpu'] = sum(m['value'] for m in self.metrics['cpu']) / len(self.metrics['cpu'])

        if self.metrics['memory']:
            averages['memory'] = sum(m['percent'] for m in self.metrics['memory']) / len(self.metrics['memory'])

        return averages

    def clear_metrics(self) -> None:
        """Clear all stored metrics."""
        self.metrics = {
            'cpu': [],
            'memory': [],
            'disk_io': []
        }
        self.start_time = time.time()

    def get_monitoring_duration(self) -> float:
        """Get the duration for which monitoring has been active."""
        return time.time() - self.start_time

    def report(self) -> Dict[str, Any]:
        """Generate a comprehensive report of system performance."""
        return {
            'duration': self.get_monitoring_duration(),
            'current': self.get_current_metrics(),
            'peak': self.get_peak_metrics(),
            'average': self.get_average_metrics()
        }
