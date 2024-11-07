"""Flask application for serving the HiveMind web interface."""

from flask import Flask, render_template, jsonify, request
from pathlib import Path
import sys

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.event_bus import EventBus
from src.communication.broker import MessageBroker
from src.memory.mongo_store import MongoMemoryStore
from src.settings.settings import settings

app = Flask(__name__)
event_bus = EventBus()

# Initialize core components
try:
    memory_store = MongoMemoryStore()
    message_broker = MessageBroker()
except Exception as e:
    print(f"Error initializing core components: {e}")
    memory_store = None
    message_broker = None

@app.route('/')
def index():
    """Render the main chat interface."""
    return render_template('index.html')

@app.route('/api/messages')
def get_messages():
    """Get all messages from the memory store."""
    if not memory_store:
        return jsonify({"error": "Memory store not available"}), 500
    
    messages = memory_store.get_messages()
    return jsonify(messages)

@app.route('/api/send_message', methods=['POST'])
def send_message():
    """Send a new message."""
    if not message_broker:
        return jsonify({"error": "Message broker not available"}), 500
    
    try:
        message = request.json
        success = message_broker.send_message(message)
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status')
def get_status():
    """Get system status."""
    return jsonify({
        "mongodb_connected": memory_store is not None,
        "rabbitmq_connected": message_broker is not None,
        "model_name": settings.model_name
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
