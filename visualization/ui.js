/**
 * ui.js - UI functionality for MetaGPT visualization
 */

/**
 * Function to set up event listeners
 */
function setupEventListeners() {
    // Get form element
    const form = document.getElementById('prompt-form');
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            submitPrompt();
        });
    }
    
    // Configuration button
    const configButton = document.getElementById('config-button');
    if (configButton) {
        configButton.addEventListener('click', openConfigModal);
    }
    
    // Config form submit
    const configForm = document.getElementById('config-form');
    if (configForm) {
        configForm.addEventListener('submit', function(e) {
            e.preventDefault();
            saveSettings();
        });
    }
    
    // Config close button
    const closeModalButton = document.getElementById('close-modal');
    if (closeModalButton) {
        closeModalButton.addEventListener('click', closeConfigModal);
    }
    
    // Reset settings button
    const resetSettingsButton = document.getElementById('reset-settings');
    if (resetSettingsButton) {
        resetSettingsButton.addEventListener('click', resetSettings);
    }
    
    // Clear messages button
    const clearMessagesButton = document.getElementById('clear-messages');
    if (clearMessagesButton) {
        clearMessagesButton.addEventListener('click', clearMessages);
    }
    
    // Debug console button
    const debugConsoleButton = document.getElementById('debug-console-button');
    if (debugConsoleButton) {
        debugConsoleButton.addEventListener('click', toggleDebugConsole);
    }
    
    // View logs button
    const viewLogsButton = document.getElementById('view-logs-button');
    if (viewLogsButton) {
        viewLogsButton.addEventListener('click', fetchAndDisplayLogs);
    }
    
    // Team diagram button
    const teamDiagramButton = document.getElementById('team-diagram-button');
    if (teamDiagramButton) {
        teamDiagramButton.addEventListener('click', toggleTeamDiagram);
    }
    
    // Close buttons for panels
    document.querySelectorAll('.close-panel').forEach(button => {
        button.addEventListener('click', function() {
            const panelId = this.closest('.panel').id;
            closePanel(panelId);
        });
    });
    
    // Set up keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl+Enter to submit
        if (e.ctrlKey && e.key === 'Enter') {
            const inputField = document.getElementById('input-field');
            if (document.activeElement === inputField) {
                submitPrompt();
            }
        }
        
        // Escape to close modals
        if (e.key === 'Escape') {
            closeConfigModal();
            closePanel('debug-console');
            closePanel('logs-panel');
            closePanel('team-diagram');
        }
    });
}

/**
 * Function to open the configuration modal
 */
function openConfigModal() {
    const modal = document.getElementById('config-modal');
    if (modal) {
        modal.classList.add('active');
        document.body.classList.add('modal-open');
        updateRecentJobsList();
    }
}

/**
 * Function to close the configuration modal
 */
function closeConfigModal() {
    const modal = document.getElementById('config-modal');
    if (modal) {
        modal.classList.remove('active');
        document.body.classList.remove('modal-open');
    }
}

/**
 * Function to toggle the debug console
 */
function toggleDebugConsole() {
    const debugConsole = document.getElementById('debug-console');
    if (debugConsole) {
        if (debugConsole.classList.contains('active')) {
            closePanel('debug-console');
        } else {
            openPanel('debug-console');
        }
    }
}

/**
 * Function to toggle the team diagram
 */
function toggleTeamDiagram() {
    const teamDiagram = document.getElementById('team-diagram');
    if (teamDiagram) {
        if (teamDiagram.classList.contains('active')) {
            closePanel('team-diagram');
        } else {
            openPanel('team-diagram');
            renderTeamDiagram();
        }
    }
}

/**
 * Function to clear all messages
 */
function clearMessages() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        if (confirm('Are you sure you want to clear all messages?')) {
            chatMessages.innerHTML = '';
            processedMessages.clear();
        }
    }
}

/**
 * Function to open a panel
 * @param {string} panelId - The ID of the panel to open
 */
function openPanel(panelId) {
    const panel = document.getElementById(panelId);
    if (panel) {
        panel.classList.add('active');
    }
}

/**
 * Function to close a panel
 * @param {string} panelId - The ID of the panel to close
 */
function closePanel(panelId) {
    const panel = document.getElementById(panelId);
    if (panel) {
        panel.classList.remove('active');
    }
}

/**
 * Function to fetch and display logs
 */
async function fetchAndDisplayLogs() {
    // Show the logs panel
    openPanel('logs-panel');
    
    // Update UI to show loading
    const logsContainer = document.getElementById('logs-container');
    if (!logsContainer) return;
    
    logsContainer.innerHTML = '<div class="loading"><div class="loading-spinner"></div><div>Loading logs...</div></div>';
    
    try {
        // Fetch available logs
        const response = await fetch('/visualization/logs');
        
        if (!response.ok) {
            throw new Error(`Failed to fetch logs: ${response.status} ${response.statusText}`);
        }
        
        const logs = await response.json();
        
        if (logs.length === 0) {
            logsContainer.innerHTML = '<div class="empty-state">No logs available</div>';
            return;
        }
        
        // Create the logs list
        logsContainer.innerHTML = `
            <div class="logs-list">
                <h3>Available Logs</h3>
                <div class="logs-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Log Name</th>
                                <th>Date</th>
                                <th>Size</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="logs-table-body">
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="log-content" id="log-content">
                <div class="empty-state">Select a log file to view</div>
            </div>
        `;
        
        // Populate the logs table
        const logsTableBody = document.getElementById('logs-table-body');
        logs.forEach(log => {
            const row = document.createElement('tr');
            
            // Format date
            const date = new Date(log.modified);
            const formattedDate = `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
            
            // Format size
            const formattedSize = formatFileSize(log.size);
            
            row.innerHTML = `
                <td class="log-name">${log.name}</td>
                <td>${formattedDate}</td>
                <td>${formattedSize}</td>
                <td>
                    <button class="view-log-btn" data-log-path="${log.path}">View</button>
                </td>
            `;
            
            logsTableBody.appendChild(row);
        });
        
        // Add event listeners to view buttons
        document.querySelectorAll('.view-log-btn').forEach(button => {
            button.addEventListener('click', async function() {
                const logPath = this.getAttribute('data-log-path');
                await viewLog(logPath);
            });
        });
    } catch (error) {
        debugLog('Error fetching logs:', error);
        logsContainer.innerHTML = `<div class="error">Error loading logs: ${error.message}</div>`;
    }
}

/**
 * Function to view a log file
 * @param {string} logPath - The path to the log file
 */
async function viewLog(logPath) {
    const logContent = document.getElementById('log-content');
    if (!logContent) return;
    
    // Show loading
    logContent.innerHTML = '<div class="loading"><div class="loading-spinner"></div><div>Loading log...</div></div>';
    
    try {
        // Fetch log content
        const response = await fetch(`/visualization/logs/view?path=${encodeURIComponent(logPath)}`);
        
        if (!response.ok) {
            throw new Error(`Failed to fetch log: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (!data.content) {
            logContent.innerHTML = '<div class="empty-state">Log file is empty</div>';
            return;
        }
        
        // Create the log viewer
        logContent.innerHTML = `
            <div class="log-header">
                <h3>${data.name}</h3>
                <div class="log-actions">
                    <button id="copy-log-btn">Copy to Clipboard</button>
                </div>
            </div>
            <div class="log-viewer">
                <pre class="log-text">${data.content}</pre>
            </div>
        `;
        
        // Add event listener to copy button
        document.getElementById('copy-log-btn').addEventListener('click', function() {
            const logText = document.querySelector('.log-text').textContent;
            navigator.clipboard.writeText(logText)
                .then(() => {
                    this.textContent = 'Copied!';
                    setTimeout(() => {
                        this.textContent = 'Copy to Clipboard';
                    }, 2000);
                })
                .catch(err => {
                    debugLog('Failed to copy:', err);
                    this.textContent = 'Copy Failed';
                    setTimeout(() => {
                        this.textContent = 'Copy to Clipboard';
                    }, 2000);
                });
        });
    } catch (error) {
        debugLog('Error viewing log:', error);
        logContent.innerHTML = `<div class="error">Error loading log: ${error.message}</div>`;
    }
}

/**
 * Function to format file size
 * @param {number} bytes - The size in bytes
 * @returns {string} - The formatted size
 */
function formatFileSize(bytes) {
    if (bytes < 1024) {
        return `${bytes} B`;
    } else if (bytes < 1024 * 1024) {
        return `${(bytes / 1024).toFixed(1)} KB`;
    } else {
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
}

/**
 * Function to render the team diagram
 */
function renderTeamDiagram() {
    const diagramContainer = document.getElementById('team-diagram-container');
    if (!diagramContainer) return;
    
    // Get all roles from messages
    const roles = new Set();
    document.querySelectorAll('.message').forEach(msg => {
        const role = msg.className.split(' ')[1]; // Get second class which is the role
        if (role && !['error', 'reconnecting', 'new-message-highlight'].includes(role)) {
            roles.add(role);
        }
    });
    
    // If no roles found, show empty state
    if (roles.size === 0) {
        diagramContainer.innerHTML = '<div class="empty-state">No team members to display. Connect to a job first.</div>';
        return;
    }
    
    // Create the diagram container
    diagramContainer.innerHTML = `
        <div class="diagram-controls">
            <button id="sequence-view-btn" class="active">Sequence View</button>
            <button id="team-view-btn">Team View</button>
        </div>
        <div id="sequence-diagram" class="diagram active"></div>
        <div id="team-diagram-view" class="diagram"></div>
    `;
    
    // Create the sequence diagram
    const sequenceDiagram = document.getElementById('sequence-diagram');
    const teamDiagramView = document.getElementById('team-diagram-view');
    
    // Create sequence diagram
    createSequenceDiagram(sequenceDiagram, Array.from(roles));
    
    // Create team diagram
    createTeamDiagram(teamDiagramView, Array.from(roles));
    
    // Add event listeners to view buttons
    document.getElementById('sequence-view-btn').addEventListener('click', function() {
        this.classList.add('active');
        document.getElementById('team-view-btn').classList.remove('active');
        document.getElementById('sequence-diagram').classList.add('active');
        document.getElementById('team-diagram-view').classList.remove('active');
    });
    
    document.getElementById('team-view-btn').addEventListener('click', function() {
        this.classList.add('active');
        document.getElementById('sequence-view-btn').classList.remove('active');
        document.getElementById('team-diagram-view').classList.add('active');
        document.getElementById('sequence-diagram').classList.remove('active');
    });
}

/**
 * Create a sequence diagram
 * @param {HTMLElement} container - The container element
 * @param {Array} roles - The roles to include in the diagram
 */
function createSequenceDiagram(container, roles) {
    let html = '<div class="sequence-diagram">';
    
    // Create header with all roles
    html += '<div class="sequence-header">';
    roles.forEach(role => {
        html += `<div class="sequence-role">${getRoleDisplayName(role)}</div>`;
    });
    html += '</div>';
    
    // Create lifelines
    html += '<div class="sequence-body">';
    roles.forEach(() => {
        html += '<div class="sequence-lifeline"></div>';
    });
    
    // Create messages (simplified)
    let messages = '';
    document.querySelectorAll('.message').forEach(msg => {
        const role = msg.className.split(' ')[1];
        if (roles.includes(role)) {
            const fromIndex = roles.indexOf(role);
            // Choose a random target different from the source
            let toIndex;
            do {
                toIndex = Math.floor(Math.random() * roles.length);
            } while (toIndex === fromIndex && roles.length > 1);
            
            const content = msg.querySelector('.content').textContent.substring(0, 20) + '...';
            
            if (fromIndex < toIndex) {
                messages += `<div class="sequence-message right" style="grid-column: ${fromIndex + 1} / ${toIndex + 2};">${content}</div>`;
            } else {
                messages += `<div class="sequence-message left" style="grid-column: ${toIndex + 1} / ${fromIndex + 2};">${content}</div>`;
            }
        }
    });
    
    html += messages;
    html += '</div>'; // Close sequence-body
    html += '</div>'; // Close sequence-diagram
    
    container.innerHTML = html;
}

/**
 * Create a team diagram
 * @param {HTMLElement} container - The container element
 * @param {Array} roles - The roles to include in the diagram
 */
function createTeamDiagram(container, roles) {
    let html = '<div class="team-diagram">';
    
    roles.forEach(role => {
        html += `
            <div class="team-member">
                <div class="member-avatar">
                    <img src="images/${role.toLowerCase()}.png" alt="${role}" onerror="this.src='images/placeholder.png'">
                </div>
                <div class="member-name">${getRoleDisplayName(role)}</div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

/**
 * Get a user-friendly display name for a role
 * @param {string} role - The role
 * @returns {string} - The display name
 */
function getRoleDisplayName(role) {
    switch(role.toLowerCase()) {
        case 'product_manager':
        case 'pm':
            return 'Product Manager';
        case 'architect':
            return 'Architect';
        case 'engineer':
        case 'programmer':
        case 'coder':
            return 'Engineer';
        case 'qa_engineer':
        case 'qa':
            return 'QA Engineer';
        case 'reviewer':
            return 'Reviewer';
        case 'requirements_analysis':
            return 'Requirements Analyst';
        case 'user':
            return 'User';
        case 'technical_lead':
            return 'Technical Lead';
        default:
            return role || 'System';
    }
}

/**
 * Function to log debug messages
 */
function debugLog(...args) {
    // Always log errors to debug console for UI debug purposes
    const debugConsole = document.getElementById('debug-messages');
    if (debugConsole) {
        const message = args.map(arg => 
            typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)
        ).join(' ');
        
        const messageElement = document.createElement('div');
        messageElement.className = 'debug-message';
        messageElement.innerHTML = `<span class="timestamp">${new Date().toLocaleTimeString()}</span> ${message}`;
        
        debugConsole.appendChild(messageElement);
        
        // Scroll to bottom
        debugConsole.scrollTop = debugConsole.scrollHeight;
    }
    
    // Also log to browser console based on log level
    console.log(...args);
}
