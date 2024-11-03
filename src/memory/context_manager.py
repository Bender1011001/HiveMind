"""Enhanced SharedContext with task dependencies and progress tracking."""

import os
import json
from typing import Dict, Optional, List, Any
from datetime import datetime
import logging
from threading import Lock
from .mongo_store import MongoMemoryStore
from ..settings import settings

logger = logging.getLogger(__name__)

class SharedContext:
    """Manages shared context, task dependencies, and persistent learning between agents."""

    def __init__(self, memory_store: MongoMemoryStore):
        """Initialize shared context manager."""
        self.memory_store = memory_store
        self.lock = Lock()
        self.context_file = os.path.join(settings.shared_data_dir, 'shared_context.json')
        self._load_context()

    def _load_context(self):
        """Load shared context from file."""
        try:
            if os.path.exists(self.context_file):
                with open(self.context_file, 'r') as f:
                    self.context = json.load(f)
            else:
                self.context = {
                    'tasks': {},  # task_id -> task details
                    'agent_learnings': {},
                    'shared_knowledge': {},
                    'last_updated': datetime.utcnow().isoformat()
                }
                self._save_context()
        except Exception as e:
            logger.error(f"Error loading context: {e}")
            raise

    def _save_context(self):
        """Save shared context to file."""
        try:
            self.context['last_updated'] = datetime.utcnow().isoformat()
            with open(self.context_file, 'w') as f:
                json.dump(self.context, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving context: {e}")
            raise

    def update_task(self, task_id: str, agent_id: Optional[str], updates: Dict[str, Any]) -> None:
        """Update task details and progress."""
        try:
            with self.lock:
                if task_id not in self.context['tasks']:
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
                    task['status'] = updates['status']
                if 'progress_update' in updates:
                    progress_entry = {
                        'timestamp': datetime.utcnow().isoformat(),
                        'agent_id': agent_id,
                        'update': updates['progress_update']
                    }
                    task['progress'].append(progress_entry)
                self._save_context()
        except Exception as e:
            logger.error(f"Error updating task: {e}")
            raise

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task details."""
        return self.context['tasks'].get(task_id)

    def add_agent_learning(self, agent_id: str, learning: Dict[str, Any],
                           category: Optional[str] = None) -> None:
        """Add a learning point from an agent that others might benefit from."""
        try:
            with self.lock:
                if agent_id not in self.context['agent_learnings']:
                    self.context['agent_learnings'][agent_id] = []

                learning_entry = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'category': category,
                    'learning': learning
                }

                self.context['agent_learnings'][agent_id].append(learning_entry)
                self._save_context()

        except Exception as e:
            logger.error(f"Error adding agent learning: {e}")
            raise

    def update_shared_knowledge(self, key: str, value: Any,
                                agent_id: str) -> None:
        """Update shared knowledge base."""
        try:
            with self.lock:
                self.context['shared_knowledge'][key] = {
                    'value': value,
                    'last_updated': datetime.utcnow().isoformat(),
                    'updated_by': agent_id
                }
                self._save_context()

        except Exception as e:
            logger.error(f"Error updating shared knowledge: {e}")
            raise

    def get_agent_learnings(self, agent_id: Optional[str] = None,
                            category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get learnings, optionally filtered by agent or category."""
        learnings = []

        if agent_id:
            agent_learnings = self.context['agent_learnings'].get(agent_id, [])
            if category:
                return [l for l in agent_learnings if l['category'] == category]
            return agent_learnings

        for agent_learnings in self.context['agent_learnings'].values():
            if category:
                learnings.extend([l for l in agent_learnings if l['category'] == category])
            else:
                learnings.extend(agent_learnings)

        return learnings

    def get_shared_knowledge(self, key: Optional[str] = None) -> Dict[str, Any]:
        """Get shared knowledge, optionally filtered by key."""
        if key:
            return self.context['shared_knowledge'].get(key)
        return self.context['shared_knowledge']

    def persist_to_mongo(self) -> None:
        """Persist current context to MongoDB for long-term storage."""
        try:
            self.memory_store.store_memory(
                agent_id='system',
                memory_type='shared_context',
                content=self.context
            )
        except Exception as e:
            logger.error(f"Error persisting context to MongoDB: {e}")
            raise
