from typing import List, Dict, Optional
from .capability import Capability, AgentCapability, CapabilityRegister
from .role_manager import Task, RoleManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MasterAgent:
    """Master Agent that analyzes tasks and delegates them appropriately."""
    
    def __init__(self, role_manager: RoleManager, capability_register: CapabilityRegister):
        """Initialize Master Agent with full capabilities."""
        self.role_manager = role_manager
        self.capability_register = capability_register
        self.agent_id = "master_agent"
        
        # Register master agent with all capabilities at maximum strength
        capabilities = [
            AgentCapability(capability=cap, strength=1.0)
            for cap in Capability
        ]
        self.capability_register.register_agent(self.agent_id, capabilities)
        
    def analyze_request(self, request: str) -> List[Capability]:
        """Analyze user request to determine required capabilities."""
        required_capabilities = set()
        
        # Language processing needs
        if any(kw in request.lower() for kw in ['write', 'summarize', 'explain', 'translate']):
            required_capabilities.add(Capability.TECHNICAL_WRITING)
            required_capabilities.add(Capability.CREATIVE_WRITING)
            
        # Code related needs
        if any(kw in request.lower() for kw in ['code', 'program', 'function', 'class', 'implement']):
            required_capabilities.add(Capability.CODE_GENERATION)
            required_capabilities.add(Capability.CODE_REVIEW)
            
        # Analysis needs
        if any(kw in request.lower() for kw in ['analyze', 'evaluate', 'assess']):
            required_capabilities.add(Capability.CRITICAL_ANALYSIS)
            required_capabilities.add(Capability.DATA_ANALYSIS)
            
        # Research needs
        if any(kw in request.lower() for kw in ['research', 'find', 'search']):
            required_capabilities.add(Capability.RESEARCH)
            required_capabilities.add(Capability.FACT_CHECKING)
            
        # Task management needs
        if any(kw in request.lower() for kw in ['plan', 'organize', 'manage']):
            required_capabilities.add(Capability.TASK_PLANNING)
            required_capabilities.add(Capability.TASK_PRIORITIZATION)
            
        # If no specific capabilities detected, add basic ones
        if not required_capabilities:
            required_capabilities.add(Capability.LOGICAL_REASONING)
            required_capabilities.add(Capability.CRITICAL_ANALYSIS)
            
        return list(required_capabilities)
        
    def process_request(self, request: str, priority: int = 3) -> Optional[str]:
        """Process user request and delegate to appropriate agent(s)."""
        try:
            # Analyze request to determine required capabilities
            required_capabilities = self.analyze_request(request)
            
            # Create task with 24h deadline
            task = Task(
                task_id=f"task_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                required_capabilities=required_capabilities,
                priority=priority,
                deadline=datetime.utcnow() + timedelta(hours=24),
                metadata={"original_request": request}
            )
            
            # Assign task to most suitable agent
            assigned_agent = self.role_manager.assign_task(task)
            
            if assigned_agent:
                logger.info(f"Task assigned to agent {assigned_agent}")
                return assigned_agent
            else:
                logger.warning("No suitable agent found for task")
                return None
                
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            raise
            
    def get_task_status(self, task_id: str) -> Dict:
        """Get status of a specific task."""
        try:
            assigned_agent = self.role_manager.get_task_agent(task_id)
            if not assigned_agent:
                return {"status": "not_found"}
                
            task_history = self.role_manager.get_task_history(task_id)
            if not task_history:
                return {"status": "unknown"}
                
            latest_assignment = task_history[-1]
            
            return {
                "status": "active" if assigned_agent else "completed",
                "assigned_agent": assigned_agent,
                "assigned_at": latest_assignment.assigned_at.isoformat(),
                "completed_at": getattr(latest_assignment, 'completed_at', None),
                "capability_match_score": latest_assignment.capability_match_score
            }
            
        except Exception as e:
            logger.error(f"Error getting task status: {e}")
            raise
