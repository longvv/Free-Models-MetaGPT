/**
 * main.js - Main entry point for the MetaGPT visualization application
 */

// Global variables for workflow data
const workflowData = {
    activeWorkflow: null,
    workflows: [],
    participants: []
};

// Global initialization
document.addEventListener('DOMContentLoaded', async function() {
    debugLog('Application initializing...');
    
    // Load user settings
    loadSettings();
    
    // Set up event listeners
    setupEventListeners();
    
    // Log the state of connection
    debugLog('Current connection state:', socket ? socket.readyState : 'No socket');
    
    // Fetch and load workflows configuration
    try {
        await fetchWorkflows();
        // Update team members list with workflow data
        updateTeamMembersList();
    } catch (error) {
        debugLog('Error loading workflows:', error);
        // If workflows failed to load, still update UI with defaults
        updateTeamMembersList();
    }
    
    // Automatically connect to the MetaGPT API server
    try {
        debugLog('Attempting to initialize API connection...');
        await initializeApiConnection();
        debugLog('API connection initialization complete');
    } catch (error) {
        debugLog('Error initializing API connection:', error);
        appendResult({
            role: 'system',
            content: `Error connecting to API: ${error.message}. Please check your Docker setup.`
        });
    }
    
    // Load job from URL if present
    loadJobFromUrl();
    
    debugLog('Application initialized');
});

/**
 * Fetch available workflows from the server
 * @returns {Promise<Array>} - The list of available workflows
 */
async function fetchWorkflows() {
    debugLog('Fetching workflows...');
    
    try {
        const response = await fetch('/api/workflows');
        if (!response.ok) {
            throw new Error(`Failed to fetch workflows: ${response.status}`);
        }
        
        const workflows = await response.json();
        debugLog(`Received ${workflows.length} workflows from server`);
        
        // Extract all unique participants from all workflows
        const allParticipants = new Set();
        workflows.forEach(workflow => {
            if (workflow.participants && Array.isArray(workflow.participants)) {
                workflow.participants.forEach(participant => {
                    allParticipants.add(participant);
                });
            }
        });
        
        // Store workflows in global variable
        workflowData.workflows = workflows;
        workflowData.participants = Array.from(allParticipants);
        
        // Set the active workflow to the first one by default
        if (workflows.length > 0) {
            workflowData.activeWorkflow = workflows[0].id || workflows[0].name;
            debugLog(`Set active workflow to: ${workflowData.activeWorkflow}`);
        }
        
        debugLog(`Loaded ${workflows.length} workflows with ${workflowData.participants.length} unique participants`);
        return workflows;
    } catch (error) {
        debugLog('Error fetching workflows:', error);
        // Return empty array as fallback
        return [];
    }
}

/**
 * Update the team members list in the UI based on workflow data
 */
function updateTeamMembersList() {
    const teamMembersList = document.getElementById('team-member-list');
    if (!teamMembersList) {
        console.log('Team members list element not found');
        return;
    }
    
    // Clear the list
    teamMembersList.innerHTML = '';
    
    // Get team members from workflowData
    let roles = [];
    
    if (typeof workflowData !== 'undefined' && workflowData.participants && workflowData.participants.length > 0) {
        // Use the participants we extracted during fetchWorkflows
        roles = workflowData.participants;
        console.log(`Using ${roles.length} roles from workflow data`);
    } else if (typeof workflowData !== 'undefined' && workflowData.workflows && workflowData.workflows.length > 0) {
        // Fall back to extracting participants from workflows directly
        const participants = new Set();
        workflowData.workflows.forEach(workflow => {
            if (workflow.participants && Array.isArray(workflow.participants)) {
                workflow.participants.forEach(role => participants.add(role));
            }
        });
        roles = Array.from(participants);
        console.log(`Extracted ${roles.length} roles from workflow data`);
    }
    
    // Use default roles if none are found
    if (roles.length === 0) {
        roles = [
            "requirements_analysis", 
            "domain_expert", 
            "user_advocate", 
            "technical_lead", 
            "architect", 
            "developer", 
            "qa_engineer", 
            "security_expert", 
            "code_review"
        ];
        console.log('No workflow participants found, using default roles');
    }
    
    console.log(`Updated team members list with roles: ${JSON.stringify(roles)}`);
    
    // Create team member elements
    roles.forEach(role => {
        const memberElement = document.createElement('div');
        memberElement.className = 'team-member';
        memberElement.setAttribute('data-role', role);
        
        // Try to get a more user-friendly display name using getRoleDisplayName if it exists
        let displayName = role;
        if (typeof getRoleDisplayName === 'function') {
            displayName = getRoleDisplayName(role);
        } else {
            // Simple formatting if the function doesn't exist
            displayName = role.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }
        
        memberElement.innerHTML = `
            <div class="member-avatar">
                <img src="/visualization/images/placeholder.png" alt="${displayName}" onerror="this.src='/visualization/images/placeholder.png'">
            </div>
            <div class="member-name">${displayName}</div>
        `;
        
        teamMembersList.appendChild(memberElement);
    });
}

/**
 * Initialize the connection to the MetaGPT API server
 */
async function initializeApiConnection() {
    debugLog('Initializing API connection...');
    
    // Show a message that we're attempting to connect to the API
    appendResult({
        role: 'system',
        content: 'Connecting to MetaGPT API server...'
    });
    
    try {
        // Attempt to connect to the API first to check if it's running
        let response = await fetch('/api/status');
        if (!response.ok) {
            throw new Error(`API server returned status: ${response.status}`);
        }
        
        let data = await response.json();
        debugLog('API status:', data);
        
        appendResult({
            role: 'system',
            content: `Connected to MetaGPT API server: ${data.status || 'OK'}`
        });
        
        // Now check for any active jobs
        response = await fetch('/api/active_jobs');
        if (!response.ok) {
            throw new Error(`Failed to get active jobs: ${response.status}`);
        }
        
        let jobs = await response.json();
        debugLog('Active jobs:', jobs);
        
        if (jobs && jobs.length > 0) {
            // If there are active jobs, connect to the first one
            const activeJob = jobs[0];
            debugLog(`Connecting to active job: ${activeJob.id}`);
            
            appendResult({
                role: 'system',
                content: `Active MetaGPT session found: ${activeJob.id}. Connecting...`
            });
            
            // Connect to the WebSocket for this job
            connect(activeJob.id);
        } else {
            debugLog('No active jobs found, will create a new session automatically');
            
            // No active jobs found - generate a new session ID
            const timestamp = new Date().toISOString().replace(/[-:.]/g, '').substring(0, 14);
            const randomSuffix = Math.random().toString(36).substring(2, 6);
            const newJobId = `auto_session_${timestamp}_${randomSuffix}`;
            
            debugLog(`Generated new auto session ID: ${newJobId}`);
            
            appendResult({
                role: 'system',
                content: `Automatically connecting to new session: ${newJobId}`
            });
            
            // Update the input field with the auto-generated ID
            const inputField = document.getElementById('input-field');
            if (inputField) {
                inputField.value = newJobId;
                debugLog('Updated input field with auto session ID');
            }
            
            // Connect to WebSocket with the generated job ID
            debugLog('Calling connect() with auto session ID');
            connect(newJobId);
        }
    } catch (error) {
        debugLog('Error connecting to API:', error);
        appendResult({
            role: 'system',
            content: `Could not connect to MetaGPT API server: ${error.message}. Please check if the server is running.`
        });
        throw error; // Re-throw to allow handling by the caller
    }
}

/**
 * Generate an automatic session ID for WebSocket connection
 * @returns {string} - A unique session ID
 */
function generateAutoSessionId() {
    const timestamp = new Date().toISOString().replace(/[-:.]/g, '').substring(0, 14);
    const randomSuffix = Math.random().toString(36).substring(2, 6);
    return `auto_session_${timestamp}_${randomSuffix}`;
}

/**
 * Initialize the team members list with default values
 * This function ensures team members are always displayed
 */
function initializeTeamMembers() {
    console.log('Initializing team members with defaults');
    
    const teamMembersList = document.getElementById('team-member-list');
    if (!teamMembersList) {
        console.error('Team member list element not found');
        return;
    }
    
    // Clear existing content
    teamMembersList.innerHTML = '';
    
    // Default roles that will always appear
    const defaultRoles = [
        "requirements_analysis", 
        "domain_expert", 
        "user_advocate", 
        "technical_lead", 
        "architect", 
        "developer", 
        "qa_engineer", 
        "security_expert", 
        "code_review"
    ];
    
    // Create team member elements
    defaultRoles.forEach(role => {
        const memberElement = document.createElement('div');
        memberElement.className = 'team-member';
        memberElement.setAttribute('data-role', role);
        
        // Format display name
        const displayName = role.replace(/_/g, ' ')
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
        
        memberElement.innerHTML = `
            <div class="member-avatar">
                <img src="/visualization/images/placeholder.png" alt="${displayName}" onerror="this.src='/visualization/images/placeholder.png'">
            </div>
            <div class="member-name">${displayName}</div>
        `;
        
        teamMembersList.appendChild(memberElement);
    });
    
    console.log('Default team members initialized');
}

// Call this function after the page has loaded
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(initializeTeamMembers, 500);
});

// Window focus event to reset title
window.addEventListener('focus', function() {
    document.title = "MetaGPT Team Chat";
});

// Window resize event to handle responsive layout
window.addEventListener('resize', function() {
    // Adjust layout for small screens
    const chatContainer = document.getElementById('chat-container');
    if (chatContainer) {
        if (window.innerWidth < 768) {
            chatContainer.classList.add('mobile-view');
        } else {
            chatContainer.classList.remove('mobile-view');
        }
    }
});
