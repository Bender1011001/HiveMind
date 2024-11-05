"""
Shared context management for multi-agent collaboration.
Provides centralized context storage and retrieval with vector embeddings.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from dataclasses import dataclass
import numpy as np

from ..memory.mongo_store import MongoMemoryStore
from ..memory.context_manager import SharedContext

logger = logging.getLogger(__name__)

@dataclass
class ContextEntry:
    """Represents a single context entry with metadata."""
    content: Dict[str, Any]
    timestamp: datetime
    source_agent: Optional[str]
    context_type: str
    relevance_score: float = 0.0
    vector_embedding: Optional[np.ndarray] = None

class ContextManager:
    """Manages shared context between agents using vector embeddings."""
    
    def __init__(self, shared_context: SharedContext, embedding_dimension: int = 768):
        """Initialize the context manager.
        
        Args:
            shared_context: SharedContext instance for persistent storage
            embedding_dimension: Dimension of vector embeddings
        """
        self.shared_context = shared_context
        self.embedding_dimension = embedding_dimension
        self.context_entries: Dict[str, List[ContextEntry]] = {}
        
    def add_context(self, 
                   task_id: str,
                   content: Dict[str, Any],
                   context_type: str,
                   source_agent: Optional[str] = None,
                   vector_embedding: Optional[np.ndarray] = None) -> None:
        """Add new context for a task.
        
        Args:
            task_id: ID of the task this context belongs to
            content: The context content to store
            context_type: Type of context (e.g., 'task_progress', 'agent_observation')
            source_agent: ID of the agent providing this context
            vector_embedding: Optional pre-computed vector embedding
        """
        entry = ContextEntry(
            content=content,
            timestamp=datetime.utcnow(),
            source_agent=source_agent,
            context_type=context_type,
            vector_embedding=vector_embedding
        )
        
        if task_id not in self.context_entries:
            self.context_entries[task_id] = []
            
        self.context_entries[task_id].append(entry)
        
        # Persist to shared context
        self.shared_context.update_task(
            task_id,
            source_agent,
            {
                "context_type": context_type,
                "content": content,
                "timestamp": entry.timestamp.isoformat()
            }
        )
        
        logger.info(f"Added {context_type} context for task {task_id}")
        
    def get_context(self,
                   task_id: str,
                   context_type: Optional[str] = None,
                   source_agent: Optional[str] = None,
                   time_window: Optional[int] = None,  # minutes
                   k: Optional[int] = None) -> List[ContextEntry]:
        """Retrieve context entries for a task with optional filtering.
        
        Args:
            task_id: ID of the task to get context for
            context_type: Optional filter by context type
            source_agent: Optional filter by source agent
            time_window: Optional time window in minutes
            k: Optional limit on number of entries to return
            
        Returns:
            List of matching context entries
        """
        if task_id not in self.context_entries:
            return []
            
        entries = self.context_entries[task_id]
        
        # Apply filters
        if context_type:
            entries = [e for e in entries if e.context_type == context_type]
            
        if source_agent:
            entries = [e for e in entries if e.source_agent == source_agent]
            
        if time_window:
            cutoff = datetime.utcnow() - timedelta(minutes=time_window)
            entries = [e for e in entries if e.timestamp >= cutoff]
            
        # Sort by timestamp descending
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        
        if k:
            entries = entries[:k]
            
        return entries
        
    def get_similar_contexts(self,
                           task_id: str,
                           query_embedding: np.ndarray,
                           k: int = 5,
                           score_threshold: float = 0.7) -> List[ContextEntry]:
        """Find similar contexts using vector similarity.
        
        Args:
            task_id: ID of the task to search contexts for
            query_embedding: Vector embedding to compare against
            k: Number of similar contexts to return
            score_threshold: Minimum similarity score threshold
            
        Returns:
            List of similar context entries
        """
        if task_id not in self.context_entries:
            return []
            
        entries = [
            e for e in self.context_entries[task_id]
            if e.vector_embedding is not None
        ]
        
        # Calculate cosine similarities
        for entry in entries:
            similarity = np.dot(query_embedding, entry.vector_embedding) / \
                        (np.linalg.norm(query_embedding) * np.linalg.norm(entry.vector_embedding))
            entry.relevance_score = float(similarity)
            
        # Filter and sort by similarity
        similar_entries = [
            e for e in entries
            if e.relevance_score >= score_threshold
        ]
        similar_entries.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return similar_entries[:k]
        
    def update_context(self,
                      task_id: str,
                      context_id: str,
                      updates: Dict[str, Any]) -> bool:
        """Update an existing context entry.
        
        Args:
            task_id: ID of the task
            context_id: ID of the context entry to update
            updates: Dictionary of updates to apply
            
        Returns:
            True if update successful, False otherwise
        """
        if task_id not in self.context_entries:
            return False
            
        entry = next(
            (e for e in self.context_entries[task_id] 
             if id(e) == int(context_id)),
            None
        )
        
        if not entry:
            return False
            
        # Update fields
        entry.content.update(updates)
        
        # Persist update
        self.shared_context.update_task(
            task_id,
            entry.source_agent,
            {
                "context_type": entry.context_type,
                "content": entry.content,
                "timestamp": entry.timestamp.isoformat()
            }
        )
        
        return True
        
    def clear_context(self, task_id: str) -> None:
        """Clear all context for a task.
        
        Args:
            task_id: ID of the task to clear context for
        """
        if task_id in self.context_entries:
            del self.context_entries[task_id]
            logger.info(f"Cleared context for task {task_id}")
