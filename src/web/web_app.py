"""Flask application for serving the HiveMind web interface."""

from flask import Flask, render_template, jsonify, request, send_from_directory
from pathlib import Path
import sys
import json
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.event_bus import EventBus
from src.communication.broker import MessageBroker
from src.memory.mongo_store import MongoMemoryStore
from src.settings.settings import settings
from src.communication.message import Message, MessageType

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

# In-memory message storage for demo
messages = []

@app.route('/')
def index():
    """Render the main chat interface."""
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    """Serve the favicon."""
    return send_from_directory(
        app.static_folder,
        'images/lost dog.jpg',
        mimetype='image/jpeg'
    )

@app.route('/api/messages')
def get_messages():
    """Get all messages from the memory store."""
    try:
        if memory_store:
            stored_messages = memory_store.get_messages()
        else:
            stored_messages = messages
        
        return jsonify([{
            'id': str(msg.get('_id', i)),
            'type': msg.get('type', 'text'),
            'content': msg.get('content', ''),
            'timestamp': msg.get('timestamp', datetime.now().isoformat()),
            'thoughts': msg.get('thoughts', None)
        } for i, msg in enumerate(stored_messages)])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/send_message', methods=['POST'])
def send_message():
    """Send a new message."""
    try:
        data = request.json
        if not data or 'content' not in data:
            return jsonify({"error": "No message content provided"}), 400

        # Create user message
        user_message = {
            'type': 'user',
            'content': data['content'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Store user message
        if memory_store:
            memory_store.add_message(user_message)
        messages.append(user_message)

        # Create and send message through broker if available
        if message_broker:
            msg = Message(
                sender_id="web_ui",
                receiver_id="master_agent",
                message_type=MessageType.TEXT,
                content={"text": data['content']},
                task_id="chat_message"
            )
            success = message_broker.send_message(msg)
            
            # Create AI response for demo
            ai_message = {
                'type': 'ai',
                'content': 'I received your message: ' + data['content'],
                'timestamp': datetime.now().isoformat(),
                'thoughts': {
                    'reasoning': 'Processing user input',
                    'plan': 'Formulating appropriate response',
                    'criticism': 'Need to improve response generation'
                }
            }
            
            if memory_store:
                memory_store.add_message(ai_message)
            messages.append(ai_message)
            
            return jsonify({"success": success})
        else:
            return jsonify({"success": True})  # For demo without broker

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

@app.route('/api/pause', methods=['POST'])
def pause_agent():
    """Pause or resume the agent."""
    try:
        data = request.json
        paused = data.get('paused', False)
        # TODO: Implement actual agent pausing logic
        return jsonify({"success": True, "paused": paused})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
