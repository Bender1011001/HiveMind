// Import message handling functions
import { MessageType, MessageStatus, MessageHandler, createMessage } from './messages.js';

// Initialize state
const state = {
    autoScroll: true,
    darkMode: initializeDarkMode(),
    showThoughts: true,
    connected: true,
    messageHandler: null
};

// Function to initialize dark mode
function initializeDarkMode() {
    if (localStorage.getItem('darkMode') === null) {
        localStorage.setItem('darkMode', 'false');
    }
    return localStorage.getItem('darkMode') === 'true';
}

// DOM Elements
let chatHistory;
let chatInput;
let sendButton;
let progressBar;
let timeDate;

// Get base URL for API
const baseUrl = window.location.origin;

// Initialize the UI
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements
    chatHistory = document.getElementById('chat-history');
    chatInput = document.getElementById('chat-input');
    sendButton = document.getElementById('send-button');
    progressBar = document.getElementById('progress-bar');
    timeDate = document.getElementById('time-date');

    // Initialize message handler with full URL
    state.messageHandler = new MessageHandler(`${baseUrl}/api`, {
        maxRetries: 3,
        retryDelay: 2000,
        messageTimeout: 30000,
        reconnectDelay: 5000
    });

    // Initialize
    initializeEventListeners();
    updateDateTime();
    checkSystemStatus();
    loadMessageHistory();
    setInterval(updateDateTime, 1000);
    setInterval(checkSystemStatus, 5000);

    console.log('UI initialized with base URL:', baseUrl);
});

// Event Listeners
function initializeEventListeners() {
    console.log('Initializing event listeners');

    // Message handler events
    window.addEventListener('message_handler_message', (event) => {
        appendMessage(event.detail);
    });

    window.addEventListener('message_handler_message_status', (event) => {
        updateMessageStatus(event.detail.messageId, event.detail.status);
    });

    window.addEventListener('message_handler_connection_status', (event) => {
        handleConnectionStatus(event.detail.status);
    });

    window.addEventListener('message_handler_message_error', (event) => {
        handleMessageError(event.detail);
    });

    window.addEventListener('message_handler_message_timeout', (event) => {
        handleMessageTimeout(event.detail);
    });

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
        state.autoScroll = isAtBottom;
        document.querySelector('#auto-scroll-switch').checked = isAtBottom;
    });

    // Copy message content on click
    chatHistory.addEventListener('click', (e) => {
        const messageText = e.target.closest('.message-content');
        if (messageText && !window.getSelection().toString()) {
            copyToClipboard(messageText.textContent);
            showToast('Message copied to clipboard!', 'success');
        }
    });

    // Handle toast close button
    document.querySelector('.toast__close').addEventListener('click', () => {
        document.getElementById('toast').style.display = 'none';
    });

    console.log('Event listeners initialized');
}

// Message Handling
async function sendMessage() {
    console.log('Sending message');
    const content = chatInput.value.trim();
    if (!content) return;

    try {
        if (!state.connected) {
            showToast('Cannot send message: System is disconnected', 'error');
            return;
        }

        // Disable input while sending
        setInputState(false);

        // Send message through handler
        const messageId = await state.messageHandler.sendMessage(content);

        // Clear input and reset height
        chatInput.value = '';
        chatInput.style.height = 'auto';

    } catch (error) {
        showToast('Failed to send message: ' + error.message, 'error');
        console.error('Error sending message:', error);
    } finally {
        setInputState(true);
    }
}

function appendMessage(message) {
    console.log('Appending message:', message);
    const messageElement = createMessage(message.type, message.content, {
        thoughts: message.thoughts,
        timestamp: message.timestamp,
        status: message.status
    });

    // Store message ID in element for status updates
    if (message.id) {
        messageElement.dataset.messageId = message.id;
    }

    chatHistory.appendChild(messageElement);

    if (state.autoScroll) {
        scrollToBottom();
    }
}

function updateMessageStatus(messageId, status) {
    const messageElement = chatHistory.querySelector(`[data-message-id="${messageId}"]`);
    if (messageElement) {
        messageElement.dataset.status = status;

        // Update status indicator
        const indicator = messageElement.querySelector('.message-status-indicator');
        if (indicator) {
            indicator.className = `message-status-indicator status-${status}`;

            // Show error icon for failed status
            if (status === MessageStatus.FAILED) {
                indicator.innerHTML = '❌';
            }
        }
    }
}

function handleConnectionStatus(status) {
    const connected = status === 'connected';
    if (connected !== state.connected) {
        state.connected = connected;
        showToast(
            connected ? 'Connected to server' : 'Connection lost',
            connected ? 'success' : 'error'
        );
        document.documentElement.dataset.connected = connected;
        Alpine.store('chat').connected = connected;

        // Update UI elements
        setInputState(connected);
        updateProgressBar(connected ? 'Connected' : 'Disconnected');
    }
}

function handleMessageError(error) {
    showToast(`Error: ${error.error}`, 'error');
    updateProgressBar('Error: ' + error.error);
}

function handleMessageTimeout(detail) {
    showToast(`Message ${detail.messageId} timed out`, 'error');
    updateProgressBar('Message timed out');
}

// UI State Management
function setInputState(enabled) {
    chatInput.disabled = !enabled;
    sendButton.disabled = !enabled;
    sendButton.classList.toggle('loading', !enabled);
}

function updateProgressBar(text) {
    if (progressBar) {
        progressBar.textContent = text;
    }
}

// Message History Management
function loadMessageHistory() {
    const messages = state.messageHandler.messageHistory.messages;
    messages.forEach(message => appendMessage(message));
    if (state.autoScroll) {
        scrollToBottom();
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
        const response = await fetch(`${baseUrl}/api/status`);
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
    state.messageHandler.messageHistory.clear();
    showToast('Chat reset', 'success');
};

window.newChat = async function () {
    await resetChat();
    showToast('New chat started', 'success');
};

// Agent Control
window.pauseAgent = async function (paused) {
    try {
        const response = await fetch(`${baseUrl}/api/pause`, {
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
