/**
 * messages.js - Message handling and display for MetaGPT visualization
 */

// Message tracking
let processedMessages = new Set();

/**
 * Create a unique message ID
 * @param {string} role - The role of the message sender
 * @param {string} content - The content of the message
 * @returns {string} - A unique ID for the message
 */
function createMessageId(role, content) {
    // Create a simple hash of the content to use as ID
    let hash = 0;
    const combinedString = `${role}:${content}`.substring(0, 200); // Limit to first 200 chars
    
    for (let i = 0; i < combinedString.length; i++) {
        const char = combinedString.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
    }
    
    return `${role}_${hash}`;
}

/**
 * Create a message element
 * @param {string} role - The role of the message sender
 * @param {string} content - The content of the message
 * @param {boolean} isError - Whether the message is an error
 * @param {boolean} isReconnecting - Whether the message is a reconnection message
 * @returns {HTMLElement} - The message element
 */
function createMessage(role, content, isError = false, isReconnecting = false) {
    debugLog(`Creating message element for role: ${role}`);
    
    const messageElement = document.createElement('div');
    messageElement.className = `message ${role}`;
    
    if (isError) {
        messageElement.classList.add('error');
    }
    
    if (isReconnecting) {
        messageElement.classList.add('reconnecting');
    }
    
    // If this is a new message, highlight it briefly
    messageElement.classList.add('new-message-highlight');
    setTimeout(() => {
        messageElement.classList.remove('new-message-highlight');
    }, 2000);
    
    // Create avatar
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    
    // Use the avatar generation function if available
    if (typeof createAvatarElement === 'function') {
        avatar.appendChild(createAvatarElement(role));
    } else if (typeof generateAvatarHtml === 'function') {
        avatar.innerHTML = generateAvatarHtml(role);
    } else {
        // Create a simple fallback avatar if functions aren't available
        const fallbackAvatar = document.createElement('div');
        fallbackAvatar.className = 'generated-avatar';
        fallbackAvatar.style.backgroundColor = '#7D7C7C'; // Gray fallback
        
        const initials = document.createElement('span');
        initials.textContent = role.substring(0, 2).toUpperCase();
        fallbackAvatar.appendChild(initials);
        
        avatar.appendChild(fallbackAvatar);
    }
    
    messageElement.appendChild(avatar);
    
    // Create message content container
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    // Create header with role name
    const header = document.createElement('div');
    header.className = 'header';
    
    const roleName = document.createElement('div');
    roleName.className = 'role-name';
    roleName.textContent = typeof getRoleDisplayName === 'function' ? 
        getRoleDisplayName(role) : role;
    
    const timestamp = document.createElement('div');
    timestamp.className = 'timestamp';
    timestamp.textContent = new Date().toLocaleTimeString();
    
    header.appendChild(roleName);
    header.appendChild(timestamp);
    messageContent.appendChild(header);
    
    // Create content
    const contentDiv = document.createElement('div');
    contentDiv.className = 'content';
    
    // Check if it's an error message
    if (isError) {
        contentDiv.classList.add('error');
        contentDiv.textContent = content;
    } else if (isReconnecting) {
        contentDiv.classList.add('reconnecting');
        contentDiv.textContent = content;
    } else {
        // Check if the content is empty
        if (!content || content.trim() === '') {
            contentDiv.innerHTML = '<em>Empty message</em>';
        } else {
            // Check if the content is code
            if (content.startsWith('```') && content.endsWith('```')) {
                const code = content.substring(3, content.length - 3);
                const pre = document.createElement('pre');
                const codeElement = document.createElement('code');
                codeElement.textContent = code;
                pre.appendChild(codeElement);
                contentDiv.appendChild(pre);
            } else {
                // Use the marked library to render Markdown
                try {
                    contentDiv.innerHTML = marked.parse(content);
                } catch (e) {
                    debugLog("Error parsing markdown:", e);
                    contentDiv.textContent = content;
                }
            }
        }
    }
    
    messageContent.appendChild(contentDiv);
    messageElement.appendChild(messageContent);
    
    return messageElement;
}

/**
 * Extract role and content from different message formats
 * @param {Object} data - The message data
 * @returns {Object|null} - The extracted role and content, or null if it's a ping message
 */
function extractRoleAndContent(data) {
    let role = 'system';
    let content = '';
    let isError = false;
    let isReconnecting = false;
    
    if (data.status === 'ping') {
        return null; // Ignore ping messages
    }
    
    debugLog('Processing message data:', JSON.stringify(data));
    
    // Check for error or reconnection messages
    if (data.status === 'error' || (data.response && data.response.error)) {
        isError = true;
        role = data.role || 'qa_engineer';
        
        if (data.response && data.response.error) {
            content = `### Error\n\n${data.response.error.message || JSON.stringify(data.response.error)}`;
        } else {
            content = `### Error\n\n${data.message || "An unknown error occurred"}`;
        }
    } else if (data.status === 'reconnecting' || (typeof data === 'object' && data.content && data.content.includes('Reconnecting'))) {
        isReconnecting = true;
        role = 'system';
        content = data.content || 'Attempting to reconnect...';
    }
    // API response format
    else if (data.hasOwnProperty('response') && data.response && data.role) {
        role = data.role;
        
        if (data.response.hasOwnProperty('choices') && 
            Array.isArray(data.response.choices) && 
            data.response.choices.length > 0 &&
            data.response.choices[0].hasOwnProperty('message') &&
            data.response.choices[0].message.hasOwnProperty('content')) {
            
            content = data.response.choices[0].message.content;
        } else if (data.response.hasOwnProperty('content')) {
            content = data.response.content;
        } else {
            content = JSON.stringify(data.response, null, 2);
        }
    } 
    // Direct role/content format
    else if (data.hasOwnProperty('role') && data.hasOwnProperty('content')) {
        role = data.role;
        content = data.content;
    }
    // Status/message format (common in monitoring messages)
    else if (data.hasOwnProperty('status') && data.hasOwnProperty('message')) {
        role = 'system';
        content = `${data.status}: ${data.message}`;
    }
    // Log file format
    else if (data.hasOwnProperty('file_content')) {
        const fileContent = data.file_content;
        
        if (typeof fileContent === 'object') {
            if (fileContent.hasOwnProperty('role') && fileContent.hasOwnProperty('content')) {
                role = fileContent.role;
                content = fileContent.content;
            } else if (fileContent.hasOwnProperty('response')) {
                role = fileContent.role || 'system';
                
                if (fileContent.response.hasOwnProperty('choices') && 
                    Array.isArray(fileContent.response.choices) && 
                    fileContent.response.choices.length > 0 &&
                    fileContent.response.choices[0].hasOwnProperty('message')) {
                    
                    content = fileContent.response.choices[0].message.content;
                } else {
                    content = JSON.stringify(fileContent.response, null, 2);
                }
            }
        } else if (typeof fileContent === 'string') {
            try {
                const parsedContent = JSON.parse(fileContent);
                if (parsedContent.hasOwnProperty('role') && parsedContent.hasOwnProperty('content')) {
                    role = parsedContent.role;
                    content = parsedContent.content;
                }
            } catch (e) {
                content = fileContent;
            }
        }
    }
    // WebSocket error/status format
    else if (data.status === 'websocket_error') {
        isError = true;
        role = 'qa_engineer';
        content = `### WebSocket Error\n\n${data.message || "Connection failed or was interrupted."}`;
    }
    // WebSocket disconnected format
    else if (data.status === 'websocket_disconnected') {
        isError = true;
        role = 'qa_engineer';
        content = `### WebSocket Disconnected\n\nCode ${data.code || 1000}`;
    }
    // Raw JSON format (likely status updates)
    else if (typeof data === 'object' && data.hasOwnProperty('status')) {
        role = 'system';
        
        // Try to create a readable message from the JSON
        if (data.status === 'connected') {
            content = 'Connected to WebSocket server';
        } else if (data.status === 'monitoring') {
            content = `Monitoring ${data.message || 'connection'}`;
            if (data.timestamp) {
                content += ` (${new Date(data.timestamp).toLocaleTimeString()})`;
            }
        } else {
            // Format the raw JSON nicely for display
            content = `Status: ${data.status}\n`;
            if (data.message) content += `Message: ${data.message}\n`;
            
            // Add other fields excluding common metadata
            Object.entries(data).forEach(([key, value]) => {
                if (!['status', 'message', 'timestamp', 'id'].includes(key)) {
                    content += `${key}: ${JSON.stringify(value)}\n`;
                }
            });
        }
    }
    // Unknown format
    else {
        content = typeof data === 'object' ? JSON.stringify(data, null, 2) : String(data);
    }
    
    return { role, content, isError, isReconnecting };
}

/**
 * Append a message to the UI
 * @param {Object} data - The message data
 */
function appendResult(data) {
    debugLog('Received data:', JSON.stringify(data));
    
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;
    
    // Don't process ping messages
    if (data.status === 'ping') {
        debugLog('Received ping message');
        return;
    }
    
    // Extract role and content from different message formats
    const messageInfo = extractRoleAndContent(data);
    if (!messageInfo) {
        debugLog('Could not extract role and content from message');
        return;
    }
    
    const { role, content, isError, isReconnecting } = messageInfo;
    debugLog(`Processing message from ${role}`);
    
    // Create message ID to avoid duplicates
    const messageId = createMessageId(role, content);
    if (processedMessages.has(messageId)) {
        debugLog(`Skipping duplicate message: ${messageId}`);
        return;
    }
    
    // Add to processed messages
    processedMessages.add(messageId);
    
    // Remove loading indicator if present
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
    
    // Create the message element
    const messageElement = createMessage(role, content, isError, isReconnecting);
    
    // Add the message to the chat
    chatMessages.appendChild(messageElement);
    
    // Update team members in the sidebar
    updateTeamMembersList();
    
    // Update document title to show new message
    if (!isReconnecting && !document.hasFocus()) {
        document.title = `MetaGPT - New message from ${role}`;
        
        // After 3 seconds, reset the title
        setTimeout(() => {
            document.title = "MetaGPT Team Chat";
        }, 3000);
    }
    
    // Scroll to the new message
    messageElement.scrollIntoView({ behavior: "smooth" });
    
    debugLog('Message added to chat');
}
