"""Enhanced SharedContext with task dependencies, progress tracking, and vector embeddings."""

import os
import json
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime, timedelta
from threading import Lock
import numpy as np
from dataclasses import dataclass, asdict
from .mongo_store import MongoMemoryStore
from ..settings import settings
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

@dataclass
class ContextEntry:
    """Represents a single context entry with metadata."""
    content: Dict[str, Any]
    timestamp: datetime
    source_agent: Optional[str]
    context_type: str
    relevance_score: float = 0.0
    vector_embedding: Optional[np.ndarray] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary format."""
        try:
            data = asdict(self)
            # Convert numpy array to list if present
            if self.vector_embedding is not None:
                data['vector_embedding'] = self.vector_embedding.tolist()
            data['timestamp'] = self.timestamp.isoformat()
            return data
        except Exception as e:
            logger.error(f"Error converting context entry to dict: {str(e)}", exc_info=True)
            raise

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextEntry':
        """Create entry from dictionary format."""
        try:
            # Convert list back to numpy array if present
            if data.get('vector_embedding'):
                data['vector_embedding'] = np.array(data['vector_embedding'])
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
            return cls(**data)
        except Exception as e:
            logger.error(f"Error creating context entry from dict: {str(e)}", exc_info=True)
            raise

class SharedContext:
    """Manages shared context, task dependencies, and persistent learning between agents."""

    def __init__(self, memory_store: MongoMemoryStore, embedding_dimension: int = 768,
                 auto_persist: bool = True, persist_interval: int = 60):  # minutes
        """Initialize shared context manager."""
        try:
            logger.info("Initializing SharedContext manager")
            self.memory_store = memory_store
            self.lock = Lock()
            self.context_file = os.path.join(settings.shared_data_dir, 'shared_context.json')
            self.embedding_dimension = embedding_dimension
            self.context_entries: Dict[str, List[ContextEntry]] = {}
            self.auto_persist = auto_persist
            self.persist_interval = persist_interval
            self.last_persist_time = datetime.utcnow()

            logger.debug(f"Context file path: {self.context_file}")
            logger.debug(f"Embedding dimension: {embedding_dimension}")
            logger.debug(f"Auto persist: {auto_persist}, Interval: {persist_interval} minutes")

            self._load_context()
            logger.info("SharedContext manager initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing SharedContext: {str(e)}", exc_info=True)
            raise

    def _should_persist(self) -> bool:
        """Check if context should be persisted based on interval."""
        return (datetime.utcnow() - self.last_persist_time) >= timedelta(minutes=self.persist_interval)

    def _load_context(self):
        """Load shared context from file."""
        try:
            logger.debug(f"Loading context from {self.context_file}")
            if os.path.exists(self.context_file):
                with open(self.context_file, 'r') as f:
                    self.context = json.load(f)
                logger.info("Successfully loaded existing context file")
                logger.debug(f"Loaded context contains {len(self.context.get('tasks', {}))} tasks")

                # Load context entries
                entries_file = self.context_file.replace('.json', '_entries.json')
                if os.path.exists(entries_file):
                    logger.debug("Loading context entries")
                    with open(entries_file, 'r') as f:
                        entries_data = json.load(f)
                        self.context_entries = {
                            task_id: [ContextEntry.from_dict(e) for e in entries]
                            for task_id, entries in entries_data.items()
                        }
                    logger.debug(f"Loaded {len(self.context_entries)} task contexts")
            else:
                logger.info("No existing context file found, creating new context")
                self.context = {
                    'tasks': {},  # task_id -> task details
                    'agent_learnings': {},
                    'shared_knowledge': {},
                    'last_updated': datetime.utcnow().isoformat()
                }
                self._save_context()

        except Exception as e:
            logger.error(f"Error loading context: {str(e)}", exc_info=True)
            raise

    def _save_context(self):
        """Save shared context to file."""
        try:
            logger.debug(f"Saving context to {self.context_file}")
            self.context['last_updated'] = datetime.utcnow().isoformat()

            # Save main context
            with open(self.context_file, 'w') as f:
                json.dump(self.context, f, indent=2)

            # Save context entries separately
            entries_file = self.context_file.replace('.json', '_entries.json')
            entries_data = {
                task_id: [entry.to_dict() for entry in entries]
                for task_id, entries in self.context_entries.items()
            }
            with open(entries_file, 'w') as f:
                json.dump(entries_data, f, indent=2)

            logger.info("Successfully saved context to file")

            # Auto-persist to MongoDB if enabled
            if self.auto_persist and self._should_persist():
                logger.debug("Auto-persisting context to MongoDB")
                self.persist_to_mongo()
                self.last_persist_time = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error saving context: {str(e)}", exc_info=True)
            raise

    def update_task(self, task_id: str, agent_id: Optional[str], updates: Dict[str, Any]) -> None:
        """Update task details and progress."""
        try:
            logger.info(f"Updating task {task_id} with agent {agent_id}")
            logger.debug(f"Update content: {updates}")

            with self.lock:
                if task_id not in self.context['tasks']:
                    logger.debug(f"Creating new task entry for {task_id}")
                    self.context['tasks'][task_id] = {
                        'status': 'pending',
                        'assigned_agent': agent_id,
                        'progress': [],
                        'dependencies': updates.get('dependencies', []),
                        'metadata': updates.get('metadata', {}),
                        'created_at': datetime.utcnow().isoformat()
                    }

                task = self.context['tasks'][task_id]
                if agent_id:
                    task['assigned_agent'] = agent_id
                if 'status' in updates:
                    logger.info(f"Updating task {task_id} status to: {updates['status']}")
                    task['status'] = updates['status']
                if 'progress_update' in updates:
                    progress_entry = {
                        'timestamp': datetime.utcnow().isoformat(),
                        'agent_id': agent_id,
                        'update': updates['progress_update']
                    }
                    task['progress'].append(progress_entry)
                    logger.debug(f"Added progress update for task {task_id}")

                # Add context entry if provided
                if 'context_type' in updates and 'content' in updates:
                    logger.debug(f"Adding context entry of type {updates['context_type']}")
                    self.add_context(
                        task_id=task_id,
                        content=updates['content'],
                        context_type=updates['context_type'],
                        source_agent=agent_id,
                        vector_embedding=updates.get('vector_embedding')
                    )

                self._save_context()
                logger.info(f"Successfully updated task {task_id}")

        except Exception as e:
            logger.error(f"Error updating task {task_id}: {str(e)}", exc_info=True)
            raise

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task details."""
        try:
            logger.debug(f"Retrieving task details for {task_id}")
            task = self.context['tasks'].get(task_id)
            if task:
                logger.info(f"Found task {task_id} with status: {task.get('status')}")
            else:
                logger.info(f"No task found with ID {task_id}")
            return task
        except Exception as e:
            logger.error(f"Error retrieving task {task_id}: {str(e)}", exc_info=True)
            raise

    def add_agent_learning(self, agent_id: str, learning: Dict[str, Any],
                         category: Optional[str] = None) -> None:
        """Add a learning point from an agent that others might benefit from."""
        try:
            logger.info(f"Adding learning point from agent {agent_id}")
            logger.debug(f"Learning category: {category}")

            with self.lock:
                if agent_id not in self.context['agent_learnings']:
                    logger.debug(f"Creating new learning entry for agent {agent_id}")
                    self.context['agent_learnings'][agent_id] = []

                learning_entry = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'category': category,
                    'learning': learning
                }

                self.context['agent_learnings'][agent_id].append(learning_entry)
                self._save_context()
                logger.info(f"Successfully added learning point for agent {agent_id}")

        except Exception as e:
            logger.error(f"Error adding agent learning for {agent_id}: {str(e)}", exc_info=True)
            raise

    def update_shared_knowledge(self, key: str, value: Any, agent_id: str) -> None:
        """Update shared knowledge base."""
        try:
            logger.info(f"Updating shared knowledge key '{key}' by agent {agent_id}")

            with self.lock:
                self.context['shared_knowledge'][key] = {
                    'value': value,
                    'last_updated': datetime.utcnow().isoformat(),
                    'updated_by': agent_id,
                    'version': self.context['shared_knowledge'].get(key, {}).get('version', 0) + 1
                }
                self._save_context()
                logger.info(f"Successfully updated shared knowledge key '{key}' (version: {self.context['shared_knowledge'][key]['version']})")

        except Exception as e:
            logger.error(f"Error updating shared knowledge key '{key}': {str(e)}", exc_info=True)
            raise

    def get_agent_learnings(self, agent_id: Optional[str] = None,
                          category: Optional[str] = None,
                          time_window: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get learnings, optionally filtered by agent, category, or time window."""
        try:
            logger.debug(f"Retrieving learnings - Agent: {agent_id}, Category: {category}, Window: {time_window}")
            learnings = []

            if time_window:
                cutoff = datetime.utcnow() - timedelta(minutes=time_window)

            if agent_id:
                agent_learnings = self.context['agent_learnings'].get(agent_id, [])
                if category:
                    learnings = [l for l in agent_learnings if l['category'] == category]
                else:
                    learnings = agent_learnings
            else:
                for agent_learnings in self.context['agent_learnings'].values():
                    if category:
                        learnings.extend([l for l in agent_learnings if l['category'] == category])
                    else:
                        learnings.extend(agent_learnings)

            if time_window:
                learnings = [
                    l for l in learnings
                    if datetime.fromisoformat(l['timestamp']) >= cutoff
                ]

            logger.info(f"Retrieved {len(learnings)} learning entries")
            return learnings

        except Exception as e:
            logger.error("Error retrieving agent learnings", exc_info=True)
            raise

    def get_shared_knowledge(self, key: Optional[str] = None,
                           include_history: bool = False) -> Dict[str, Any]:
        """Get shared knowledge, optionally filtered by key and including version history."""
        try:
            logger.debug(f"Retrieving shared knowledge for key: {key}")
            if key:
                knowledge = self.context['shared_knowledge'].get(key)
                if knowledge and include_history:
                    # Add version history from MongoDB
                    history = self.memory_store.retrieve_memories(
                        memory_type='shared_knowledge_history',
                        filter={'key': key},
                        limit=10
                    )
                    knowledge['history'] = history
                logger.info(f"Retrieved shared knowledge for key '{key}'")
                return knowledge

            result = self.context['shared_knowledge']
            if include_history:
                # Add version history for all keys
                for key in result:
                    history = self.memory_store.retrieve_memories(
                        memory_type='shared_knowledge_history',
                        filter={'key': key},
                        limit=10
                    )
                    result[key]['history'] = history

            logger.info(f"Retrieved all shared knowledge ({len(result)} entries)")
            return result

        except Exception as e:
            logger.error(f"Error retrieving shared knowledge: {str(e)}", exc_info=True)
            raise

    def add_context(self,
                   task_id: str,
                   content: Dict[str, Any],
                   context_type: str,
                   source_agent: Optional[str] = None,
                   vector_embedding: Optional[np.ndarray] = None) -> None:
        """Add new context for a task."""
        try:
            logger.info(f"Adding {context_type} context for task {task_id}")
            logger.debug(f"Source agent: {source_agent}")

            entry = ContextEntry(
                content=content,
                timestamp=datetime.utcnow(),
                source_agent=source_agent,
                context_type=context_type,
                vector_embedding=vector_embedding
            )

            with self.lock:
                if task_id not in self.context_entries:
                    logger.debug(f"Creating new context entry list for task {task_id}")
                    self.context_entries[task_id] = []

                self.context_entries[task_id].append(entry)
                self._save_context()

                logger.info(f"Successfully added context entry for task {task_id}")
                logger.debug(f"Total context entries for task {task_id}: {len(self.context_entries[task_id])}")

        except Exception as e:
            logger.error(f"Error adding context for task {task_id}: {str(e)}", exc_info=True)
            raise

    def get_context_entries(self,
                          task_id: str,
                          context_type: Optional[str] = None,
                          source_agent: Optional[str] = None,
                          time_window: Optional[int] = None,  # minutes
                          k: Optional[int] = None) -> List[ContextEntry]:
        """Retrieve context entries for a task with optional filtering."""
        try:
            logger.info(f"Retrieving context entries for task {task_id}")
            logger.debug(f"Filters - Type: {context_type}, Agent: {source_agent}, Window: {time_window}, Limit: {k}")

            if task_id not in self.context_entries:
                logger.info(f"No context entries found for task {task_id}")
                return []

            entries = self.context_entries[task_id]
            original_count = len(entries)
            logger.debug(f"Found {original_count} total entries")

            # Apply filters
            if context_type:
                entries = [e for e in entries if e.context_type == context_type]
                logger.debug(f"After type filter: {len(entries)} entries")

            if source_agent:
                entries = [e for e in entries if e.source_agent == source_agent]
                logger.debug(f"After agent filter: {len(entries)} entries")

            if time_window:
                cutoff = datetime.utcnow() - timedelta(minutes=time_window)
                entries = [e for e in entries if e.timestamp >= cutoff]
                logger.debug(f"After time window filter: {len(entries)} entries")

            # Sort by timestamp descending
            entries.sort(key=lambda x: x.timestamp, reverse=True)

            if k:
                entries = entries[:k]
                logger.debug(f"After limit: {len(entries)} entries")

            logger.info(f"Retrieved {len(entries)} context entries (filtered from {original_count})")
            return entries

        except Exception as e:
            logger.error(f"Error retrieving context entries for task {task_id}: {str(e)}", exc_info=True)
            raise

    def get_similar_contexts(self,
                           task_id: str,
                           query_embedding: np.ndarray,
                           k: int = 5,
                           score_threshold: float = 0.7,
                           context_type: Optional[str] = None) -> List[Tuple[ContextEntry, float]]:
        """Find similar contexts using vector similarity."""
        try:
            logger.info(f"Finding similar contexts for task {task_id}")
            logger.debug(f"Parameters - k: {k}, threshold: {score_threshold}, type: {context_type}")

            if task_id not in self.context_entries:
                logger.info(f"No context entries found for task {task_id}")
                return []

            entries = [
                e for e in self.context_entries[task_id]
                if e.vector_embedding is not None and
                (context_type is None or e.context_type == context_type)
            ]
            logger.debug(f"Found {len(entries)} entries with embeddings")

            # Calculate cosine similarities
            similarities = []
            for entry in entries:
                similarity = np.dot(query_embedding, entry.vector_embedding) / \
                            (np.linalg.norm(query_embedding) * np.linalg.norm(entry.vector_embedding))
                entry.relevance_score = float(similarity)
                if similarity >= score_threshold:
                    similarities.append((entry, similarity))
                logger.debug(f"Calculated similarity score: {similarity:.4f}")

            # Sort by similarity
            similarities.sort(key=lambda x: x[1], reverse=True)
            result = similarities[:k]

            logger.info(f"Found {len(result)} similar contexts above threshold {score_threshold}")
            return result

        except Exception as e:
            logger.error(f"Error finding similar contexts for task {task_id}: {str(e)}", exc_info=True)
            raise

    def persist_to_mongo(self) -> None:
        """Persist current context to MongoDB for long-term storage."""
        try:
            logger.info("Persisting context to MongoDB")

            # Store main context
            self.memory_store.store_memory(
                agent_id='system',
                memory_type='shared_context',
                content=self.context
            )

            # Store context entries
            entries_data = {
                task_id: [entry.to_dict() for entry in entries]
                for task_id, entries in self.context_entries.items()
            }
            self.memory_store.store_memory(
                agent_id='system',
                memory_type='context_entries',
                content=entries_data
            )

            logger.info("Successfully persisted context to MongoDB")
            self.last_persist_time = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error persisting context to MongoDB: {str(e)}", exc_info=True)
            raise

    def cleanup_old_entries(self, days: int = 30) -> None:
        """Remove context entries older than specified days."""
        try:
            logger.info(f"Cleaning up context entries older than {days} days")
            cutoff = datetime.utcnow() - timedelta(days=days)

            with self.lock:
                total_removed = 0
                for task_id in list(self.context_entries.keys()):
                    original_count = len(self.context_entries[task_id])
                    self.context_entries[task_id] = [
                        entry for entry in self.context_entries[task_id]
                        if entry.timestamp >= cutoff
                    ]
                    removed = original_count - len(self.context_entries[task_id])
                    if removed > 0:
                        logger.debug(f"Removed {removed} old entries for task {task_id}")
                        total_removed += removed

                    # Remove empty task entries
                    if not self.context_entries[task_id]:
                        del self.context_entries[task_id]
                        logger.debug(f"Removed empty task entry for {task_id}")

                self._save_context()
                logger.info(f"Cleanup complete. Removed {total_removed} old entries")

        except Exception as e:
            logger.error(f"Error cleaning up old entries: {str(e)}", exc_info=True)
            raise
