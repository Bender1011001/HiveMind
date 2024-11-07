// Message type definitions
export const MessageType = {
    USER: 'user',
    AI: 'ai',
    SYSTEM: 'system',
    ERROR: 'error',
    WARNING: 'warning',
    CODE: 'code'
};

// Message rendering functions
export function createMessage(type, content, metadata = {}) {
    const messageContainer = document.createElement('div');
    messageContainer.className = `message message-${type}`;

    // Add timestamp if provided
    if (metadata.timestamp) {
        const timestamp = document.createElement('div');
        timestamp.className = 'message-timestamp';
        timestamp.textContent = new Date(metadata.timestamp).toLocaleTimeString();
        messageContainer.appendChild(timestamp);
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
    }
}

// Message history management
export class MessageHistory {
    constructor(maxSize = 100) {
        this.maxSize = maxSize;
        this.messages = [];
        this.loadFromLocalStorage();
    }

    add(message) {
        this.messages.push(message);
        if (this.messages.length > this.maxSize) {
            this.messages.shift();
        }
        this.saveToLocalStorage();
    }

    clear() {
        this.messages = [];
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
            }
        } catch (error) {
            console.error('Failed to load message history:', error);
            this.messages = [];
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
