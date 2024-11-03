"""
Launcher script for HiveMind application.
Checks and starts required services before launching the main application.
"""

import subprocess
import sys
import time
import logging
from typing import Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_service_status(service_name: str) -> bool:
    """Check if a Windows service is running."""
    try:
        output = subprocess.check_output(['net', 'start'], text=True)
        return service_name in output
    except subprocess.CalledProcessError:
        return False

def start_service(service_name: str) -> Tuple[bool, str]:
    """Start a Windows service."""
    try:
        subprocess.check_output(['net', 'start', service_name], text=True)
        return True, f"Successfully started {service_name}"
    except subprocess.CalledProcessError as e:
        return False, f"Failed to start {service_name}: {str(e)}"

def ensure_service(service_name: str) -> bool:
    """Ensure a service is running, start it if it's not."""
    logger.info(f"Checking {service_name} status...")
    
    if check_service_status(service_name):
        logger.info(f"{service_name} is already running")
        return True
    
    logger.info(f"{service_name} is not running. Attempting to start...")
    success, message = start_service(service_name)
    logger.info(message)
    
    if success:
        # Give the service some time to fully start
        time.sleep(5)
        return True
    return False

def main():
    """Main launcher function."""
    # Required services
    services = [
        "MongoDB",
        "RabbitMQ"
    ]
    
    # Check and start services
    all_services_running = True
    for service in services:
        if not ensure_service(service):
            all_services_running = False
            logger.error(f"Failed to ensure {service} is running")
    
    if not all_services_running:
        logger.error("Failed to start all required services. Please start them manually.")
        sys.exit(1)
    
    # All services are running, start the main application
    logger.info("All required services are running. Starting the application...")
    
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "run.py"])
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Error running the application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
