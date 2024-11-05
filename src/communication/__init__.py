"""Communication module for inter-agent messaging."""

from .message import Message, MessageType
from .broker import MessageBroker

__all__ = ['Message', 'MessageType', 'MessageBroker']
