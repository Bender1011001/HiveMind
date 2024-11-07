// Import highlight.js for code syntax highlighting
import hljs from 'https://cdn.skypack.dev/highlight.js';

// State management
let autoScroll = true;
let darkMode = localStorage.getItem('darkMode') !== 'false';
let showThoughts = true;
let connected = true;
let messageHistory = [];

// DOM Elements
const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const sendButton = document.getElementById('send-button');
const progressBar = document.getElementById('progress-bar');
const timeDate = document.getElementById('time-date');

// Initialize the UI
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    updateDateTime();
    checkSystemStatus();
    loadMessageHistory();
    setInterval(updateDateTime, 1000);
    setInterval(checkSystemStatus, 5000);
});

// Event Listeners
function initializeEventListeners() {
    // Send message on Enter (but allow Shift+Enter for new lines)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Send message on button click
    sendButton.addEventListener('click', sendMessage);

    // Auto-resize input field
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = chatInput.scrollHeight + 'px';
    });

    // Handle chat history scrolling
    chatHistory.addEventListener('scroll', () => {
        const isAtBottom = chatHistory.scrollHeight - chatHistory.scrollTop <= chatHistory.clientHeight + 100;
        if (autoScroll !== isAtBottom) {
            autoScroll = isAtBottom;
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

    // Copy code blocks with button
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('copy-code-button')) {
            const codeBlock = e.target.nextElementSibling;
            copyToClipboard(codeBlock.textContent);
            e.target.textContent = 'Copied!';
            setTimeout(() => {
                e.target.textContent = 'Copy';
            }, 2000);
        }
    });
}

// Message Handling
async function sendMessage() {
    const message = chatInput.value.trim();
    if (!message) return;

    try {
        // Add user message to chat
        appendMessage({
            type: 'user',
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

        if (!response.ok) throw new Error('Failed to send message');

        // Start polling for AI response
        startResponsePolling();

    } catch (error) {
        showToast(error.message, 'error');
    }
}

function appendMessage(message) {
    const messageElement = createMessageElement(message);
    chatHistory.appendChild(messageElement);
    messageHistory.push(message);
    saveMessageHistory();

    if (autoScroll) {
        scrollToBottom();
    }

    // Highlight code blocks
    messageElement.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
    });
}

function createMessageElement(message) {
    const div = document.createElement('div');
    div.className = `message message-${message.type}`;

    // Format timestamp
    const time = new Date(message.timestamp).toLocaleTimeString();

    // Create message content
    const content = document.createElement('div');
    content.className = 'message-content';

    // Handle code blocks
    const formattedContent = formatMessageContent(message.content);
    content.innerHTML = formattedContent;

    // Add timestamp
    const timestamp = document.createElement('div');
    timestamp.className = 'message-timestamp';
    timestamp.textContent = time;

    div.appendChild(content);
    div.appendChild(timestamp);

    return div;
}

function formatMessageContent(content) {
    // Replace code blocks with syntax highlighted versions
    return content.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, language, code) => {
        const highlightedCode = hljs.highlight(code.trim(), {
            language: language || 'plaintext'
        }).value;

        return `
            <div class="code-block">
                <button class="copy-code-button">Copy</button>
                <pre><code class="hljs ${language || ''}">${highlightedCode}</code></pre>
            </div>
        `;
    });
}

// Utility Functions
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
    } catch (err) {
        console.error('Failed to copy text:', err);
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

    setTimeout(() => {
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

        if (status.mongodb_connected && status.rabbitmq_connected) {
            if (!connected) {
                showToast('System connected', 'success');
                connected = true;
            }
        } else {
            if (connected) {
                showToast('System disconnected', 'error');
                connected = false;
            }
        }

        // Update UI to reflect status
        document.documentElement.dataset.connected = connected;

    } catch (error) {
        if (connected) {
            showToast('Connection lost', 'error');
            connected = false;
        }
    }
}

// Message History Persistence
function saveMessageHistory() {
    localStorage.setItem('messageHistory', JSON.stringify(
        messageHistory.slice(-100) // Keep last 100 messages
    ));
}

function loadMessageHistory() {
    try {
        const saved = localStorage.getItem('messageHistory');
        if (saved) {
            const messages = JSON.parse(saved);
            messages.forEach(message => appendMessage(message));
        }
    } catch (error) {
        console.error('Failed to load message history:', error);
    }
}

// Theme Management
window.toggleDarkMode = function (isDark) {
    darkMode = isDark;
    localStorage.setItem('darkMode', isDark);
    document.body.classList.toggle('light-mode', !isDark);
};

// Autoscroll Management
window.toggleAutoScroll = function (enabled) {
    autoScroll = enabled;
    if (enabled) {
        scrollToBottom();
    }
};

// Thoughts Display Management
window.toggleThoughts = function (show) {
    showThoughts = show;
    document.documentElement.dataset.showThoughts = show;
};

// Export functions for use in HTML
window.sendMessage = sendMessage;
window.resetChat = async function () {
    chatHistory.innerHTML = '';
    messageHistory = [];
    saveMessageHistory();
    showToast('Chat reset', 'success');
};

window.newChat = async function () {
    await resetChat();
    showToast('New chat started', 'success');
};
