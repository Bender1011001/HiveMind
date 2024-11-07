// Import message handling functions
import { MessageType, createMessage, MessageHistory } from './messages.js';

// Initialize state
const state = {
    autoScroll: true,
    darkMode: localStorage.getItem('darkMode') !== 'false',
    showThoughts: true,
    connected: true,
    messageHistory: new MessageHistory()
};

// DOM Elements
let chatHistory;
let chatInput;
let sendButton;
let progressBar;
let timeDate;

// Initialize the UI
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements
    chatHistory = document.getElementById('chat-history');
    chatInput = document.getElementById('chat-input');
    sendButton = document.getElementById('send-button');
    progressBar = document.getElementById('progress-bar');
    timeDate = document.getElementById('time-date');

    // Initialize
    initializeEventListeners();
    updateDateTime();
    checkSystemStatus();
    loadMessageHistory();
    setInterval(updateDateTime, 1000);
    setInterval(checkSystemStatus, 5000);

    console.log('UI initialized');
});

// Event Listeners
function initializeEventListeners() {
    console.log('Initializing event listeners');

    // Send message on Enter (but allow Shift+Enter for new lines)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Send message on button click
    sendButton.addEventListener('click', () => {
        console.log('Send button clicked');
        sendMessage();
    });

    // Auto-resize input field
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = chatInput.scrollHeight + 'px';
    });

    // Handle chat history scrolling
    chatHistory.addEventListener('scroll', () => {
        const isAtBottom = chatHistory.scrollHeight - chatHistory.scrollTop <= chatHistory.clientHeight + 100;
        if (state.autoScroll !== isAtBottom) {
            state.autoScroll = isAtBottom;
            document.querySelector('#auto-scroll-switch').checked = isAtBottom;
        }
    });

    // Copy message content on click
    chatHistory.addEventListener('click', (e) => {
        const messageText = e.target.closest('.message-content');
        if (messageText && !window.getSelection().toString()) {
            copyToClipboard(messageText.textContent);
            showToast('Message copied to clipboard!', 'success');
        }
    });

    console.log('Event listeners initialized');
}

// Message Handling
async function sendMessage() {
    console.log('Sending message');
    const message = chatInput.value.trim();
    if (!message) return;

    try {
        // Add user message to chat
        appendMessage({
            type: MessageType.USER,
            content: message,
            timestamp: new Date()
        });

        // Clear input and reset height
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // Send to backend
        const response = await fetch('/api/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ content: message })
        });

        if (!response.ok) {
            throw new Error('Failed to send message');
        }

        const data = await response.json();
        console.log('Message sent:', data);

        if (data.success) {
            // Start polling for AI response
            pollForResponse();
        } else {
            showToast('Error sending message', 'error');
        }

    } catch (error) {
        showToast(error.message, 'error');
        console.error('Error sending message:', error);
    }
}

function appendMessage(message) {
    console.log('Appending message:', message);
    const messageElement = createMessage(message.type, message.content, {
        thoughts: message.thoughts,
        timestamp: message.timestamp
    });

    chatHistory.appendChild(messageElement);
    state.messageHistory.add(message);

    if (state.autoScroll) {
        scrollToBottom();
    }
}

async function pollForResponse() {
    try {
        const response = await fetch('/api/messages');
        const messages = await response.json();

        // Find new messages
        const lastMessageTime = state.messageHistory.getLastMessageTime();
        const newMessages = messages.filter(msg => new Date(msg.timestamp) > lastMessageTime);

        // Add new messages to chat
        newMessages.forEach(msg => appendMessage(msg));

        // Continue polling if we're still waiting for a response
        if (messages[messages.length - 1]?.type !== MessageType.AI) {
            setTimeout(pollForResponse, 1000);
        }
    } catch (error) {
        console.error('Error polling for response:', error);
        showToast('Error receiving response', 'error');
    }
}

// Utility Functions
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard!', 'success');
    } catch (err) {
        console.error('Failed to copy text:', err);
        showToast('Failed to copy text', 'error');
    }
}

function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.className = `toast toast--${type}`;
    toast.querySelector('.toast__message').textContent = message;
    toast.style.display = 'flex';

    // Clear any existing timeout
    if (toast.timeoutId) {
        clearTimeout(toast.timeoutId);
    }

    // Auto-hide after 3 seconds
    toast.timeoutId = setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

function updateDateTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    const dateStr = now.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
    timeDate.innerHTML = `${timeStr}<br><span class="date">${dateStr}</span>`;
}

async function checkSystemStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();

        const newConnected = status.mongodb_connected && status.rabbitmq_connected;
        if (newConnected !== state.connected) {
            state.connected = newConnected;
            showToast(
                state.connected ? 'System connected' : 'System disconnected',
                state.connected ? 'success' : 'error'
            );

            // Update UI to reflect status
            document.documentElement.dataset.connected = state.connected;
            Alpine.store('chat').connected = state.connected;
        }
    } catch (error) {
        if (state.connected) {
            state.connected = false;
            showToast('Connection lost', 'error');
            document.documentElement.dataset.connected = false;
            Alpine.store('chat').connected = false;
        }
    }
}

// Message History Management
function loadMessageHistory() {
    const messages = state.messageHistory.messages;
    messages.forEach(message => appendMessage(message));
}

// Theme Management
window.toggleDarkMode = function (isDark) {
    state.darkMode = isDark;
    localStorage.setItem('darkMode', isDark);
    document.body.classList.toggle('light-mode', !isDark);
};

// Autoscroll Management
window.toggleAutoScroll = function (enabled) {
    state.autoScroll = enabled;
    if (enabled) {
        scrollToBottom();
    }
};

// Thoughts Display Management
window.toggleThoughts = function (show) {
    state.showThoughts = show;
    document.documentElement.dataset.showThoughts = show;
};

// Chat Management
window.resetChat = async function () {
    chatHistory.innerHTML = '';
    state.messageHistory.clear();
    showToast('Chat reset', 'success');
};

window.newChat = async function () {
    await resetChat();
    showToast('New chat started', 'success');
};

// Agent Control
window.pauseAgent = async function (paused) {
    try {
        const response = await fetch('/api/pause', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ paused })
        });

        if (response.ok) {
            Alpine.store('chat').paused = paused;
            showToast(paused ? 'Agent paused' : 'Agent resumed', 'success');
        } else {
            throw new Error('Failed to update agent state');
        }
    } catch (error) {
        showToast(error.message, 'error');
    }
};
