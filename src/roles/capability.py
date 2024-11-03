from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
import logging
from threading import Lock
import json
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Capability(Enum):
    """Enum representing different agent capabilities."""
    # Language Processing
    CREATIVE_WRITING = "creative_writing"
    TECHNICAL_WRITING = "technical_writing"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    
    # Code Related
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    CODE_OPTIMIZATION = "code_optimization"
    CODE_DOCUMENTATION = "code_documentation"
    
    # Reasoning
    MATH_REASONING = "math_reasoning"
    LOGICAL_REASONING = "logical_reasoning"
    CRITICAL_ANALYSIS = "critical_analysis"
    
    # Data & Research
    DATA_ANALYSIS = "data_analysis"
    DATA_VISUALIZATION = "data_visualization"
    RESEARCH = "research"
    FACT_CHECKING = "fact_checking"
    
    # Domain Specific
    SCIENTIFIC_REASONING = "scientific_reasoning"
    LEGAL_ANALYSIS = "legal_analysis"
    MEDICAL_KNOWLEDGE = "medical_knowledge"
    FINANCIAL_ANALYSIS = "financial_analysis"
    
    # Task Management
    TASK_PLANNING = "task_planning"
    TASK_PRIORITIZATION = "task_prioritization"
    RESOURCE_MANAGEMENT = "resource_management"

    # Model Specific
    COMPUTER_USE = "computer_use"  # Added for Claude 3.5 Sonnet
    
    @classmethod
    def get_category(cls, capability: 'Capability') -> str:
        """Get the category of a capability."""
        categories = {
            'LANGUAGE': {'CREATIVE_WRITING', 'TECHNICAL_WRITING', 'TRANSLATION', 'SUMMARIZATION'},
            'CODE': {'CODE_GENERATION', 'CODE_REVIEW', 'CODE_OPTIMIZATION', 'CODE_DOCUMENTATION'},
            'REASONING': {'MATH_REASONING', 'LOGICAL_REASONING', 'CRITICAL_ANALYSIS'},
            'DATA': {'DATA_ANALYSIS', 'DATA_VISUALIZATION', 'RESEARCH', 'FACT_CHECKING'},
            'DOMAIN': {'SCIENTIFIC_REASONING', 'LEGAL_ANALYSIS', 'MEDICAL_KNOWLEDGE', 'FINANCIAL_ANALYSIS'},
            'TASK': {'TASK_PLANNING', 'TASK_PRIORITIZATION', 'RESOURCE_MANAGEMENT'},
            'MODEL': {'COMPUTER_USE'}  # Added category for model-specific capabilities
        }
        
        for category, caps in categories.items():
            if capability.name in caps:
                return category
        return 'MISC'

@dataclass
class AgentCapability:
    """Represents an agent's capability and its strength."""
    capability: Capability
    strength: float  # 0.0 to 1.0 representing capability strength
    last_updated: datetime = datetime.utcnow()
    metadata: Optional[Dict] = None
    
    def __post_init__(self):
        """Validate capability parameters after initialization."""
        self.validate()
        
    def validate(self):
        """Validate capability parameters."""
        if not isinstance(self.capability, Capability):
            raise ValueError("capability must be an instance of Capability enum")
        if not isinstance(self.strength, (int, float)):
            raise ValueError("strength must be a number")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError("strength must be between 0.0 and 1.0")
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
    
    def to_dict(self) -> Dict:
        """Convert capability to dictionary format."""
        return {
            "capability": self.capability.value,
            "strength": self.strength,
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentCapability':
        """Create capability from dictionary format."""
        return cls(
            capability=Capability(data["capability"]),
            strength=float(data["strength"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            metadata=data.get("metadata", {})
        )

class CapabilityRegister:
    """Registry for managing agent capabilities with thread safety and persistence."""
    
    def __init__(self, storage_path: Optional[str] = None):
        """Initialize capability register with optional persistence."""
        self.agent_capabilities: Dict[str, List[AgentCapability]] = {}
        self.storage_path = storage_path
        self.lock = Lock()
        self._load_capabilities()
        
    def _load_capabilities(self):
        """Load capabilities from storage if available."""
        if self.storage_path:
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    with self.lock:
                        for agent_id, caps in data.items():
                            self.agent_capabilities[agent_id] = [
                                AgentCapability.from_dict(cap) for cap in caps
                            ]
                logger.info("Successfully loaded capabilities from storage")
            except FileNotFoundError:
                logger.info("No existing capability storage found")
            except Exception as e:
                logger.error(f"Error loading capabilities: {e}")
                
    def _save_capabilities(self):
        """Save capabilities to storage if path is configured."""
        if self.storage_path:
            try:
                with self.lock:
                    data = {
                        agent_id: [cap.to_dict() for cap in caps]
                        for agent_id, caps in self.agent_capabilities.items()
                    }
                with open(self.storage_path, 'w') as f:
                    json.dump(data, f, indent=2)
                logger.info("Successfully saved capabilities to storage")
            except Exception as e:
                logger.error(f"Error saving capabilities: {e}")
        
    def register_agent(self, agent_id: str, capabilities: List[AgentCapability]):
        """Register an agent's capabilities with validation."""
        try:
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError("agent_id must be a non-empty string")
            if not isinstance(capabilities, list):
                raise ValueError("capabilities must be a list")
            if not capabilities:
                raise ValueError("capabilities list cannot be empty")
                
            # Validate all capabilities before registering
            for cap in capabilities:
                if not isinstance(cap, AgentCapability):
                    raise ValueError("All capabilities must be instances of AgentCapability")
                cap.validate()
                
            with self.lock:
                self.agent_capabilities[agent_id.strip()] = capabilities
                self._save_capabilities()
                
            logger.info(f"Successfully registered capabilities for agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Error registering agent capabilities: {e}")
            raise
        
    def update_capability(self, agent_id: str, capability: AgentCapability) -> bool:
        """Update a specific capability for an agent."""
        try:
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError("agent_id must be a non-empty string")
            capability.validate()
            
            with self.lock:
                if agent_id not in self.agent_capabilities:
                    return False
                    
                for i, cap in enumerate(self.agent_capabilities[agent_id]):
                    if cap.capability == capability.capability:
                        self.agent_capabilities[agent_id][i] = capability
                        self._save_capabilities()
                        logger.info(f"Updated capability {capability.capability} for agent {agent_id}")
                        return True
                        
                self.agent_capabilities[agent_id].append(capability)
                self._save_capabilities()
                logger.info(f"Added new capability {capability.capability} for agent {agent_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating capability: {e}")
            raise
        
    def remove_capability(self, agent_id: str, capability: Capability) -> bool:
        """Remove a specific capability from an agent."""
        try:
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError("agent_id must be a non-empty string")
            if not isinstance(capability, Capability):
                raise ValueError("capability must be an instance of Capability enum")
                
            with self.lock:
                if agent_id not in self.agent_capabilities:
                    return False
                    
                original_length = len(self.agent_capabilities[agent_id])
                self.agent_capabilities[agent_id] = [
                    cap for cap in self.agent_capabilities[agent_id]
                    if cap.capability != capability
                ]
                
                if len(self.agent_capabilities[agent_id]) < original_length:
                    self._save_capabilities()
                    logger.info(f"Removed capability {capability} from agent {agent_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error removing capability: {e}")
            raise
        
    def get_agent_capabilities(self, agent_id: str) -> Optional[List[AgentCapability]]:
        """Get capabilities for a specific agent."""
        try:
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError("agent_id must be a non-empty string")
                
            with self.lock:
                return self.agent_capabilities.get(agent_id.strip())
        except Exception as e:
            logger.error(f"Error getting agent capabilities: {e}")
            raise
        
    def get_agents_by_category(self, category: str) -> Dict[str, List[AgentCapability]]:
        """Get all agents with capabilities in a specific category."""
        try:
            result = {}
            with self.lock:
                for agent_id, capabilities in self.agent_capabilities.items():
                    category_caps = [
                        cap for cap in capabilities
                        if Capability.get_category(cap.capability) == category.upper()
                    ]
                    if category_caps:
                        result[agent_id] = category_caps
            return result
        except Exception as e:
            logger.error(f"Error getting agents by category: {e}")
            raise
        
    def find_best_agent(self, required_capability: Capability) -> Optional[str]:
        """Find the best agent for a specific capability."""
        try:
            if not isinstance(required_capability, Capability):
                raise ValueError("required_capability must be an instance of Capability enum")
                
            with self.lock:
                best_agent = None
                best_strength = 0.0
                
                for agent_id, capabilities in self.agent_capabilities.items():
                    for cap in capabilities:
                        if cap.capability == required_capability and cap.strength > best_strength:
                            best_agent = agent_id
                            best_strength = cap.strength
                            
                return best_agent
        except Exception as e:
            logger.error(f"Error finding best agent: {e}")
            raise
        
    def find_agents_with_capability(self, 
                                  required_capability: Capability,
                                  min_strength: float = 0.0) -> List[str]:
        """Find all agents with a specific capability above minimum strength."""
        try:
            if not isinstance(required_capability, Capability):
                raise ValueError("required_capability must be an instance of Capability enum")
            if not isinstance(min_strength, (int, float)):
                raise ValueError("min_strength must be a number")
            if not 0.0 <= min_strength <= 1.0:
                raise ValueError("min_strength must be between 0.0 and 1.0")
                
            with self.lock:
                qualified_agents = []
                for agent_id, capabilities in self.agent_capabilities.items():
                    for cap in capabilities:
                        if cap.capability == required_capability and cap.strength >= min_strength:
                            qualified_agents.append(agent_id)
                            break
                return qualified_agents
        except Exception as e:
            logger.error(f"Error finding agents with capability: {e}")
            raise
            
    def get_capability_matrix(self) -> Dict[str, Dict[Capability, float]]:
        """Get a matrix of all agents and their capabilities."""
        try:
            with self.lock:
                return {
                    agent_id: {
                        cap.capability: cap.strength for cap in capabilities
                    }
                    for agent_id, capabilities in self.agent_capabilities.items()
                }
        except Exception as e:
            logger.error(f"Error getting capability matrix: {e}")
            raise
