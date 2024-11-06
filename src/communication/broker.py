from typing import Callable, Dict, List, Optional
import pika
import json
import logging
import time
from pika.exceptions import AMQPConnectionError, AMQPChannelError
from .message import Message, MessageType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageBroker:
    """Message broker for handling inter-agent communication using RabbitMQ."""
    
    def __init__(self, host: str = "localhost", port: int = 5672, 
                 username: str = "guest", password: str = "guest",
                 virtual_host: str = "/", heartbeat: int = 600,
                 connection_attempts: int = 3):
        """Initialize RabbitMQ connection with retry mechanism."""
        self.host = host
        self.port = port
        self.virtual_host = virtual_host
        self.heartbeat = heartbeat
        self.connection_attempts = connection_attempts
        
        # Set up credentials
        self.credentials = pika.PlainCredentials(username, password)
        logger.info(f"Initializing RabbitMQ connection to {host}:{port}")
        
        self.connection = None
        self.channel = None
        self._connect()
        
    def _connect(self) -> None:
        """Establish connection to RabbitMQ with retry mechanism."""
        for attempt in range(self.connection_attempts):
            try:
                logger.info(f"Attempting to connect to RabbitMQ (attempt {attempt + 1}/{self.connection_attempts})")
                parameters = pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    virtual_host=self.virtual_host,
                    credentials=self.credentials,
                    heartbeat=self.heartbeat,
                    connection_attempts=3,
                    retry_delay=2,
                    socket_timeout=5
                )
                
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                
                # Declare exchange for inter-agent communication
                logger.info("Declaring RabbitMQ exchange")
                self.channel.exchange_declare(
                    exchange='agent_communication',
                    exchange_type='topic',
                    durable=True
                )
                
                logger.info("Successfully connected to RabbitMQ")
                return
                
            except AMQPConnectionError as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.connection_attempts - 1:
                    delay = 2 ** attempt
                    logger.info(f"Waiting {delay} seconds before next attempt")
                    time.sleep(delay)  # Exponential backoff
                else:
                    logger.error("Failed all connection attempts")
                    raise ConnectionError(f"Failed to connect to RabbitMQ after {self.connection_attempts} attempts: {str(e)}")
                    
    def _ensure_connection(self) -> None:
        """Ensure connection is active, reconnect if necessary."""
        try:
            if not self.connection or self.connection.is_closed:
                logger.info("Connection closed, attempting to reconnect")
                self._connect()
            if not self.channel or self.channel.is_closed:
                logger.info("Channel closed, creating new channel")
                self.channel = self.connection.channel()
        except Exception as e:
            logger.error(f"Failed to ensure connection: {str(e)}")
            raise
            
    def send_message(self, message: Message) -> bool:
        """Send a message to a specific agent with retry mechanism."""
        try:
            if not isinstance(message, Message):
                raise ValueError("message must be an instance of Message")
            self._ensure_connection()
            
            routing_key = f"agent.{message.receiver_id}"
            properties = pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/json',
                message_id=str(time.time()),
                timestamp=int(time.time())
            )
            
            logger.info(f"Sending message to {message.receiver_id}")
            self.channel.basic_publish(
                exchange='agent_communication',
                routing_key=routing_key,
                body=json.dumps(message.to_dict()),
                properties=properties
            )
            
            logger.info(f"Message sent successfully to {message.receiver_id}")
            return True
            
        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"RabbitMQ error while sending message: {str(e)}")
            try:
                self._connect()  # Try to reconnect
            except Exception as reconnect_error:
                logger.error(f"Failed to reconnect: {str(reconnect_error)}")
            return False
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return False
            
    def subscribe(self, agent_id: str, callback: Callable[[Message], None]):
        """Subscribe to messages for a specific agent with error handling."""
        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("agent_id must be a non-empty string")
        if not callable(callback):
            raise ValueError("callback must be a callable")
            
        try:
            self._ensure_connection()
            queue_name = f"agent_{agent_id}_queue"
            
            # Declare queue for the agent
            logger.info(f"Declaring queue for agent {agent_id}")
            self.channel.queue_declare(
                queue=queue_name,
                durable=True,
                arguments={
                    'x-message-ttl': 86400000,  # 24 hours in milliseconds
                    'x-max-length': 10000  # Maximum number of messages
                }
            )
            
            # Bind queue to exchange with agent-specific routing key
            routing_key = f"agent.{agent_id}"
            logger.info(f"Binding queue to exchange with routing key {routing_key}")
            self.channel.queue_bind(
                exchange='agent_communication',
                queue=queue_name,
                routing_key=routing_key
            )
            
            def message_handler(ch, method, properties, body):
                """Handle incoming messages with error handling."""
                try:
                    message_dict = json.loads(body)
                    message = Message.from_dict(message_dict)
                    logger.info(f"Received message for agent {agent_id}")
                    callback(message)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {str(e)}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
            # Set up consumer with QoS
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=message_handler
            )
            
            logger.info(f"Successfully subscribed to messages for agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Error setting up subscription: {str(e)}")
            raise
            
    def start_consuming(self):
        """Start consuming messages with reconnection handling."""
        while True:
            try:
                self._ensure_connection()
                logger.info("Starting to consume messages")
                self.channel.start_consuming()
            except (AMQPConnectionError, AMQPChannelError) as e:
                logger.error(f"Connection error while consuming: {str(e)}")
                logger.info("Waiting 5 seconds before reconnecting")
                time.sleep(5)  # Wait before reconnecting
            except Exception as e:
                logger.error(f"Unexpected error while consuming: {str(e)}")
                break
                
    def close(self):
        """Clean up resources."""
        try:
            if self.channel and not self.channel.is_closed:
                logger.info("Closing RabbitMQ channel")
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                logger.info("Closing RabbitMQ connection")
                self.connection.close()
            logger.info("Successfully closed RabbitMQ connection")
        except Exception as e:
            logger.error(f"Error closing connection: {str(e)}")
            
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
