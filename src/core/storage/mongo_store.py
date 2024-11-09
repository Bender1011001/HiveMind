from typing import Dict, List, Optional, Any, Tuple
from pymongo import MongoClient, DESCENDING, IndexModel, UpdateOne
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
from datetime import datetime, timedelta
import time
from src.utils.cache import Cache
from ...utils.logging_setup import setup_logging

# Rest of the file remains unchanged
# Set up centralized logging
logger = setup_logging(__name__)

class MongoMemoryStore:
    """Centralized memory store using MongoDB for multi-agent collaboration."""

    def __init__(self, connection_string: str = "mongodb://localhost:27017/",
                 max_retries: int = 3, retry_delay: int = 1):
        """Initialize MongoDB connection and set up indexes."""
        try:
            # Mask credentials in connection string for logging
            safe_conn_string = self._mask_connection_string(connection_string)
            logger.info(f"Initializing MongoDB connection to {safe_conn_string}")

            self.max_retries = max_retries
            self.retry_delay = retry_delay
            self.client = MongoClient(
                connection_string,
                maxPoolSize=100,  # Increased pool size for better concurrency
                minPoolSize=10,   # Maintain minimum connections
                maxIdleTimeMS=45000,  # Close idle connections after 45 seconds
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                retryWrites=True,  # Enable automatic retry of write operations
                w='majority'  # Ensure writes are acknowledged by majority of replicas
            )

            # Test the connection
            logger.info("Testing MongoDB connection with ping command")
            self.client.admin.command('ping')
            logger.info("MongoDB ping successful, connection established")

            self.db = self.client.langchain_multi_agent
            self.memory_collection = self.db.shared_memory
            self.context_collection = self.db.context
            self.metrics_collection = self.db.metrics  # New collection for storing metrics
            logger.debug(f"Using database: {self.db.name}")

            # Initialize cache with monitoring
            self.cache = Cache()
            self.cache_hits = 0
            self.cache_misses = 0
            logger.debug("Cache system initialized")

            # Create indexes for better query performance
            logger.info("Setting up MongoDB indexes for collections")
            self._setup_indexes()
            self.is_connected = True

            # Start periodic metrics collection
            self._start_metrics_collection()

            logger.info("MongoDB initialization completed successfully")

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            self.is_connected = False
            logger.error(f"Failed to connect to MongoDB: {str(e)}", exc_info=True)
            logger.error(f"Connection details: {safe_conn_string}")
            raise ConnectionError(f"Failed to connect to MongoDB: {str(e)}")

    def _mask_connection_string(self, conn_string: str) -> str:
        """Mask sensitive information in connection string for logging."""
        try:
            if '@' in conn_string:
                prefix, rest = conn_string.split('@')
                return f"mongodb://*****@{rest}"
            return conn_string
        except Exception as e:
            logger.error(f"Error masking connection string: {str(e)}", exc_info=True)
            return "mongodb://[masked]"

    def _setup_indexes(self):
        """Set up necessary indexes for better query performance."""
        try:
            # Compound indexes for memory_collection
            memory_indexes = [
                IndexModel([("agent_id", DESCENDING), ("memory_type", DESCENDING)]),
                IndexModel([("agent_id", DESCENDING), ("timestamp", DESCENDING)]),
                IndexModel([("memory_type", DESCENDING), ("timestamp", DESCENDING)]),
                IndexModel([("accessed_count", DESCENDING), ("timestamp", DESCENDING)]),
                IndexModel([("timestamp", DESCENDING)])  # For TTL cleanup
            ]
            self.memory_collection.create_indexes(memory_indexes)
            logger.info("Created indexes for memory collection")

            # Compound indexes for context_collection
            context_indexes = [
                IndexModel([("task_id", DESCENDING)], unique=True),
                IndexModel([("last_updated", DESCENDING), ("task_id", DESCENDING)]),
                IndexModel([("timestamp", DESCENDING)])  # For TTL cleanup
            ]
            self.context_collection.create_indexes(context_indexes)
            logger.info("Created indexes for context collection")

            # Indexes for metrics collection
            metrics_indexes = [
                IndexModel([("timestamp", DESCENDING)]),
                IndexModel([("metric_type", DESCENDING), ("timestamp", DESCENDING)])
            ]
            self.metrics_collection.create_indexes(metrics_indexes)
            logger.info("Created indexes for metrics collection")

            logger.debug("Index creation details - Memory Collection Indexes: 5, Context Collection Indexes: 3, Metrics Collection Indexes: 2")

        except OperationFailure as e:
            self.is_connected = False
            logger.error(f"Failed to create MongoDB indexes: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to create indexes: {str(e)}")

    def _collect_metrics(self):
        """Collect and store system metrics."""
        try:
            metrics = {
                "timestamp": datetime.utcnow(),
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_hit_ratio": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
                "memory_count": self.memory_collection.count_documents({}),
                "context_count": self.context_collection.count_documents({}),
                "db_stats": self.db.command("dbStats")
            }

            self.metrics_collection.insert_one(metrics)
            logger.debug("Collected and stored system metrics")

        except Exception as e:
            logger.error(f"Error collecting metrics: {str(e)}", exc_info=True)

    def _start_metrics_collection(self):
        """Start periodic metrics collection."""
        try:
            self._collect_metrics()  # Initial collection
            logger.info("Started metrics collection")
        except Exception as e:
            logger.error(f"Error starting metrics collection: {str(e)}", exc_info=True)

    def _retry_operation(self, operation, *args, **kwargs) -> Any:
        """Retry an operation with exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(f"Operation failed, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})")
                time.sleep(wait_time)

    def store_memory(self, agent_id: str, memory_type: str, content: Dict) -> str:
        """Store a memory entry with retry mechanism."""
        if not self.is_connected:
            logger.error("Attempted to store memory while disconnected from MongoDB")
            raise ConnectionError("Not connected to MongoDB")

        try:
            self._validate_store_params(agent_id, memory_type, content)
            logger.debug(f"Storing memory for agent {agent_id} of type {memory_type}")

            document = {
                "agent_id": agent_id.strip(),
                "memory_type": memory_type.strip(),
                "content": content,
                "timestamp": datetime.utcnow(),
                "accessed_count": 0
            }

            result = self._retry_operation(
                self.memory_collection.insert_one,
                document
            )

            # Invalidate related cache entries
            cache_key = self._generate_cache_key(agent_id, memory_type)
            self.cache.invalidate(cache_key)
            logger.debug(f"Invalidated cache for key: {cache_key}")

            logger.info(f"Successfully stored memory for agent {agent_id} with ID {result.inserted_id}")
            return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Failed to store memory for agent {agent_id}: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to store memory: {str(e)}")

    def retrieve_memories(self,
                        agent_id: Optional[str] = None,
                        memory_type: Optional[str] = None,
                        limit: int = 10,
                        min_accessed: Optional[int] = None,
                        max_age: Optional[int] = None) -> List[Dict]:
        """Retrieve memories based on filters with enhanced query options."""
        if not self.is_connected:
            logger.error("Attempted to retrieve memories while disconnected from MongoDB")
            raise ConnectionError("Not connected to MongoDB")

        try:
            if limit < 1:
                logger.error(f"Invalid limit provided: {limit}")
                raise ValueError("limit must be a positive integer")

            # Generate cache key
            cache_key = self._generate_cache_key(agent_id, memory_type, limit, min_accessed, max_age)
            logger.debug(f"Checking cache for key: {cache_key}")

            # Check cache first
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                logger.debug("Retrieved memories from cache")
                self.cache_hits += 1
                return cached_result

            self.cache_misses += 1

            # Build query
            query = {}
            if agent_id:
                if not isinstance(agent_id, str) or not agent_id.strip():
                    logger.error("Invalid agent_id provided for memory retrieval")
                    raise ValueError("agent_id must be a non-empty string")
                query["agent_id"] = agent_id.strip()

            if memory_type:
                if not isinstance(memory_type, str) or not memory_type.strip():
                    logger.error("Invalid memory_type provided for memory retrieval")
                    raise ValueError("memory_type must be a non-empty string")
                query["memory_type"] = memory_type.strip()

            if min_accessed is not None:
                query["accessed_count"] = {"$gte": min_accessed}

            if max_age is not None:
                cutoff = datetime.utcnow() - timedelta(hours=max_age)
                query["timestamp"] = {"$gte": cutoff}

            # Use hint to force index usage for common queries
            hint = None
            if agent_id and memory_type:
                hint = [("agent_id", DESCENDING), ("memory_type", DESCENDING)]
            elif agent_id:
                hint = [("agent_id", DESCENDING), ("timestamp", DESCENDING)]
            elif memory_type:
                hint = [("memory_type", DESCENDING), ("timestamp", DESCENDING)]

            logger.debug(f"Executing memory query with filters: {query}")
            cursor = self.memory_collection.find(
                query,
                {"_id": 0}  # Exclude MongoDB ID from results
            ).sort("timestamp", -1).limit(limit)

            if hint:
                cursor = cursor.hint(hint)
                logger.debug(f"Using index hint: {hint}")

            memories = list(cursor)
            logger.info(f"Retrieved {len(memories)} memories")

            # Update access count in bulk
            if memories:
                bulk_updates = [
                    UpdateOne(
                        {"_id": m["_id"]},
                        {"$inc": {"accessed_count": 1}}
                    ) for m in memories
                ]
                self.memory_collection.bulk_write(bulk_updates)
                logger.debug(f"Updated access counts for {len(memories)} memories")

            # Cache the results
            self.cache.set(cache_key, memories, ttl_minutes=5)  # Cache for 5 minutes
            logger.debug(f"Cached query results with key: {cache_key}")

            return memories

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to retrieve memories: {str(e)}")

    def cleanup_old_data(self, days: int = 30) -> Tuple[int, int]:
        """Clean up old data from collections."""
        try:
            logger.info(f"Starting cleanup of data older than {days} days")
            cutoff = datetime.utcnow() - timedelta(days=days)

            # Clean up old memories
            memory_result = self.memory_collection.delete_many({
                "timestamp": {"$lt": cutoff}
            })
            memory_count = memory_result.deleted_count
            logger.info(f"Deleted {memory_count} old memories")

            # Clean up old contexts
            context_result = self.context_collection.delete_many({
                "timestamp": {"$lt": cutoff}
            })
            context_count = context_result.deleted_count
            logger.info(f"Deleted {context_count} old contexts")

            # Clean up old metrics
            metrics_result = self.metrics_collection.delete_many({
                "timestamp": {"$lt": cutoff}
            })
            logger.info(f"Deleted {metrics_result.deleted_count} old metrics")

            return memory_count, context_count

        except Exception as e:
            logger.error(f"Error during data cleanup: {str(e)}", exc_info=True)
            raise

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            logger.debug("Collecting storage statistics")
            stats = {
                "memory_count": self.memory_collection.count_documents({}),
                "context_count": self.context_collection.count_documents({}),
                "cache_stats": {
                    "hits": self.cache_hits,
                    "misses": self.cache_misses,
                    "hit_ratio": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0
                },
                "db_stats": self.db.command("dbStats"),
                "timestamp": datetime.utcnow().isoformat()
            }
            logger.info("Successfully collected storage statistics")
            return stats
        except Exception as e:
            logger.error(f"Error getting storage stats: {str(e)}", exc_info=True)
            raise

    def close(self):
        """Close the MongoDB connection and perform cleanup."""
        if hasattr(self, 'client'):
            try:
                logger.info("Performing final metrics collection before shutdown")
                self._collect_metrics()

                logger.info("Closing MongoDB connection")
                self.client.close()
                self.is_connected = False

                logger.info("Cleaning up cache")
                self.cache.cleanup_expired()

                logger.info("MongoDB connection and cleanup completed successfully")

            except Exception as e:
                logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
                raise
