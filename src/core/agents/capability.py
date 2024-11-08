from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
from threading import Lock
import json
from datetime import datetime
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

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
        try:
            logger.debug(f"Getting category for capability: {capability.name}")
            categories = {
                'LANGUAGE': {'CREATIVE_WRITING', 'TECHNICAL_WRITING', 'TRANSLATION', 'SUMMARIZATION'},
                'CODE': {'CODE_GENERATION', 'CODE_REVIEW', 'CODE_OPTIMIZATION', 'CODE_DOCUMENTATION'},
                'REASONING': {'MATH_REASONING', 'LOGICAL_REASONING', 'CRITICAL_ANALYSIS'},
                'DATA': {'DATA_ANALYSIS', 'DATA_VISUALIZATION', 'RESEARCH', 'FACT_CHECKING'},
                'DOMAIN': {'SCIENTIFIC_REASONING', 'LEGAL_ANALYSIS', 'MEDICAL_KNOWLEDGE', 'FINANCIAL_ANALYSIS'},
                'TASK': {'TASK_PLANNING', 'TASK_PRIORITIZATION', 'RESOURCE_MANAGEMENT'},
                'MODEL': {'COMPUTER_USE'}
            }

            for category, caps in categories.items():
                if capability.name in caps:
                    logger.debug(f"Found category {category} for capability {capability.name}")
                    return category

            logger.debug(f"No specific category found for capability {capability.name}, using MISC")
            return 'MISC'

        except Exception as e:
            logger.error(f"Error getting category for capability {capability}: {str(e)}", exc_info=True)
            raise

@dataclass
class AgentCapability:
    """Represents an agent's capability and its strength."""
    capability: Capability
    strength: float  # 0.0 to 1.0 representing capability strength
    last_updated: datetime = datetime.utcnow()
    metadata: Optional[Dict] = None

    def __post_init__(self):
        """Validate capability parameters after initialization."""
        logger.debug(f"Validating new capability: {self.capability.name}")
        self.validate()

    def validate(self):
        """Validate capability parameters."""
        try:
            if not isinstance(self.capability, Capability):
                logger.error("Invalid capability type")
                raise ValueError("capability must be an instance of Capability enum")

            if not isinstance(self.strength, (int, float)):
                logger.error(f"Invalid strength type: {type(self.strength)}")
                raise ValueError("strength must be a number")

            if not 0.0 <= self.strength <= 1.0:
                logger.error(f"Invalid strength value: {self.strength}")
                raise ValueError("strength must be between 0.0 and 1.0")

            if self.metadata is not None and not isinstance(self.metadata, dict):
                logger.error(f"Invalid metadata type: {type(self.metadata)}")
                raise ValueError("metadata must be a dictionary")

            logger.debug(f"Capability {self.capability.name} validated successfully")

        except Exception as e:
            logger.error(f"Capability validation failed: {str(e)}", exc_info=True)
            raise

    def to_dict(self) -> Dict:
        """Convert capability to dictionary format."""
        try:
            logger.debug(f"Converting capability {self.capability.name} to dictionary")
            result = {
                "capability": self.capability.value,
                "strength": self.strength,
                "last_updated": self.last_updated.isoformat(),
                "metadata": self.metadata or {}
            }
            logger.debug("Capability successfully converted to dictionary")
            return result
        except Exception as e:
            logger.error(f"Error converting capability to dictionary: {str(e)}", exc_info=True)
            raise

    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentCapability':
        """Create capability from dictionary format."""
        try:
            logger.debug("Creating capability from dictionary")
            capability = cls(
                capability=Capability(data["capability"]),
                strength=float(data["strength"]),
                last_updated=datetime.fromisoformat(data["last_updated"]),
                metadata=data.get("metadata", {})
            )
            logger.debug(f"Successfully created capability {capability.capability.name}")
            return capability
        except Exception as e:
            logger.error(f"Error creating capability from dictionary: {str(e)}", exc_info=True)
            raise

class CapabilityRegister:
    """Registry for managing agent capabilities with thread safety and persistence."""

    def __init__(self, storage_path: Optional[str] = None):
        """Initialize capability register with optional persistence."""
        try:
            logger.info("Initializing CapabilityRegister")
            self.agent_capabilities: Dict[str, List[AgentCapability]] = {}
            self.storage_path = storage_path
            self.lock = Lock()

            if storage_path:
                logger.debug(f"Using storage path: {storage_path}")

            self._load_capabilities()
            logger.info("CapabilityRegister initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing CapabilityRegister: {str(e)}", exc_info=True)
            raise

    def _load_capabilities(self):
        """Load capabilities from storage if available."""
        if not self.storage_path:
            logger.debug("No storage path configured, skipping capability load")
            return

        try:
            logger.info(f"Loading capabilities from {self.storage_path}")
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                with self.lock:
                    for agent_id, caps in data.items():
                        self.agent_capabilities[agent_id] = [
                            AgentCapability.from_dict(cap) for cap in caps
                        ]
            logger.info(f"Successfully loaded capabilities for {len(self.agent_capabilities)} agents")

        except FileNotFoundError:
            logger.info("No existing capability storage found")
        except Exception as e:
            logger.error(f"Error loading capabilities: {str(e)}", exc_info=True)
            raise

    def _save_capabilities(self):
        """Save capabilities to storage if path is configured."""
        if not self.storage_path:
            logger.debug("No storage path configured, skipping capability save")
            return

        try:
            logger.debug("Preparing to save capabilities")
            with self.lock:
                data = {
                    agent_id: [cap.to_dict() for cap in caps]
                    for agent_id, caps in self.agent_capabilities.items()
                }

            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Successfully saved capabilities for {len(self.agent_capabilities)} agents")

        except Exception as e:
            logger.error(f"Error saving capabilities: {str(e)}", exc_info=True)
            raise

    def register_agent(self, agent_id: str, capabilities: List[AgentCapability]):
        """Register an agent's capabilities with validation."""
        try:
            logger.info(f"Registering capabilities for agent {agent_id}")

            if not isinstance(agent_id, str) or not agent_id.strip():
                logger.error("Invalid agent_id provided")
                raise ValueError("agent_id must be a non-empty string")

            if not isinstance(capabilities, list):
                logger.error("Invalid capabilities type")
                raise ValueError("capabilities must be a list")

            if not capabilities:
                logger.error("Empty capabilities list provided")
                raise ValueError("capabilities list cannot be empty")

            # Validate all capabilities before registering
            logger.debug(f"Validating {len(capabilities)} capabilities")
            for cap in capabilities:
                if not isinstance(cap, AgentCapability):
                    logger.error(f"Invalid capability type: {type(cap)}")
                    raise ValueError("All capabilities must be instances of AgentCapability")
                cap.validate()

            with self.lock:
                self.agent_capabilities[agent_id.strip()] = capabilities
                self._save_capabilities()

            logger.info(f"Successfully registered {len(capabilities)} capabilities for agent {agent_id}")

        except Exception as e:
            logger.error(f"Error registering agent capabilities: {str(e)}", exc_info=True)
            raise

    def update_capability(self, agent_id: str, capability: AgentCapability) -> bool:
        """Update a specific capability for an agent."""
        try:
            logger.info(f"Updating capability {capability.capability.name} for agent {agent_id}")

            if not isinstance(agent_id, str) or not agent_id.strip():
                logger.error("Invalid agent_id provided")
                raise ValueError("agent_id must be a non-empty string")

            capability.validate()

            with self.lock:
                if agent_id not in self.agent_capabilities:
                    logger.warning(f"Agent {agent_id} not found in registry")
                    return False

                for i, cap in enumerate(self.agent_capabilities[agent_id]):
                    if cap.capability == capability.capability:
                        self.agent_capabilities[agent_id][i] = capability
                        self._save_capabilities()
                        logger.info(f"Updated existing capability {capability.capability.name} for agent {agent_id}")
                        return True

                self.agent_capabilities[agent_id].append(capability)
                self._save_capabilities()
                logger.info(f"Added new capability {capability.capability.name} for agent {agent_id}")
                return True

        except Exception as e:
            logger.error(f"Error updating capability: {str(e)}", exc_info=True)
            raise

    def remove_capability(self, agent_id: str, capability: Capability) -> bool:
        """Remove a specific capability from an agent."""
        try:
            logger.info(f"Removing capability {capability.name} from agent {agent_id}")

            if not isinstance(agent_id, str) or not agent_id.strip():
                logger.error("Invalid agent_id provided")
                raise ValueError("agent_id must be a non-empty string")

            if not isinstance(capability, Capability):
                logger.error("Invalid capability type")
                raise ValueError("capability must be an instance of Capability enum")

            with self.lock:
                if agent_id not in self.agent_capabilities:
                    logger.warning(f"Agent {agent_id} not found in registry")
                    return False

                original_length = len(self.agent_capabilities[agent_id])
                self.agent_capabilities[agent_id] = [
                    cap for cap in self.agent_capabilities[agent_id]
                    if cap.capability != capability
                ]

                if len(self.agent_capabilities[agent_id]) < original_length:
                    self._save_capabilities()
                    logger.info(f"Successfully removed capability {capability.name} from agent {agent_id}")
                    return True

                logger.debug(f"Capability {capability.name} not found for agent {agent_id}")
                return False

        except Exception as e:
            logger.error(f"Error removing capability: {str(e)}", exc_info=True)
            raise

    def get_agent_capabilities(self, agent_id: str) -> Optional[List[AgentCapability]]:
        """Get capabilities for a specific agent."""
        try:
            logger.debug(f"Retrieving capabilities for agent {agent_id}")

            if not isinstance(agent_id, str) or not agent_id.strip():
                logger.error("Invalid agent_id provided")
                raise ValueError("agent_id must be a non-empty string")

            with self.lock:
                capabilities = self.agent_capabilities.get(agent_id.strip())
                if capabilities:
                    logger.info(f"Found {len(capabilities)} capabilities for agent {agent_id}")
                else:
                    logger.debug(f"No capabilities found for agent {agent_id}")
                return capabilities

        except Exception as e:
            logger.error(f"Error getting agent capabilities: {str(e)}", exc_info=True)
            raise

    def get_agents_by_category(self, category: str) -> Dict[str, List[AgentCapability]]:
        """Get all agents with capabilities in a specific category."""
        try:
            logger.info(f"Retrieving agents with capabilities in category: {category}")
            result = {}

            with self.lock:
                for agent_id, capabilities in self.agent_capabilities.items():
                    category_caps = [
                        cap for cap in capabilities
                        if Capability.get_category(cap.capability) == category.upper()
                    ]
                    if category_caps:
                        result[agent_id] = category_caps
                        logger.debug(f"Found {len(category_caps)} matching capabilities for agent {agent_id}")

            logger.info(f"Found {len(result)} agents with capabilities in category {category}")
            return result

        except Exception as e:
            logger.error(f"Error getting agents by category: {str(e)}", exc_info=True)
            raise

    def find_best_agent(self, required_capability: Capability) -> Optional[str]:
        """Find the best agent for a specific capability."""
        try:
            logger.info(f"Finding best agent for capability: {required_capability.name}")

            if not isinstance(required_capability, Capability):
                logger.error("Invalid capability type")
                raise ValueError("required_capability must be an instance of Capability enum")

            with self.lock:
                best_agent = None
                best_strength = 0.0

                for agent_id, capabilities in self.agent_capabilities.items():
                    for cap in capabilities:
                        if cap.capability == required_capability and cap.strength > best_strength:
                            best_agent = agent_id
                            best_strength = cap.strength
                            logger.debug(f"New best agent found: {agent_id} (strength: {best_strength})")

                if best_agent:
                    logger.info(f"Best agent for {required_capability.name}: {best_agent} (strength: {best_strength})")
                else:
                    logger.warning(f"No agent found with capability {required_capability.name}")

                return best_agent

        except Exception as e:
            logger.error(f"Error finding best agent: {str(e)}", exc_info=True)
            raise

    def find_agents_with_capability(self,
                                  required_capability: Capability,
                                  min_strength: float = 0.0) -> List[str]:
        """Find all agents with a specific capability above minimum strength."""
        try:
            logger.info(f"Finding agents with capability {required_capability.name} (min strength: {min_strength})")

            if not isinstance(required_capability, Capability):
                logger.error("Invalid capability type")
                raise ValueError("required_capability must be an instance of Capability enum")

            if not isinstance(min_strength, (int, float)):
                logger.error(f"Invalid min_strength type: {type(min_strength)}")
                raise ValueError("min_strength must be a number")

            if not 0.0 <= min_strength <= 1.0:
                logger.error(f"Invalid min_strength value: {min_strength}")
                raise ValueError("min_strength must be between 0.0 and 1.0")

            with self.lock:
                qualified_agents = []
                for agent_id, capabilities in self.agent_capabilities.items():
                    for cap in capabilities:
                        if cap.capability == required_capability and cap.strength >= min_strength:
                            qualified_agents.append(agent_id)
                            logger.debug(f"Found qualified agent: {agent_id} (strength: {cap.strength})")
                            break

                logger.info(f"Found {len(qualified_agents)} qualified agents")
                return qualified_agents

        except Exception as e:
            logger.error(f"Error finding agents with capability: {str(e)}", exc_info=True)
            raise

    def get_capability_matrix(self) -> Dict[str, Dict[Capability, float]]:
        """Get a matrix of all agents and their capabilities."""
        try:
            logger.debug("Generating capability matrix")

            with self.lock:
                matrix = {
                    agent_id: {
                        cap.capability: cap.strength for cap in capabilities
                    }
                    for agent_id, capabilities in self.agent_capabilities.items()
                }

            logger.info(f"Generated capability matrix for {len(matrix)} agents")
            return matrix

        except Exception as e:
            logger.error(f"Error getting capability matrix: {str(e)}", exc_info=True)
            raise
