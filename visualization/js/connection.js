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
 * Update connection status in the UI
 * @param {string} status - The connection status
 */
function updateConnectionStatus(status) {
    const statusElement = document.getElementById('connection-status');
    if (!statusElement) return;
    
    statusElement.className = 'connection-status';
    
    switch(status) {
        case 'Connected':
            statusElement.innerHTML = '<i class="fas fa-plug"></i>Connected';
            statusElement.classList.add('connection-open');
            break;
        case 'Connecting...':
            statusElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i>Connecting...';
            statusElement.classList.add('connection-connecting');
            break;
        case 'Disconnected':
            statusElement.innerHTML = '<i class="fas fa-plug-circle-xmark"></i>Disconnected';
            statusElement.classList.add('connection-closed');
            break;
        case 'Connection Error':
            statusElement.innerHTML = '<i class="fas fa-triangle-exclamation"></i>Connection Error';
            statusElement.classList.add('connection-closed');
            break;
        default:
            statusElement.innerHTML = '<i class="fas fa-plug"></i>' + status;
            if (status.includes('Reconnecting')) {
                statusElement.classList.add('connection-connecting');
            } else {
                statusElement.classList.add('connection-closed');
            }
    }
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
    connectToJobWebSocket(jobId);
    
    // Update URL without reloading the page
    const url = new URL(window.location);
    url.searchParams.set('job_id', jobId);
    window.history.pushState({}, '', url);
    
    // Add to recent jobs
    addToRecentJobs(jobId);
    
    return false; // Prevent form submission
}
