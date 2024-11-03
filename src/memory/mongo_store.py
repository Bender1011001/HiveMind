from typing import Dict, List, Optional
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure
from datetime import datetime

class MongoMemoryStore:
    """Centralized memory store using MongoDB for multi-agent collaboration."""
    
    def __init__(self, connection_string: str = "mongodb://localhost:27017/"):
        """Initialize MongoDB connection and set up indexes."""
        try:
            self.client = MongoClient(connection_string)
            # Test the connection
            self.client.admin.command('ping')
            
            self.db = self.client.langchain_multi_agent
            self.memory_collection = self.db.shared_memory
            self.context_collection = self.db.context
            
            # Create indexes for better query performance
            self._setup_indexes()
        except ConnectionFailure as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {e}")
            
    def _setup_indexes(self):
        """Set up necessary indexes for better query performance."""
        try:
            # Indexes for memory_collection
            self.memory_collection.create_index([("agent_id", DESCENDING)])
            self.memory_collection.create_index([("memory_type", DESCENDING)])
            self.memory_collection.create_index([("timestamp", DESCENDING)])
            
            # Indexes for context_collection
            self.context_collection.create_index([("task_id", DESCENDING)], unique=True)
            self.context_collection.create_index([("last_updated", DESCENDING)])
        except OperationFailure as e:
            raise RuntimeError(f"Failed to create indexes: {e}")
            
    def _validate_store_params(self, agent_id: str, memory_type: str, content: Dict):
        """Validate parameters for store_memory method."""
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("agent_id must be a non-empty string")
        if not isinstance(memory_type, str) or not memory_type.strip():
            raise ValueError("memory_type must be a non-empty string")
        if not isinstance(content, dict):
            raise ValueError("content must be a dictionary")
            
    def store_memory(self, agent_id: str, memory_type: str, content: Dict) -> str:
        """Store a memory entry."""
        try:
            self._validate_store_params(agent_id, memory_type, content)
            
            document = {
                "agent_id": agent_id.strip(),
                "memory_type": memory_type.strip(),
                "content": content,
                "timestamp": datetime.utcnow(),
                "accessed_count": 0
            }
            result = self.memory_collection.insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            raise RuntimeError(f"Failed to store memory: {e}")
        
    def retrieve_memories(self, 
                        agent_id: Optional[str] = None, 
                        memory_type: Optional[str] = None, 
                        limit: int = 10) -> List[Dict]:
        """Retrieve memories based on filters."""
        try:
            if limit < 1:
                raise ValueError("limit must be a positive integer")
                
            query = {}
            if agent_id:
                if not isinstance(agent_id, str) or not agent_id.strip():
                    raise ValueError("agent_id must be a non-empty string")
                query["agent_id"] = agent_id.strip()
            if memory_type:
                if not isinstance(memory_type, str) or not memory_type.strip():
                    raise ValueError("memory_type must be a non-empty string")
                query["memory_type"] = memory_type.strip()
                
            memories = list(self.memory_collection.find(
                query,
                {"_id": 0}  # Exclude MongoDB ID from results
            ).sort("timestamp", -1).limit(limit))
            
            # Update access count
            if memories:
                self.memory_collection.update_many(
                    {"_id": {"$in": [m["_id"] for m in memories]}},
                    {"$inc": {"accessed_count": 1}}
                )
            
            return memories
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve memories: {e}")
        
    def store_context(self, task_id: str, context: Dict) -> str:
        """Store shared context for a task."""
        try:
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("task_id must be a non-empty string")
            if not isinstance(context, dict):
                raise ValueError("context must be a dictionary")
                
            document = {
                "task_id": task_id.strip(),
                "context": context,
                "timestamp": datetime.utcnow(),
                "last_updated": datetime.utcnow()
            }
            result = self.context_collection.insert_one(document)
            return str(result.inserted_id)
        except Exception as e:
            raise RuntimeError(f"Failed to store context: {e}")
        
    def update_context(self, task_id: str, context_update: Dict) -> bool:
        """Update existing context for a task."""
        try:
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("task_id must be a non-empty string")
            if not isinstance(context_update, dict):
                raise ValueError("context_update must be a dictionary")
                
            result = self.context_collection.update_one(
                {"task_id": task_id.strip()},
                {
                    "$set": {
                        "context": context_update,
                        "last_updated": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            raise RuntimeError(f"Failed to update context: {e}")
        
    def get_context(self, task_id: str) -> Optional[Dict]:
        """Retrieve context for a specific task."""
        try:
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("task_id must be a non-empty string")
                
            result = self.context_collection.find_one(
                {"task_id": task_id.strip()},
                {"_id": 0}  # Exclude MongoDB ID from results
            )
            return result["context"] if result else None
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve context: {e}")
            
    def close(self):
        """Close the MongoDB connection."""
        if hasattr(self, 'client'):
            self.client.close()
            
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
