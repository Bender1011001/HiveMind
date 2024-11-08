/**
 * Message handling module for the HiveMind web interface.
 * @module messages
 */

/**
 * Enumeration of message types supported by the system.
 * @enum {string}
 */
export const MessageType = {
  USER: 'user',
  AI: 'ai',
  SYSTEM: 'system',
  ERROR: 'error',
  WARNING: 'warning',
  CODE: 'code',
  STATUS: 'status'
};

/**
 * Enumeration of possible message statuses.
 * @enum {string}
 */
export const MessageStatus = {
  PENDING: 'pending',
  SENDING: 'sending',
  SENT: 'sent',
  FAILED: 'failed',
  RECEIVED: 'received'
};

/**
 * Handles message communication and management between client and server.
 * @class
 */
export class MessageHandler {
  /**
   * Creates a new MessageHandler instance.
   * @param {string} apiEndpoint - The API endpoint for message communication
   * @param {Object} options - Configuration options
   * @param {number} [options.maxRetries=3] - Maximum number of retry attempts
   * @param {number} [options.retryDelay=2000] - Delay between retries in milliseconds
   * @param {number} [options.messageTimeout=30000] - Message timeout in milliseconds
   * @param {number} [options.reconnectDelay=5000] - Delay before reconnection attempts
   */
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

  /**
   * Sets up the EventSource connection for server-sent events.
   * @private
   */
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

  /**
   * Handles connection errors and implements exponential backoff.
   * @private
   */
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

  /**
   * Sends a message to the server.
   * @param {string|Object} content - Message content
   * @param {string} [type=MessageType.USER] - Message type
   * @returns {string} Message ID
   */
  async sendMessage(content, type = MessageType.USER) {
    const messageId = generateMessageId();
    const message = {
      id: messageId,
      type,
      content,
      timestamp: new Date().toISOString(),
      status: MessageStatus.PENDING
    };

    this.messageHistory.add(message);
    this.emit('message', message);

    try {
      await this.sendMessageWithRetry(message);
    } catch (error) {
      this.handleMessageError(message, error);
    }

    return messageId;
  }

  /**
   * Attempts to send a message with retry logic.
   * @private
   * @param {Object} message - Message object
   * @param {number} retryCount - Current retry attempt
   * @returns {Promise<Object>} Server response
   */
  async sendMessageWithRetry(message, retryCount = 0) {
    try {
      this.updateMessageStatus(message.id, MessageStatus.SENDING);

      const response = await this.sendMessageToServer(message);
      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`);
      }

      const result = await response.json();
      this.updateMessageStatus(message.id, MessageStatus.SENT);

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

  /**
   * Sends a message to the server endpoint.
   * @private
   * @param {Object} message - Message object
   * @returns {Promise<Response>} Fetch response
   */
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

  /**
   * Starts a timeout for message response.
   * @private
   * @param {string} messageId - Message ID
   */
  startMessageTimeout(messageId) {
    const timer = setTimeout(() => {
      const message = this.messageHistory.getById(messageId);
      if (message && message.status !== MessageStatus.RECEIVED) {
        this.handleMessageTimeout(messageId);
      }
    }, this.options.messageTimeout);

    this.pendingMessages.set(messageId, { timer });
  }

  /**
   * Handles message timeout events.
   * @private
   * @param {string} messageId - Message ID
   */
  handleMessageTimeout(messageId) {
    this.updateMessageStatus(messageId, MessageStatus.FAILED);
    this.emit('message_timeout', { messageId });
  }

  /**
   * Handles message sending errors.
   * @private
   * @param {Object} message - Message object
   * @param {Error} error - Error object
   */
  handleMessageError(message, error) {
    this.updateMessageStatus(message.id, MessageStatus.FAILED);
    this.emit('message_error', {
      messageId: message.id,
      error: error.message
    });

    this.messageHistory.add({
      id: generateMessageId(),
      type: MessageType.ERROR,
      content: `Failed to send message: ${error.message}`,
      timestamp: new Date().toISOString()
    });
  }

  /**
   * Handles incoming messages from the server.
   * @private
   * @param {Object} message - Message object
   */
  handleIncomingMessage(message) {
    if (this.pendingMessages.has(message.response_to)) {
      clearTimeout(this.pendingMessages.get(message.response_to).timer);
      this.pendingMessages.delete(message.response_to);
    }

    if (message.response_to) {
      this.updateMessageStatus(message.response_to, MessageStatus.RECEIVED);
    }

    this.messageHistory.add(message);
    this.emit('message', message);
  }

  /**
   * Updates the status of a message.
   * @private
   * @param {string} messageId - Message ID
   * @param {string} status - New status
   */
  updateMessageStatus(messageId, status) {
    const message = this.messageHistory.getById(messageId);
    if (message) {
      message.status = status;
      this.emit('message_status', { messageId, status });
    }
  }

  /**
   * Emits a custom event.
   * @private
   * @param {string} event - Event name
   * @param {Object} data - Event data
   */
  emit(event, data) {
    window.dispatchEvent(new CustomEvent(`message_handler_${event}`, {
      detail: data
    }));
  }
}

/**
 * Creates a DOM element for displaying a message.
 * @param {string} type - Message type
 * @param {string|Object} content - Message content
 * @param {Object} metadata - Additional message metadata
 * @returns {HTMLElement} Message container element
 */
export function createMessage(type, content, metadata = {}) {
  const messageContainer = document.createElement('div');
  messageContainer.className = `message message-${type}`;

  if (metadata.status) {
    messageContainer.dataset.status = metadata.status;
  }

  if (metadata.timestamp) {
    const timestamp = document.createElement('div');
    timestamp.className = 'message-timestamp';
    timestamp.textContent = new Date(metadata.timestamp).toLocaleTimeString();
    messageContainer.appendChild(timestamp);
  }

  if (type === MessageType.USER) {
    const statusIndicator = document.createElement('div');
    statusIndicator.className = 'message-status-indicator';
    messageContainer.appendChild(statusIndicator);
  }

  const contentWrapper = document.createElement('div');
  contentWrapper.className = 'message-content-wrapper';

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

/**
 * Creates a user message element.
 * @private
 * @param {string} content - Message content
 * @returns {HTMLElement} Message element
 */
function createUserMessage(content) {
  const message = document.createElement('div');
  message.className = 'message-content user-content';
  message.innerHTML = formatContent(content);
  return message;
}

/**
 * Creates an AI message element.
 * @private
 * @param {string|Object} content - Message content
 * @param {Object} metadata - Message metadata
 * @returns {HTMLElement} Message element
 */
function createAIMessage(content, metadata) {
  const container = document.createElement('div');
  container.className = 'message-content ai-content';

  if (metadata.thoughts) {
    const thoughts = document.createElement('div');
    thoughts.className = 'message-thoughts';
    thoughts.innerHTML = `
            <div class="thoughts-header">Thinking Process</div>
            <div class="thoughts-content">${formatThoughts(metadata.thoughts)}</div>
        `;
    container.appendChild(thoughts);
  }

  const mainContent = document.createElement('div');
  mainContent.className = 'message-main-content';
  mainContent.innerHTML = formatContent(content);
  container.appendChild(mainContent);

  return container;
}

/**
 * Creates a system message element.
 * @private
 * @param {string} content - Message content
 * @returns {HTMLElement} Message element
 */
function createSystemMessage(content) {
  const message = document.createElement('div');
  message.className = 'message-content system-content';
  message.innerHTML = `<i class="system-icon">ℹ️</i> ${formatContent(content)}`;
  return message;
}

/**
 * Creates an error message element.
 * @private
 * @param {string} content - Message content
 * @returns {HTMLElement} Message element
 */
function createErrorMessage(content) {
  const message = document.createElement('div');
  message.className = 'message-content error-content';
  message.innerHTML = `<i class="error-icon">❌</i> ${formatContent(content)}`;
  return message;
}

/**
 * Creates a warning message element.
 * @private
 * @param {string} content - Message content
 * @returns {HTMLElement} Message element
 */
function createWarningMessage(content) {
  const message = document.createElement('div');
  message.className = 'message-content warning-content';
  message.innerHTML = `<i class="warning-icon">⚠️</i> ${formatContent(content)}`;
  return message;
}

/**
 * Creates a status message element.
 * @private
 * @param {string} content - Message content
 * @returns {HTMLElement} Message element
 */
function createStatusMessage(content) {
  const message = document.createElement('div');
  message.className = 'message-content status-content';
  message.innerHTML = `<i class="status-icon">🔄</i> ${formatContent(content)}`;
  return message;
}

/**
 * Creates a code message element.
 * @private
 * @param {string} content - Code content
 * @param {string} language - Programming language
 * @returns {HTMLElement} Code block element
 */
function createCodeMessage(content, language) {
  const container = document.createElement('div');
  container.className = 'code-block-container';

  const copyButton = document.createElement('button');
  copyButton.className = 'copy-code-button';
  copyButton.textContent = 'Copy';
  copyButton.onclick = () => copyCode(content);

  const codeBlock = document.createElement('pre');
  const code = document.createElement('code');
  code.className = language ? `language-${language}` : '';
  code.textContent = content;

  codeBlock.appendChild(code);
  container.appendChild(copyButton);
  container.appendChild(codeBlock);

  return container;
}

/**
 * Formats message content, handling code blocks.
 * @private
 * @param {string} content - Raw content
 * @returns {string} Formatted content
 */
function formatContent(content) {
  return content.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, language, code) => {
    return createCodeBlock(code.trim(), language);
  });
}

/**
 * Formats thinking process content.
 * @private
 * @param {string|Object} thoughts - Thinking process content
 * @returns {string} Formatted HTML
 */
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

/**
 * Creates a code block element.
 * @private
 * @param {string} code - Code content
 * @param {string} language - Programming language
 * @returns {string} HTML string for code block
 */
function createCodeBlock(code, language) {
  return `
        <div class="code-block">
            <button class="copy-code-button" onclick="copyCode(this)">Copy</button>
            <pre><code class="language-${language || 'plaintext'}">${escapeHtml(code)}</code></pre>
        </div>
    `;
}

/**
 * Escapes HTML special characters.
 * @private
 * @param {string} text - Raw text
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Copies code to clipboard.
 * @private
 * @param {HTMLElement} button - Copy button element
 * @returns {Promise<void>}
 */
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

/**
 * Generates a unique message ID.
 * @private
 * @returns {string} Message ID
 */
function generateMessageId() {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Manages message history with local storage persistence.
 * @class
 */
export class MessageHistory {
  /**
   * Creates a new MessageHistory instance.
   * @param {number} [maxSize=100] - Maximum number of messages to store
   */
  constructor(maxSize = 100) {
    this.maxSize = maxSize;
    this.messages = [];
    this.messageMap = new Map();  // messageId -> message
    this.loadFromLocalStorage();
  }

  /**
   * Adds a message to history.
   * @param {Object} message - Message object
   */
  add(message) {
    if (!message.id) {
      message.id = generateMessageId();
    }

    this.messages.push(message);
    this.messageMap.set(message.id, message);

    while (this.messages.length > this.maxSize) {
      const removed = this.messages.shift();
      this.messageMap.delete(removed.id);
    }

    this.saveToLocalStorage();
  }

  /**
   * Retrieves a message by ID.
   * @param {string} messageId - Message ID
   * @returns {Object|undefined} Message object
   */
  getById(messageId) {
    return this.messageMap.get(messageId);
  }

  /**
   * Clears message history.
   */
  clear() {
    this.messages = [];
    this.messageMap.clear();
    this.saveToLocalStorage();
  }

  /**
   * Gets timestamp of last message.
   * @returns {Date} Timestamp
   */
  getLastMessageTime() {
    if (this.messages.length === 0) return new Date(0);
    return new Date(this.messages[this.messages.length - 1].timestamp);
  }

  /**
   * Loads message history from local storage.
   * @private
   */
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

  /**
   * Saves message history to local storage.
   * @private
   */
  saveToLocalStorage() {
    try {
      localStorage.setItem('messageHistory', JSON.stringify(this.messages));
    } catch (error) {
      console.error('Failed to save message history:', error);
    }
  }
}
