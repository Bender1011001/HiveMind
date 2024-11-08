from typing import Callable, Dict, List, Optional
import pika
import json
import time
from pika.exceptions import AMQPConnectionError, AMQPChannelError
from .message import Message, MessageType
from ...utils.logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

class MessageBroker:
    """Message broker for handling inter-agent communication using RabbitMQ."""

    def __init__(self, host: str = "localhost", port: int = 5672,
                 username: str = "guest", password: str = "guest",
                 virtual_host: str = "/", heartbeat: int = 600,
                 connection_attempts: int = 3, retry_count: int = 3):
        """Initialize RabbitMQ connection with retry mechanism."""
        self.host = host
        self.port = port
        self.virtual_host = virtual_host
        self.heartbeat = heartbeat
        self.connection_attempts = connection_attempts
        self.retry_count = retry_count

        # Set up credentials
        self.credentials = pika.PlainCredentials(username, password)
        logger.info(f"Initializing RabbitMQ connection to {host}:{port} with virtual host '{virtual_host}'")

        self.connection = None
        self.channel = None
        self._connect_with_retry()

    def _connect_with_retry(self) -> None:
        """Enhanced connection method with retry logic."""
        for attempt in range(self.retry_count):
            try:
                self._connect()
                return
            except AMQPConnectionError as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {str(e)}", exc_info=True)
                if attempt == self.retry_count - 1:
                    logger.critical(f"Failed to connect after {self.retry_count} attempts", exc_info=True)
                    raise ConnectionError(f"Failed to connect after {self.retry_count} retries")
                delay = 2 ** attempt  # Exponential backoff
                logger.info(f"Waiting {delay} seconds before next connection attempt")
                time.sleep(delay)

    def _connect(self) -> None:
        """Establish connection to RabbitMQ."""
        logger.debug(f"Creating connection parameters for RabbitMQ connection")
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

        logger.info("Establishing connection to RabbitMQ")
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

        # Declare exchange for inter-agent communication
        logger.info("Declaring RabbitMQ exchange 'agent_communication'")
        self.channel.exchange_declare(
            exchange='agent_communication',
            exchange_type='topic',
            durable=True
        )

        logger.info("Successfully established RabbitMQ connection and channel")

    def _ensure_connection(self) -> None:
        """Ensure connection is active, reconnect if necessary."""
        try:
            if not self.connection or self.connection.is_closed:
                logger.warning("Connection closed, attempting to reconnect")
                self._connect_with_retry()
            if not self.channel or self.channel.is_closed:
                logger.warning("Channel closed, creating new channel")
                self.channel = self.connection.channel()
        except Exception as e:
            logger.error(f"Failed to ensure connection: {str(e)}", exc_info=True)
            raise

    def send_message_with_confirmation(self, message: Message) -> bool:
        """Send a message with delivery confirmation."""
        try:
            if not isinstance(message, Message):
                logger.error("Invalid message type provided")
                raise ValueError("message must be an instance of Message")
            self._ensure_connection()

            routing_key = f"agent.{message.receiver_id}"
            properties = pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/json',
                message_id=str(time.time()),
                timestamp=int(time.time())
            )

            # Enable publisher confirms
            self.channel.confirm_delivery()

            logger.info(f"Sending message {message.message_id} to {message.receiver_id} with confirmation")
            self.channel.basic_publish(
                exchange='agent_communication',
                routing_key=routing_key,
                body=json.dumps(message.to_dict()),
                properties=properties,
                mandatory=True  # Ensure message is routable
            )

            logger.info(f"Message {message.message_id} confirmed delivered to {message.receiver_id}")
            return True

        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"RabbitMQ error while sending message {message.message_id}: {str(e)}", exc_info=True)
            try:
                self._connect_with_retry()  # Try to reconnect
            except Exception as reconnect_error:
                logger.error(f"Failed to reconnect: {str(reconnect_error)}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Error sending message {message.message_id}: {str(e)}", exc_info=True)
            return False

    def send_message(self, message: Message) -> bool:
        """Send a message to a specific agent with retry mechanism."""
        try:
            if not isinstance(message, Message):
                logger.error("Invalid message type provided")
                raise ValueError("message must be an instance of Message")
            self._ensure_connection()

            routing_key = f"agent.{message.receiver_id}"
            properties = pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/json',
                message_id=str(time.time()),
                timestamp=int(time.time())
            )

            logger.info(f"Sending message {message.message_id} to {message.receiver_id}")
            self.channel.basic_publish(
                exchange='agent_communication',
                routing_key=routing_key,
                body=json.dumps(message.to_dict()),
                properties=properties
            )

            logger.info(f"Message {message.message_id} sent successfully to {message.receiver_id}")
            return True

        except (AMQPConnectionError, AMQPChannelError) as e:
            logger.error(f"RabbitMQ error while sending message {message.message_id}: {str(e)}", exc_info=True)
            try:
                self._connect_with_retry()  # Try to reconnect
            except Exception as reconnect_error:
                logger.error(f"Failed to reconnect: {str(reconnect_error)}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Error sending message {message.message_id}: {str(e)}", exc_info=True)
            return False

    def subscribe(self, agent_id: str, callback: Callable[[Message], None]):
        """Subscribe to messages for a specific agent with error handling."""
        if not isinstance(agent_id, str) or not agent_id.strip():
            logger.error("Invalid agent_id provided")
            raise ValueError("agent_id must be a non-empty string")
        if not callable(callback):
            logger.error("Invalid callback provided")
            raise ValueError("callback must be a callable")

        try:
            self._ensure_connection()
            queue_name = f"agent_{agent_id}_queue"

            # Declare queue for the agent
            logger.info(f"Declaring queue '{queue_name}' for agent {agent_id}")
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
            logger.info(f"Binding queue '{queue_name}' to exchange with routing key '{routing_key}'")
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
                    logger.info(f"Received message {message.message_id} for agent {agent_id}")
                    callback(message)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.debug(f"Successfully processed message {message.message_id}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {str(e)}", exc_info=True)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}", exc_info=True)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            # Set up consumer with QoS
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=message_handler
            )

            logger.info(f"Successfully subscribed to messages for agent {agent_id}")

        except Exception as e:
            logger.error(f"Error setting up subscription for agent {agent_id}: {str(e)}", exc_info=True)
            raise

    def start_consuming(self):
        """Start consuming messages with reconnection handling."""
        while True:
            try:
                self._ensure_connection()
                logger.info("Starting to consume messages")
                self.channel.start_consuming()
            except (AMQPConnectionError, AMQPChannelError) as e:
                logger.error(f"Connection error while consuming: {str(e)}", exc_info=True)
                logger.info("Waiting 5 seconds before reconnecting")
                time.sleep(5)  # Wait before reconnecting
            except Exception as e:
                logger.error(f"Unexpected error while consuming: {str(e)}", exc_info=True)
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
            logger.info("Successfully closed RabbitMQ connection and channel")
        except Exception as e:
            logger.error(f"Error closing connection: {str(e)}", exc_info=True)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
