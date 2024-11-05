"""Role management module for dynamic task assignment."""

from .capability import Capability, AgentCapability, CapabilityRegister
from .role_manager import Task, TaskAssignment, RoleManager

__all__ = ['Capability', 'AgentCapability', 'CapabilityRegister', 
           'Task', 'TaskAssignment', 'RoleManager']
