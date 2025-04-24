/**
 * connection.js - WebSocket connection handling for MetaGPT visualization
 */

// WebSocket connection variables
let socket = null;
let isReconnecting = false;
let reconnectAttempts = 0;
let reconnectInterval = null;

// URL for WebSocket connection
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProtocol}//${window.location.host}/ws`;

// Auto-connect when script is loaded - ensures connection even if API checks fail
document.addEventListener('DOMContentLoaded', function() {
    // Wait a short time to let the UI initialize first
    setTimeout(function() {
        // If no connection has been established yet, auto-connect
        if (!socket || socket.readyState !== WebSocket.OPEN) {
            debugLog("No active connection detected, attempting auto-connect");
            autoConnect();
        }
    }, 2000); // Wait 2 seconds after page load
});

/**
 * Auto-connect to a new WebSocket session with a generated ID
 */
function autoConnect() {
    // Generate a unique session ID
    const timestamp = new Date().toISOString().replace(/[-:.]/g, '').substring(0, 14);
    const randomSuffix = Math.random().toString(36).substring(2, 6);
    const newSessionId = `auto_session_${timestamp}_${randomSuffix}`;
    
    debugLog(`Auto-connecting with generated session ID: ${newSessionId}`);
    
    // Update the input field
    const inputField = document.getElementById('input-field');
    if (inputField) {
        inputField.value = newSessionId;
    }
    
    // Connect to this session
    connect(newSessionId);
    
    // Add a status message
    appendResult({
        role: 'system',
        content: `🔄 Automatically connected to new session: ${newSessionId}`
    });
}

/**
 * Check if WebSocket is currently connected
 * @returns {boolean} - Whether the WebSocket is connected
 */
function isConnected() {
    return socket && socket.readyState === WebSocket.OPEN;
}

/**
 * Connect to a job using the job ID
 * This is a wrapper function for connectToJobWebSocket
 * @param {string} jobId - The job ID to connect to
 */
function connect(jobId) {
    debugLog(`Connection attempt initiated for job: ${jobId}`);
    
    // Display connecting status immediately
    updateConnectionStatus('Connecting...');
    
    // Add a message about connection attempt
    appendResult({
        role: 'system',
        content: `Connecting to MetaGPT session ${jobId}...`
    });
    
    // Call the actual connection function
    connectToJobWebSocket(jobId);
}

/**
 * Send a message to the connected WebSocket
 * @param {string} message - The message to send
 */
function sendMessage(message) {
    if (!isConnected()) {
        debugLog("Cannot send message - WebSocket not connected");
        appendResult({
            role: 'system',
            content: 'Not connected to a MetaGPT session. Please enter a job ID to connect.'
        });
        return;
    }
    
    try {
        // Log the outgoing message
        debugLog(`Sending message: ${message}`);
        
        // Send as JSON
        const messageObj = {
            role: 'user',
            content: message
        };
        
        // Send to WebSocket
        socket.send(JSON.stringify(messageObj));
        
        // Add message to UI
        appendResult(messageObj);
    } catch (error) {
        debugLog("Error sending message:", error);
        appendResult({
            role: 'system',
            content: `Failed to send message: ${error.message}`
        });
    }
}

/**
 * Debug function to log WebSocket state
 */
function logSocketState() {
    if (!socket) {
        debugLog("WebSocket status: No socket created");
        return;
    }
    
    let stateDesc = "Unknown";
    switch(socket.readyState) {
        case WebSocket.CONNECTING:
            stateDesc = "CONNECTING";
            break;
        case WebSocket.OPEN:
            stateDesc = "OPEN";
            break;
        case WebSocket.CLOSING:
            stateDesc = "CLOSING";
            break;
        case WebSocket.CLOSED:
            stateDesc = "CLOSED";
            break;
    }
    
    debugLog(`WebSocket status: ${stateDesc} (${socket.readyState})`);
    debugLog(`WebSocket URL: ${socket.url}`);
}

/**
 * Debug function to log the current connection state
 */
function logConnectionStatus() {
    if (!socket) {
        debugLog("WebSocket status: No socket created");
        return;
    }
    
    let stateDesc = "Unknown";
    switch(socket.readyState) {
        case WebSocket.CONNECTING:
            stateDesc = "CONNECTING";
            break;
        case WebSocket.OPEN:
            stateDesc = "OPEN";
            break;
        case WebSocket.CLOSING:
            stateDesc = "CLOSING";
            break;
        case WebSocket.CLOSED:
            stateDesc = "CLOSED";
            break;
    }
    
    debugLog(`WebSocket status: ${stateDesc} (${socket.readyState})`);
    if (socket.url) {
        debugLog(`WebSocket URL: ${socket.url}`);
    }
}

/**
 * Connect to WebSocket for a specific job ID
 * @param {string} jobId - The job ID to connect to
 */
function connectToJobWebSocket(jobId) {
    debugLog(`Connecting to WebSocket for job: ${jobId}`);
    updateConnectionStatus('Connecting...');
    
    // Show loading indicator
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'block';
    }
    
    // Close existing socket if open
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        debugLog('Closing existing WebSocket connection');
        socket.close();
    }
    
    // Clear processed messages to start fresh
    processedMessages.clear();
    
    // Connect to the WebSocket endpoint with job ID
    try {
        const fullWsUrl = `${wsUrl}/${jobId}`;
        debugLog(`WebSocket URL: ${fullWsUrl}`);
        socket = new WebSocket(fullWsUrl);
        
        socket.onopen = function() {
            debugLog('WebSocket connection established');
            updateConnectionStatus('Connected');
            reconnectAttempts = 0;
            isReconnecting = false;
            
            // Clear any pending reconnect interval
            if (reconnectInterval) {
                clearInterval(reconnectInterval);
                reconnectInterval = null;
            }
            
            // Hide loading indicator
            const loadingIndicator = document.getElementById('loading-indicator');
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            
            // Add a system message about the connection
            appendResult({
                role: 'system',
                content: `Connected to job ${jobId}. Loading messages...`
            });
        };
        
        socket.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                appendResult(data);
            } catch (e) {
                debugLog('Error parsing WebSocket message:', e);
                debugLog('Raw message:', event.data);
                
                // Still try to display the message
                appendResult({
                    role: 'system',
                    content: `Error parsing message: ${e.message}\n\nRaw data: ${event.data.substring(0, 100)}...`
                });
            }
        };
        
        socket.onclose = function(event) {
            debugLog(`WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}`);
            updateConnectionStatus('Disconnected');
            
            // Add message about disconnection
            appendResult({
                status: 'websocket_disconnected',
                code: event.code,
                reason: event.reason
            });
            
            // Attempt to reconnect after a delay
            if (!isReconnecting) {
                isReconnecting = true;
                attemptReconnect(jobId);
            }
        };
        
        socket.onerror = function(error) {
            debugLog('WebSocket error:', error);
            updateConnectionStatus('Connection Error');
            
            // Add error message
            appendResult({
                status: 'websocket_error',
                message: 'Connection failed or was interrupted.'
            });
        };
        
    } catch (error) {
        debugLog('Error creating WebSocket:', error);
        updateConnectionStatus('Connection Error');
        
        // Add error message
        appendResult({
            status: 'websocket_error',
            message: `Error: ${error.message}`
        });
        
        // Hide loading indicator
        const loadingIndicator = document.getElementById('loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.style.display = 'none';
        }
    }
}

/**
 * Function to update connection status display
 * @param {string} status - The connection status
 */
function updateConnectionStatus(status) {
    const connectionStatus = document.getElementById('connection-status');
    if (!connectionStatus) return;
    
    // Remove all existing status classes
    connectionStatus.classList.remove('connection-connected', 'connection-closed', 'connection-connecting', 'connection-error');
    
    // Add appropriate class and set text
    let iconClass = 'fa-plug';
    switch(status) {
        case 'Connected':
            connectionStatus.classList.add('connection-connected');
            iconClass = 'fa-plug-circle-check';
            break;
        case 'Disconnected':
            connectionStatus.classList.add('connection-closed');
            iconClass = 'fa-plug-circle-xmark';
            break;
        case 'Connecting...':
            connectionStatus.classList.add('connection-connecting');
            iconClass = 'fa-plug-circle-bolt';
            break;
        case 'Connection Error':
            connectionStatus.classList.add('connection-error');
            iconClass = 'fa-plug-circle-exclamation';
            break;
    }
    
    // Update icon and text
    connectionStatus.innerHTML = `<i class="fas ${iconClass}"></i>${status}`;
    
    debugLog(`Connection status updated: ${status}`);
    logConnectionStatus();
}

/**
 * Attempt to reconnect to WebSocket
 * @param {string} jobId - The job ID to reconnect to
 */
function attemptReconnect(jobId) {
    if (reconnectInterval) {
        clearInterval(reconnectInterval);
    }
    
    reconnectInterval = setInterval(() => {
        if (reconnectAttempts >= userSettings.maxReconnectAttempts) {
            clearInterval(reconnectInterval);
            reconnectInterval = null;
            debugLog('Maximum reconnection attempts reached');
            
            // Add error message
            appendResult({
                role: 'system',
                content: '⚠️ Connection lost. Please refresh the page to try again.'
            });
            
            return;
        }
        
        reconnectAttempts++;
        debugLog(`Attempting to reconnect (${reconnectAttempts}/${userSettings.maxReconnectAttempts})...`);
        updateConnectionStatus(`Reconnecting (${reconnectAttempts}/${userSettings.maxReconnectAttempts})`);
        
        // Add reconnecting message
        appendResult({
            status: 'reconnecting',
            content: `Reconnecting: Attempting to reconnect to job ${jobId}...`
        });
        
        connectToJobWebSocket(jobId);
    }, userSettings.reconnectInterval);
}

/**
 * Function to load job from a URL
 */
function loadJobFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const jobId = urlParams.get('job_id');
    
    if (jobId) {
        debugLog(`Loading job from URL: ${jobId}`);
        document.getElementById('input-field').value = jobId;
        submitPrompt();
    }
}

/**
 * Function to handle form submission
 */
function submitPrompt() {
    const inputField = document.getElementById('input-field');
    const jobId = inputField.value.trim();
    
    if (!jobId) {
        alert('Please enter a job ID or prompt');
        return;
    }
    
    debugLog(`Submitting job ID: ${jobId}`);
    
    // Clear the chat messages
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = '';
    
    // Add loading indicator
    chatMessages.innerHTML = `
        <div class="loading" id="loading-indicator">
            <div class="loading-spinner"></div>
            <div>Connecting to MetaGPT...</div>
        </div>
    `;
    
    // Connect to the WebSocket for this job
    connect(jobId);
    
    // Update URL without reloading the page
    const url = new URL(window.location);
    url.searchParams.set('job_id', jobId);
    window.history.pushState({}, '', url);
    
    // Add to recent jobs
    addToRecentJobs(jobId);
    
    return false; // Prevent form submission
}
