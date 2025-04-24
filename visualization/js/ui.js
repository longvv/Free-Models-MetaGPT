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
    const debugButton = document.getElementById('debug-console-button');
    if (debugButton) {
        debugButton.addEventListener('click', toggleDebugConsole);
    }
    
    // Close debug button
    const closeDebugBtn = document.getElementById('close-debug');
    if (closeDebugBtn) {
        closeDebugBtn.addEventListener('click', function() {
            const debugPanel = document.getElementById('debug-panel');
            if (debugPanel) {
                debugPanel.classList.remove('active');
                
                // Also update button state
                const debugButton = document.getElementById('debug-console-button');
                if (debugButton) {
                    debugButton.classList.remove('active');
                }
            }
        });
    }
    
    // ESC key to close modals and panels
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            // Close debug panel if open
            const debugPanel = document.getElementById('debug-panel');
            if (debugPanel && debugPanel.classList.contains('active')) {
                debugPanel.classList.remove('active');
                const debugButton = document.getElementById('debug-console-button');
                if (debugButton) debugButton.classList.remove('active');
                return;
            }
            
            // Close config modal if open
            closeConfigModal();
        }
    });

    // Pass initial log message to debug console
    debugLog('Visualization UI initialized - Working with containerized MetaGPT API');
    debugLog('Connected to workspace directory at /workspace');
    debugLog('Ready to access logs from both /logs and /workspace directories');
}

/**
 * Function to open the configuration modal
 */
function openConfigModal() {
    const modal = document.getElementById('config-modal');
    if (modal) {
        // Directly add the active class to show the modal
        modal.classList.add('active');
        
        // Also add modal-open class to body to prevent scrolling
        document.body.classList.add('modal-open');
        
        console.log('Config modal opened');
    } else {
        console.error('Config modal element not found');
    }
}

/**
 * Function to close the configuration modal
 */
function closeConfigModal() {
    const modal = document.getElementById('config-modal');
    if (modal) {
        // Remove the active class to hide the modal
        modal.classList.remove('active');
        
        // Also remove modal-open class from body
        document.body.classList.remove('modal-open');
        
        console.log('Config modal closed');
    }
}

/**
 * Function to toggle the debug console
 */
function toggleDebugConsole() {
    const debugPanel = document.getElementById('debug-panel');
    const debugButton = document.getElementById('debug-console-button');
    
    if (!debugPanel) {
        console.error('Debug panel element not found');
        return;
    }
    
    // Toggle the active class to show/hide the panel
    if (debugPanel.classList.contains('active')) {
        debugPanel.classList.remove('active');
        console.log('Debug panel hidden');
    } else {
        debugPanel.classList.add('active');
        console.log('Debug panel shown');
    }
    
    // Update button state
    if (debugButton) {
        debugButton.classList.toggle('active');
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
        panel.classList.add('visible');
        debugLog(`Opened panel: ${panelId}`);
    }
}

/**
 * Function to close a panel
 * @param {string} panelId - The ID of the panel to close
 */
function closePanel(panelId) {
    const panel = document.getElementById(panelId);
    if (panel) {
        panel.classList.remove('visible');
        debugLog(`Closed panel: ${panelId}`);
    }
}

/**
 * Function to fetch and display logs
 */
async function fetchAndDisplayLogs() {
    // Close other panels first
    closePanel('debug-console');
    
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
 * Map role name to image filename
 * @param {string} role - The role name
 * @returns {string} - The image filename
 */
function getRoleImageFilename(role) {
    // Map long role names to their image filenames
    const roleMap = {
        'product_manager': 'pm',
        'qa_engineer': 'qa',
        'requirements_analysis': 'requirements',
        'technical_lead': 'technical_lead'
    };
    
    // Use the mapping if available, otherwise just use the role itself
    return roleMap[role.toLowerCase()] || role.toLowerCase();
}

/**
 * Update team members list in the sidebar
 * This should be called on page load and whenever messages are received
 */
function updateTeamMembersList() {
    const teamMemberList = document.getElementById('team-member-list');
    if (!teamMemberList) return;
    
    // Check if we have a workflow file available
    const hasWorkflow = workflowData.workflows && workflowData.workflows.length > 0;
    
    // If no workflow is available, hide the team members list
    if (!hasWorkflow) {
        teamMemberList.innerHTML = '<div class="empty-state">No workflow loaded</div>';
        return;
    }
    
    // Get team participants
    const currentRoles = getTeamParticipants().join(',');
    if (teamMemberList.getAttribute('data-roles') === currentRoles) {
        // No change in roles, skip update
        return;
    }
    
    // Get current active roles from all messages
    const roles = new Set(getTeamParticipants());
    
    // No roles found, show empty state
    if (roles.size === 0) {
        teamMemberList.innerHTML = '<div class="empty-state">No team members found</div>';
    } else {
        // Build team member list
        let html = '';
        Array.from(roles).forEach(role => {
            html += `
                <div class="team-member-item">
                    <div class="team-member-avatar">
                        ${generateAvatarHtml(role)}
                    </div>
                    <div class="team-member-name">${getRoleDisplayName(role)}</div>
                </div>
            `;
        });
        
        teamMemberList.innerHTML = html;
        teamMemberList.setAttribute('data-roles', currentRoles);
        debugLog('Updated team members list with roles:', Array.from(roles));
    }
    
    // Force a repaint to ensure scrollbar appears correctly
    const scrollContainer = document.querySelector('.team-member-list-scroll');
    if (scrollContainer) {
        // Force scrollbar to appear if content exceeds container
        setTimeout(() => {
            if (teamMemberList.offsetHeight > scrollContainer.offsetHeight) {
                scrollContainer.style.overflowY = 'scroll';
            } else {
                scrollContainer.style.overflowY = 'auto';
            }
        }, 50);
    }
}

/**
 * Function to log debug messages
 */
function debugLog(...args) {
    console.log('[DEBUG]', ...args);
    
    // Format message for debug panel
    const debugMessages = document.getElementById('debug-messages');
    if (debugMessages) {
        const timestamp = new Date().toLocaleTimeString();
        const message = document.createElement('div');
        message.className = 'debug-message';
        
        const timestampSpan = document.createElement('span');
        timestampSpan.className = 'debug-timestamp';
        timestampSpan.textContent = timestamp;
        message.appendChild(timestampSpan);
        
        const content = document.createElement('span');
        content.className = 'debug-content';
        content.textContent = args.map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg);
                } catch (e) {
                    return String(arg);
                }
            }
            return String(arg);
        }).join(' ');
        message.appendChild(content);
        
        debugMessages.appendChild(message);
        debugMessages.scrollTop = debugMessages.scrollHeight;
    }
}

/**
 * Check if debug mode is enabled
 * @returns {boolean} - Whether debug mode is enabled
 */
function isDebugMode() {
    return localStorage.getItem('debug_mode') === 'true' || true; // Always true for now
}

/**
 * Function to handle close panel button click
 */
function handleClosePanelClick() {
    const panel = this.closest('.panel');
    if (panel) {
        panel.classList.remove('visible');
        
        // Also update any related button state
        if (panel.id === 'debug-console') {
            const debugButton = document.getElementById('debug-console-button');
            if (debugButton) {
                debugButton.classList.remove('active');
            }
        }
    }
}

/**
 * Function to submit the prompt
 */
function submitPrompt() {
    const inputField = document.getElementById('input-field');
    if (!inputField) return;
    
    const input = inputField.value.trim();
    if (!input) return;
    
    // Clear input field
    inputField.value = '';
    
    // Focus back on input field
    inputField.focus();
    
    // Check if we're connected
    if (isConnected()) {
        // Send the message
        sendMessage(input);
    } else {
        // Try to connect using input as job ID
        connect(input);
    }
}

/**
 * Generate a consistent color based on a string
 * @param {string} str - The string to generate a color for
 * @returns {string} - A hex color code
 */
function generateColorFromString(str) {
    // Default colors for known roles to ensure consistency
    const roleColors = {
        'product_manager': '#4A6FDC',  // Blue
        'pm': '#4A6FDC',               // Blue
        'architect': '#E94E77',        // Pink
        'engineer': '#53A548',         // Green
        'programmer': '#53A548',       // Green
        'coder': '#53A548',            // Green
        'qa_engineer': '#F1AB41',      // Yellow
        'qa': '#F1AB41',               // Yellow
        'reviewer': '#9B59B6',         // Purple
        'requirements_analysis': '#2C9FA7', // Teal
        'user': '#7D7C7C',             // Gray
        'technical_lead': '#D95829',   // Orange
        'system': '#7D7C7C'            // Gray
    };
    
    const normalizedStr = str.toLowerCase();
    
    // Return predefined color if available
    if (roleColors[normalizedStr]) {
        return roleColors[normalizedStr];
    }
    
    // Otherwise generate a color based on string
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    // Ensure the color isn't too light (min 40% brightness)
    const h = hash % 360;
    const s = 65 + (hash % 35); // 65-100%
    const l = 40 + (hash % 20); // 40-60%
    
    return `hsl(${h}, ${s}%, ${l}%)`;
}

/**
 * Get avatar initials from a role name
 * @param {string} role - The role name
 * @returns {string} - The initials (1-2 characters)
 */
function getInitialsFromRole(role) {
    if (!role) return '?';
    
    // Use display name to get more meaningful initials
    const displayName = getRoleDisplayName(role);
    
    // Split on spaces, underscores, or camelCase
    const words = displayName
        .replace(/([a-z])([A-Z])/g, '$1 $2') // Split camelCase
        .replace(/_/g, ' ') // Replace underscores with spaces
        .split(' ');
    
    // For single word, use first two letters
    if (words.length === 1) {
        return words[0].substring(0, 2).toUpperCase();
    }
    
    // For multiple words, use first letter of each of the first two words
    return (words[0][0] + (words[1] ? words[1][0] : '')).toUpperCase();
}

/**
 * Generate an HTML avatar element
 * @param {string} role - The role name
 * @param {boolean} large - Whether to make the avatar large
 * @returns {string} - HTML for the avatar
 */
function generateAvatarHtml(role, large = false) {
    const color = generateColorFromString(role);
    const initials = getInitialsFromRole(role);
    const size = large ? 'large-avatar' : '';
    
    return `
        <div class="generated-avatar ${size}" style="background-color: ${color}">
            <span>${initials}</span>
        </div>
    `;
}

/**
 * Create a team avatar element
 * @param {string} role - The role name
 * @param {boolean} large - Whether to use a large avatar
 * @returns {HTMLElement} - The avatar element
 */
function createAvatarElement(role, large = false) {
    const color = generateColorFromString(role);
    const initials = getInitialsFromRole(role);
    const size = large ? 'large-avatar' : '';
    
    const avatar = document.createElement('div');
    avatar.className = `generated-avatar ${size}`;
    avatar.style.backgroundColor = color;
    
    const span = document.createElement('span');
    span.textContent = initials;
    avatar.appendChild(span);
    
    return avatar;
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
 * Fetch available workflows and their participants
 * @returns {Promise<Array>} - Promise resolving to workflow data
 */
async function fetchWorkflows() {
    try {
        debugLog('Fetching workflows...');
        const response = await fetch('/api/workflows');
        if (!response.ok) {
            throw new Error(`Failed to fetch workflows: ${response.status}`);
        }
        
        const workflows = await response.json();
        workflowData.workflows = workflows;
        
        debugLog(`Received ${workflows.length} workflows from server`);
        
        if (workflows.length === 0) {
            debugLog('No workflows found, using default roles');
            setDefaultWorkflowData();
            return [];
        }
        
        // Extract all unique participants from all workflows
        const allParticipants = new Set();
        workflows.forEach(workflow => {
            workflow.participants.forEach(participant => {
                allParticipants.add(participant);
            });
        });
        
        workflowData.participants = Array.from(allParticipants).sort();
        
        // If we have workflows, set the first one as active by default
        if (workflows.length > 0) {
            workflowData.activeWorkflow = workflows[0];
            debugLog(`Set active workflow to: ${workflows[0].name}`);
        }
        
        debugLog(`Loaded ${workflows.length} workflows with ${workflowData.participants.length} unique participants`);
        return workflows;
    } catch (error) {
        debugLog('Error fetching workflows:', error);
        setDefaultWorkflowData();
        return [];
    }
}

/**
 * Set default workflow data when no workflows are available
 */
function setDefaultWorkflowData() {
    // We don't set default roles anymore - we only show roles from actual workflow files
    workflowData.workflows = [];
    workflowData.activeWorkflow = null;
    workflowData.participants = [];
    
    debugLog('Set empty workflow data - waiting for workflow file');
}

/**
 * Get team participants from workflow or return empty array
 * @returns {Array} - List of participant roles
 */
function getTeamParticipants() {
    // If we have an active workflow with participants, use those
    if (workflowData.activeWorkflow && workflowData.activeWorkflow.participants.length > 0) {
        return workflowData.activeWorkflow.participants;
    }
    
    // If we have any participants from any workflow, use those
    if (workflowData.participants.length > 0) {
        return workflowData.participants;
    }
    
    // Return empty array if no workflow is available
    return [];
}

// Store workflow data globally for access
let workflowData = {
    activeWorkflow: null,
    workflows: [],
    participants: []
};
