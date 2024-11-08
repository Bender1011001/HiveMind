"""Test script for performance monitoring functionality."""

import time
import sys
import os
import traceback

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.agents.metrics_collector import MetricsCollector
from src.utils.performance_monitor import PerformanceMonitor
from src.utils.logging_setup import setup_logging

# Set up logging
logger = setup_logging(__name__)

def test_standalone_performance_monitor():
    """Test the PerformanceMonitor class directly."""
    try:
        print("\nTesting standalone PerformanceMonitor...")
        monitor = PerformanceMonitor()

        # Collect metrics multiple times
        for i in range(3):
            monitor.collect_metrics()
            print(f"\nCollection {i + 1}:")
            print("Current Metrics:", monitor.get_current_metrics())
            time.sleep(1)

        # Get comprehensive report
        print("\nFinal Performance Report:")
        report = monitor.report()
        print("- Monitoring Duration:", f"{report['duration']:.2f} seconds")
        print("- Peak CPU Usage:", f"{report['peak'].get('cpu', 'N/A')}%")
        print("- Peak Memory Usage:", f"{report['peak'].get('memory', 'N/A')}%")
        print("- Average CPU Usage:", f"{report['average'].get('cpu', 'N/A')}%")
        print("- Average Memory Usage:", f"{report['average'].get('memory', 'N/A')}%")

        return True
    except Exception as e:
        print(f"\nError in standalone test: {str(e)}")
        traceback.print_exc()
        return False

def test_metrics_collector_integration():
    """Test the integration with MetricsCollector."""
    try:
        print("\nTesting MetricsCollector integration...")
        collector = MetricsCollector("test_agent")

        print("\nCollecting system metrics...")
        # Collect system metrics multiple times
        for i in range(3):
            print(f"\nCollection {i + 1}:")
            collector.collect_system_metrics()
            report = collector.get_system_performance_report()

            if 'current' in report and 'cpu' in report['current']:
                print("- Current CPU Usage:", f"{report['current']['cpu']['value']}%")
            if 'current' in report and 'memory' in report['current']:
                print("- Current Memory Usage:", f"{report['current']['memory']['percent']}%")

            time.sleep(1)

        # Get metric statistics
        print("\nMetric Statistics:")
        cpu_stats = collector.get_metric_stats('system_cpu')
        memory_stats = collector.get_metric_stats('system_memory')

        if cpu_stats:
            print("\nCPU Usage Stats:")
            print(f"- Average: {cpu_stats['average']:.2f}%")
            print(f"- Peak: {cpu_stats['max']:.2f}%")

        if memory_stats:
            print("\nMemory Usage Stats:")
            print(f"- Average: {memory_stats['average']:.2f}%")
            print(f"- Peak: {memory_stats['max']:.2f}%")

        return True
    except Exception as e:
        print(f"\nError in integration test: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Starting Performance Monitor Tests...")

    standalone_success = test_standalone_performance_monitor()
    integration_success = test_metrics_collector_integration()

    if standalone_success and integration_success:
        print("\nAll tests completed successfully!")
    else:
        print("\nSome tests failed. Please check the error messages above.")
        sys.exit(1)
