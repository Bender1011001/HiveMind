"""API route definitions for the HiveMind system.

This module defines the REST API endpoints that external systems can use to interact
with the HiveMind system.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request
from ..core.agents.master_agent import MasterAgent
from ..core.messaging.broker import MessageBroker
from ..core.storage.context_manager import SharedContext
from ..utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

router = APIRouter()

@router.post("/tasks")
async def create_task(task_data: Dict[str, Any], request: Request):
    """Create a new task for processing."""
    try:
        logger.info("Received task creation request")
        logger.debug(f"Task data: {task_data}")

        client_host = request.client.host if request.client else "unknown"
        logger.debug(f"Request from client: {client_host}")

        # Implementation will be added in future phases
        logger.info("Task creation endpoint placeholder - implementation pending")
        pass

    except ValueError as e:
        logger.error(f"Invalid task data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, request: Request):
    """Get the status of a specific task."""
    try:
        logger.info(f"Received status request for task: {task_id}")

        client_host = request.client.host if request.client else "unknown"
        logger.debug(f"Request from client: {client_host}")

        # Implementation will be added in future phases
        logger.info("Task status endpoint placeholder - implementation pending")
        pass

    except ValueError as e:
        logger.error(f"Invalid task ID {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving status for task {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents")
async def register_agent(agent_data: Dict[str, Any], request: Request):
    """Register a new agent in the system."""
    try:
        logger.info("Received agent registration request")
        logger.debug(f"Agent data: {agent_data}")

        client_host = request.client.host if request.client else "unknown"
        logger.debug(f"Request from client: {client_host}")

        # Implementation will be added in future phases
        logger.info("Agent registration endpoint placeholder - implementation pending")
        pass

    except ValueError as e:
        logger.error(f"Invalid agent data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error registering agent: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system/status")
async def get_system_status(request: Request):
    """Get the current system status."""
    try:
        logger.info("Received system status request")

        client_host = request.client.host if request.client else "unknown"
        logger.debug(f"Request from client: {client_host}")

        # Implementation will be added in future phases
        logger.info("System status endpoint placeholder - implementation pending")
        pass

    except Exception as e:
        logger.error(f"Error retrieving system status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Error handling middleware
@router.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and their outcomes."""
    try:
        logger.info(f"Incoming {request.method} request to {request.url.path}")
        logger.debug(f"Request headers: {dict(request.headers)}")

        response = await call_next(request)

        logger.info(f"Request completed with status code: {response.status_code}")
        return response

    except Exception as e:
        logger.error(f"Unhandled error processing request: {str(e)}", exc_info=True)
        raise

# Startup and shutdown events
@router.on_event("startup")
async def startup_event():
    """Log when the API starts up."""
    logger.info("API router starting up")
    try:
        # Add any startup initialization here
        logger.info("API router startup complete")
    except Exception as e:
        logger.error(f"Error during API router startup: {str(e)}", exc_info=True)
        raise

@router.on_event("shutdown")
async def shutdown_event():
    """Log when the API shuts down."""
    logger.info("API router shutting down")
    try:
        # Add any cleanup code here
        logger.info("API router shutdown complete")
    except Exception as e:
        logger.error(f"Error during API router shutdown: {str(e)}", exc_info=True)
        raise
