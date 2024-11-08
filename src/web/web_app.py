"""Flask application for serving the HiveMind web interface."""

from flask import Flask, render_template, jsonify, request, send_from_directory, Response, url_for, copy_current_request_context
from pathlib import Path
import sys
import json
import logging
import queue
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
import urllib.parse
import mimetypes

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.event_bus import EventBus
from src.communication.broker import MessageBroker
from src.memory.mongo_store import MongoMemoryStore
from src.settings.settings import settings
from src.communication.message import Message, MessageType
from src.roles.master_agent import MasterAgent
from src.roles.role_manager import RoleManager
from src.roles.capability import CapabilityRegister

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app with correct static folder
web_dir = Path(__file__).parent
static_dir = web_dir / 'static'
template_dir = web_dir / 'templates'

app = Flask(
    __name__,
    static_folder=str(static_dir),
    template_folder=str(template_dir)
)

# Enable debug mode
app.debug = True

# Ensure proper MIME types for JavaScript modules
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

event_bus = EventBus()

# Message queues for SSE
message_queues = {}

def initialize_components() -> tuple[Optional[MongoMemoryStore], Optional[MessageBroker], Optional[MasterAgent]]:
    """Initialize core components with proper error handling."""
    memory_store = None
    message_broker = None
    master_agent = None
    
    try:
        memory_store = MongoMemoryStore()
        logger.info("Successfully initialized MongoDB connection")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {str(e)}\n{traceback.format_exc()}")
        
    try:
        message_broker = MessageBroker()
        logger.info("Successfully initialized RabbitMQ connection")
        
        # Initialize role management components
        capability_register = CapabilityRegister()
        role_manager = RoleManager(capability_register)
        
        # Initialize master agent
        master_agent = MasterAgent(role_manager, capability_register, memory_store, message_broker)
        logger.info("Successfully initialized Master Agent")
        
    except Exception as e:
        logger.error(f"Failed to initialize RabbitMQ or Master Agent: {str(e)}\n{traceback.format_exc()}")
        
    return memory_store, message_broker, master_agent

# Initialize core components
memory_store, message_broker, master_agent = initialize_components()

@app.route('/')
def index():
    """Render the main chat interface."""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/favicon.ico')
def favicon():
    """Serve the favicon."""
    try:
        return send_from_directory(
            app.static_folder,
            'images/lost dog.jpg',
            mimetype='image/jpeg'
        )
    except Exception as e:
        logger.error(f"Error serving favicon: {str(e)}")
        return "", 404

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files with proper MIME types."""
    try:
        # Decode URL-encoded filename
        decoded_filename = urllib.parse.unquote(filename)
        logger.debug(f"Serving static file: {decoded_filename}")
        
        # Get the correct MIME type
        mime_type = None
        if decoded_filename.endswith('.js'):
            mime_type = 'application/javascript'
        elif decoded_filename.endswith('.css'):
            mime_type = 'text/css'
                
        response = send_from_directory(
            app.static_folder,
            decoded_filename,
            mimetype=mime_type
        )
        
        # Add CORS headers for JavaScript modules
        if mime_type == 'application/javascript':
            response.headers['Access-Control-Allow-Origin'] = '*'
                
        return response
    except Exception as e:
        logger.error(f"Error serving static file {filename}: {str(e)}")
        return jsonify({"error": str(e)}), 404

@app.route('/api/stream')
def stream():
    """SSE endpoint for real-time updates."""
    # Get client ID from request headers before entering the generator
    client_id = request.headers.get('X-Client-ID', str(datetime.utcnow().timestamp()))
    client_queue = queue.Queue(maxsize=100)  # Limit queue size
    message_queues[client_id] = client_queue
    
    logger.info(f"New client connected: {client_id}")
    
    def generate():
        try:
            # Send initial connection success message
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            
            while True:
                try:
                    # Wait for messages with timeout
                    message = client_queue.get(timeout=30)
                    if message is None:  # Shutdown signal
                        break
                        
                    # Send message event
                    yield f"data: {json.dumps(message)}\n\n"
                    
                except queue.Empty:
                    # Send keep-alive ping
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    
        except GeneratorExit:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error in SSE stream: {str(e)}\n{traceback.format_exc()}")
        finally:
            # Clean up client queue
            message_queues.pop(client_id, None)
            logger.info(f"Cleaned up client {client_id}")

    try:
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'  # Disable proxy buffering
            }
        )
    except Exception as e:
        logger.error(f"Error setting up SSE stream: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/messages')
def get_messages():
    """Get all messages from the memory store with proper error handling."""
    try:
        if not memory_store or not memory_store.is_connected:
            return jsonify({"error": "Message storage is not available"}), 503
            
        stored_messages = memory_store.retrieve_memories(
            memory_type="chat",
            limit=100  # Adjust limit as needed
        )
        
        formatted_messages = [{
            'id': str(msg.get('_id', '')),
            'type': msg.get('content', {}).get('type', 'text'),
            'content': msg.get('content', {}).get('text', ''),
            'timestamp': msg.get('timestamp', datetime.now()).isoformat(),
            'thoughts': msg.get('content', {}).get('thoughts')
        } for msg in stored_messages]
        
        return jsonify(formatted_messages)
        
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/send_message', methods=['POST'])
def send_message():
    """Send a new message with proper error handling and broker integration."""
    try:
        data = request.json
        if not data or 'content' not in data:
            return jsonify({"error": "No message content provided"}), 400
            
        # Validate message store connection
        if not memory_store or not memory_store.is_connected:
            return jsonify({"error": "Message storage is not available"}), 503
            
        # Create and store user message
        user_message_content = {
            'type': 'user',
            'text': data['content'],
            'timestamp': datetime.utcnow()
        }
        
        try:
            memory_store.store_memory(
                agent_id="web_ui",
                memory_type="chat",
                content=user_message_content
            )
            
            # Broadcast message to connected clients
            broadcast_message({
                'type': 'user',
                'content': data['content'],
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to store user message: {str(e)}\n{traceback.format_exc()}")
            return jsonify({"error": str(e)}), 500
            
        # Send message through broker if available
        if message_broker and master_agent:
            try:
                msg = Message(
                    sender_id="web_ui",
                    receiver_id="master_agent",
                    message_type=MessageType.TEXT,
                    content={"text": data['content']},
                    task_id="chat_message"
                )
                
                success = message_broker.send_message(msg)
                if not success:
                    logger.error("Failed to send message through broker")
                    return jsonify({"error": "Failed to process message"}), 500
                    
                return jsonify({"success": True, "message": "Message sent successfully"})
                
            except Exception as e:
                logger.error(f"Error sending message through broker: {str(e)}\n{traceback.format_exc()}")
                return jsonify({"error": str(e)}), 500
        else:
            logger.warning("Message processing system is offline")
            return jsonify({"error": "Message processing system is offline"}), 503
            
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/status')
def get_status():
    """Get detailed system status."""
    try:
        status = {
            "mongodb_connected": bool(memory_store and memory_store.is_connected),
            "rabbitmq_connected": bool(message_broker and hasattr(message_broker, 'connection') and 
                                     not message_broker.connection.is_closed),
            "master_agent_ready": bool(master_agent),
            "model_name": settings.model_name,
            "timestamp": datetime.utcnow().isoformat(),
            "connected_clients": len(message_queues)
        }
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pause', methods=['POST'])
def pause_agent():
    """Pause or resume the agent with proper error handling."""
    try:
        if not message_broker or not master_agent:
            return jsonify({"error": "Agent control system is not available"}), 503
            
        data = request.json
        if not isinstance(data, dict) or 'paused' not in data:
            return jsonify({"error": "Invalid request format"}), 400
            
        paused = bool(data.get('paused'))
        
        # Send pause/resume command through broker
        control_msg = Message(
            sender_id="web_ui",
            receiver_id="master_agent",
            message_type=MessageType.CONTROL,
            content={"command": "pause" if paused else "resume"},
            task_id="agent_control"
        )
        
        success = message_broker.send_message(control_msg)
        if not success:
            return jsonify({"error": "Failed to send control command"}), 500
            
        # Broadcast status change
        broadcast_message({
            'type': 'status',
            'content': 'Agent paused' if paused else 'Agent resumed',
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return jsonify({"success": True, "paused": paused})
        
    except Exception as e:
        logger.error(f"Error in pause_agent: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(Exception)
def handle_error(error):
    """Global error handler for unhandled exceptions."""
    logger.error(f"Unhandled error: {str(error)}\n{traceback.format_exc()}")
    return jsonify({"error": str(error)}), 500

# Event bus handlers
def broadcast_message(message: Dict):
    """Broadcast message to all connected clients."""
    dead_queues = []
    
    for client_id, queue in message_queues.items():
        try:
            if not queue.full():
                queue.put_nowait(message)
            else:
                logger.warning(f"Message queue full for client {client_id}")
                dead_queues.append(client_id)
        except Exception as e:
            logger.error(f"Error broadcasting to client {client_id}: {str(e)}")
            dead_queues.append(client_id)
    
    # Clean up dead queues
    for client_id in dead_queues:
        message_queues.pop(client_id, None)
        logger.info(f"Removed dead client {client_id}")

def handle_agent_message(message):
    """Handle messages from agents."""
    try:
        broadcast_message({
            'type': 'ai',
            'content': message.get('content', {}).get('text', ''),
            'thoughts': message.get('content', {}).get('thoughts'),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error handling agent message: {str(e)}\n{traceback.format_exc()}")

def handle_agent_error(error):
    """Handle agent errors."""
    try:
        broadcast_message({
            'type': 'error',
            'content': str(error.get('error', 'Unknown error')),
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error handling agent error: {str(e)}\n{traceback.format_exc()}")

# Register event handlers
event_bus.subscribe('agent_message', handle_agent_message)
event_bus.subscribe('agent_error', handle_agent_error)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
