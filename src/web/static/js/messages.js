// Message type definitions
export const MessageType = {
    USER: 'user',
    AI: 'ai',
    SYSTEM: 'system',
    ERROR: 'error',
    WARNING: 'warning',
    CODE: 'code',
    STATUS: 'status'
};

export const MessageStatus = {
    PENDING: 'pending',
    SENDING: 'sending',
    SENT: 'sent',
    FAILED: 'failed',
    RECEIVED: 'received'
};

// Message handling class
export class MessageHandler {
    constructor(apiEndpoint, options = {}) {
        this.apiEndpoint = apiEndpoint;
        this.options = {
            maxRetries: 3,
            retryDelay: 2000,
            messageTimeout: 30000,
            reconnectDelay: 5000,
            ...options
        };

        this.messageHistory = new MessageHistory();
        this.pendingMessages = new Map();  // messageId -> {message, retryCount, timer}
        this.eventSource = null;
        this.isConnected = false;
        this.connectionAttempts = 0;

        this.setupEventSource();
    }

    setupEventSource() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        this.eventSource = new EventSource(`${this.apiEndpoint}/stream`);

        this.eventSource.onopen = () => {
            this.isConnected = true;
            this.connectionAttempts = 0;
            this.emit('connection_status', { status: 'connected' });
        };

        this.eventSource.onerror = () => {
            this.isConnected = false;
            this.emit('connection_status', { status: 'disconnected' });
            this.handleConnectionError();
        };

        this.eventSource.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleIncomingMessage(message);
            } catch (error) {
                console.error('Error parsing message:', error);
            }
        };
    }

    handleConnectionError() {
        this.connectionAttempts++;
        const delay = Math.min(
            this.options.reconnectDelay * Math.pow(2, this.connectionAttempts - 1),
            30000
        );

        setTimeout(() => {
            if (!this.isConnected) {
                this.setupEventSource();
            }
        }, delay);
    }

    async sendMessage(content, type = MessageType.USER) {
        const messageId = generateMessageId();
        const message = {
            id: messageId,
            type,
            content,
            timestamp: new Date().toISOString(),
            status: MessageStatus.PENDING
        };

        // Add to history and update UI immediately
        this.messageHistory.add(message);
        this.emit('message', message);

        try {
            await this.sendMessageWithRetry(message);
        } catch (error) {
            this.handleMessageError(message, error);
        }

        return messageId;
    }

    async sendMessageWithRetry(message, retryCount = 0) {
        try {
            this.updateMessageStatus(message.id, MessageStatus.SENDING);

            const response = await this.sendMessageToServer(message);
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }

            const result = await response.json();
            this.updateMessageStatus(message.id, MessageStatus.SENT);

            // Start timeout for response
            this.startMessageTimeout(message.id);

            return result;

        } catch (error) {
            if (retryCount < this.options.maxRetries) {
                await new Promise(resolve =>
                    setTimeout(resolve, this.options.retryDelay)
                );
                return this.sendMessageWithRetry(message, retryCount + 1);
            }
            throw error;
        }
    }

    async sendMessageToServer(message) {
        return fetch(`${this.apiEndpoint}/send_message`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content: message.content,
                type: message.type,
                message_id: message.id
            })
        });
    }

    startMessageTimeout(messageId) {
        const timer = setTimeout(() => {
            const message = this.messageHistory.getById(messageId);
            if (message && message.status !== MessageStatus.RECEIVED) {
                this.handleMessageTimeout(messageId);
            }
        }, this.options.messageTimeout);

        this.pendingMessages.set(messageId, { timer });
    }

    handleMessageTimeout(messageId) {
        this.updateMessageStatus(messageId, MessageStatus.FAILED);
        this.emit('message_timeout', { messageId });
    }

    handleMessageError(message, error) {
        this.updateMessageStatus(message.id, MessageStatus.FAILED);
        this.emit('message_error', {
            messageId: message.id,
            error: error.message
        });

        // Add error message to history
        this.messageHistory.add({
            id: generateMessageId(),
            type: MessageType.ERROR,
            content: `Failed to send message: ${error.message}`,
            timestamp: new Date().toISOString()
        });
    }

    handleIncomingMessage(message) {
        // Clear timeout for corresponding message if exists
        if (this.pendingMessages.has(message.response_to)) {
            clearTimeout(this.pendingMessages.get(message.response_to).timer);
            this.pendingMessages.delete(message.response_to);
        }

        // Update original message status
        if (message.response_to) {
            this.updateMessageStatus(message.response_to, MessageStatus.RECEIVED);
        }

        // Add to history and emit
        this.messageHistory.add(message);
        this.emit('message', message);
    }

    updateMessageStatus(messageId, status) {
        const message = this.messageHistory.getById(messageId);
        if (message) {
            message.status = status;
            this.emit('message_status', { messageId, status });
        }
    }

    emit(event, data) {
        // Dispatch custom event
        window.dispatchEvent(new CustomEvent(`message_handler_${event}`, {
            detail: data
        }));
    }
}

// Message rendering functions
export function createMessage(type, content, metadata = {}) {
    const messageContainer = document.createElement('div');
    messageContainer.className = `message message-${type}`;

    if (metadata.status) {
        messageContainer.dataset.status = metadata.status;
    }

    // Add timestamp if provided
    if (metadata.timestamp) {
        const timestamp = document.createElement('div');
        timestamp.className = 'message-timestamp';
        timestamp.textContent = new Date(metadata.timestamp).toLocaleTimeString();
        messageContainer.appendChild(timestamp);
    }

    // Add status indicator for user messages
    if (type === MessageType.USER) {
        const statusIndicator = document.createElement('div');
        statusIndicator.className = 'message-status-indicator';
        messageContainer.appendChild(statusIndicator);
    }

    // Create content wrapper
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'message-content-wrapper';

    // Handle different message types
    switch (type) {
        case MessageType.USER:
            contentWrapper.appendChild(createUserMessage(content));
            break;
        case MessageType.AI:
            contentWrapper.appendChild(createAIMessage(content, metadata));
            break;
        case MessageType.SYSTEM:
            contentWrapper.appendChild(createSystemMessage(content));
            break;
        case MessageType.ERROR:
            contentWrapper.appendChild(createErrorMessage(content));
            break;
        case MessageType.WARNING:
            contentWrapper.appendChild(createWarningMessage(content));
            break;
        case MessageType.CODE:
            contentWrapper.appendChild(createCodeMessage(content, metadata.language));
            break;
        case MessageType.STATUS:
            contentWrapper.appendChild(createStatusMessage(content));
            break;
    }

    messageContainer.appendChild(contentWrapper);

    return messageContainer;
}

function createUserMessage(content) {
    const message = document.createElement('div');
    message.className = 'message-content user-content';
    message.innerHTML = formatContent(content);
    return message;
}

function createAIMessage(content, metadata) {
    const container = document.createElement('div');
    container.className = 'message-content ai-content';

    // Add thinking process if available
    if (metadata.thoughts) {
        const thoughts = document.createElement('div');
        thoughts.className = 'message-thoughts';
        thoughts.innerHTML = `
            <div class="thoughts-header">Thinking Process</div>
            <div class="thoughts-content">${formatThoughts(metadata.thoughts)}</div>
        `;
        container.appendChild(thoughts);
    }

    // Add main content
    const mainContent = document.createElement('div');
    mainContent.className = 'message-main-content';
    mainContent.innerHTML = formatContent(content);
    container.appendChild(mainContent);

    return container;
}

function createSystemMessage(content) {
    const message = document.createElement('div');
    message.className = 'message-content system-content';
    message.innerHTML = `<i class="system-icon">ℹ️</i> ${formatContent(content)}`;
    return message;
}

function createErrorMessage(content) {
    const message = document.createElement('div');
    message.className = 'message-content error-content';
    message.innerHTML = `<i class="error-icon">❌</i> ${formatContent(content)}`;
    return message;
}

function createWarningMessage(content) {
    const message = document.createElement('div');
    message.className = 'message-content warning-content';
    message.innerHTML = `<i class="warning-icon">⚠️</i> ${formatContent(content)}`;
    return message;
}

function createStatusMessage(content) {
    const message = document.createElement('div');
    message.className = 'message-content status-content';
    message.innerHTML = `<i class="status-icon">🔄</i> ${formatContent(content)}`;
    return message;
}

function createCodeMessage(content, language) {
    const container = document.createElement('div');
    container.className = 'code-block-container';

    // Add copy button
    const copyButton = document.createElement('button');
    copyButton.className = 'copy-code-button';
    copyButton.textContent = 'Copy';
    copyButton.onclick = () => copyCode(content);

    // Add code block
    const codeBlock = document.createElement('pre');
    const code = document.createElement('code');
    code.className = language ? `language-${language}` : '';
    code.textContent = content;

    codeBlock.appendChild(code);
    container.appendChild(copyButton);
    container.appendChild(codeBlock);

    return container;
}

// Helper functions
function formatContent(content) {
    // Replace code blocks with syntax highlighted versions
    return content.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, language, code) => {
        return createCodeBlock(code.trim(), language);
    });
}

function formatThoughts(thoughts) {
    if (typeof thoughts === 'string') {
        return `<div class="thought-item">${thoughts}</div>`;
    }

    return `
        ${thoughts.reasoning ? `
            <div class="thought-item">
                <strong>Reasoning:</strong> ${thoughts.reasoning}
            </div>
        ` : ''}
        ${thoughts.plan ? `
            <div class="thought-item">
                <strong>Plan:</strong> ${thoughts.plan}
            </div>
        ` : ''}
        ${thoughts.criticism ? `
            <div class="thought-item">
                <strong>Criticism:</strong> ${thoughts.criticism}
            </div>
        ` : ''}
    `;
}

function createCodeBlock(code, language) {
    return `
        <div class="code-block">
            <button class="copy-code-button" onclick="copyCode(this)">Copy</button>
            <pre><code class="language-${language || 'plaintext'}">${escapeHtml(code)}</code></pre>
        </div>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function copyCode(button) {
    const codeBlock = button.nextElementSibling.querySelector('code');
    try {
        await navigator.clipboard.writeText(codeBlock.textContent);
        button.textContent = 'Copied!';
        setTimeout(() => {
            button.textContent = 'Copy';
        }, 2000);
    } catch (err) {
        console.error('Failed to copy code:', err);
        button.textContent = 'Failed to copy';
        setTimeout(() => {
            button.textContent = 'Copy';
        }, 2000);
    }
}

function generateMessageId() {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Message history management
export class MessageHistory {
    constructor(maxSize = 100) {
        this.maxSize = maxSize;
        this.messages = [];
        this.messageMap = new Map();  // messageId -> message
        this.loadFromLocalStorage();
    }

    add(message) {
        // Ensure message has an ID
        if (!message.id) {
            message.id = generateMessageId();
        }

        this.messages.push(message);
        this.messageMap.set(message.id, message);

        // Remove oldest messages if exceeding maxSize
        while (this.messages.length > this.maxSize) {
            const removed = this.messages.shift();
            this.messageMap.delete(removed.id);
        }

        this.saveToLocalStorage();
    }

    getById(messageId) {
        return this.messageMap.get(messageId);
    }

    clear() {
        this.messages = [];
        this.messageMap.clear();
        this.saveToLocalStorage();
    }

    getLastMessageTime() {
        if (this.messages.length === 0) return new Date(0);
        return new Date(this.messages[this.messages.length - 1].timestamp);
    }

    loadFromLocalStorage() {
        try {
            const saved = localStorage.getItem('messageHistory');
            if (saved) {
                this.messages = JSON.parse(saved);
                this.messageMap = new Map(
                    this.messages.map(msg => [msg.id, msg])
                );
            }
        } catch (error) {
            console.error('Failed to load message history:', error);
            this.messages = [];
            this.messageMap.clear();
        }
    }

    saveToLocalStorage() {
        try {
            localStorage.setItem('messageHistory', JSON.stringify(this.messages));
        } catch (error) {
            console.error('Failed to save message history:', error);
        }
    }
}
