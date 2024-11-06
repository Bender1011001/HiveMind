"""
Launcher script for HiveMind application.
Checks and starts required services before launching the main application.
"""

import subprocess
import sys
import time
import logging
import shutil
from typing import Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'  # Simplified format for better readability
)
logger = logging.getLogger(__name__)

def is_mongodb_installed() -> bool:
    """Check if MongoDB is installed."""
    return shutil.which('mongod') is not None

def is_rabbitmq_installed() -> bool:
    """Check if RabbitMQ is installed."""
    return shutil.which('rabbitmqctl') is not None

def check_mongodb_running() -> bool:
    """Check if MongoDB is running."""
    try:
        import pymongo
        client = pymongo.MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
        client.server_info()
        return True
    except Exception:
        return False

def check_rabbitmq_running() -> bool:
    """Check if RabbitMQ is running."""
    try:
        result = subprocess.run(['rabbitmqctl', 'status'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        return result.returncode == 0
    except Exception:
        return False

def check_service(service_name: str) -> bool:
    """Check if a service is installed and running."""
    logger.info(f"\nChecking {service_name}...")
    
    # Check installation
    if service_name == "MongoDB":
        installed = is_mongodb_installed()
        if not installed:
            logger.error(f"{service_name} is not installed.")
            logger.info("Please install MongoDB from: https://www.mongodb.com/try/download/community")
            return False
        
        running = check_mongodb_running()
        if not running:
            logger.error(f"{service_name} is installed but not running.")
            logger.info("Start MongoDB using one of these methods:")
            logger.info("1. Start MongoDB service if installed as a service")
            logger.info("2. Run 'mongod' from command line")
            return False
            
    elif service_name == "RabbitMQ":
        installed = is_rabbitmq_installed()
        if not installed:
            logger.error(f"{service_name} is not installed.")
            logger.info("Please install RabbitMQ from: https://www.rabbitmq.com/download.html")
            return False
            
        running = check_rabbitmq_running()
        if not running:
            logger.error(f"{service_name} is installed but not running.")
            logger.info("Start RabbitMQ using one of these methods:")
            logger.info("1. Start RabbitMQ service if installed as a service")
            logger.info("2. Run 'rabbitmq-server' from command line")
            return False
    
    logger.info(f"{service_name} is installed and running properly.")
    return True

def main():
    """Main launcher function."""
    logger.info("HiveMind Launcher")
    logger.info("=================")
    
    # Required services
    services = [
        "MongoDB",
        "RabbitMQ"
    ]
    
    # Check services
    all_services_running = True
    for service in services:
        if not check_service(service):
            all_services_running = False
    
    if not all_services_running:
        logger.error("\nCannot start HiveMind: Required services are not ready.")
        logger.info("Please fix the issues mentioned above and try again.")
        sys.exit(1)
    
    # All services are running, start the main application
    logger.info("\nAll required services are running.")
    logger.info("Starting HiveMind application...")
    
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "run.py"])
    except KeyboardInterrupt:
        logger.info("\nApplication stopped by user")
    except Exception as e:
        logger.error(f"\nError running the application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
