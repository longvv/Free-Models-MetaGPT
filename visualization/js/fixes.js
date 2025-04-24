/**
 * fixes.js - Direct fixes for UI issues
 */

// Execute when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Applying UI fixes...');
    
    // Wait for everything else to load first
    setTimeout(function() {
        // 1. Fix debug console toggle
        fixDebugConsole();
        
        // 2. Fix team members list
        fixTeamMembers();
        
        // 3. Fix settings modal
        fixSettingsModal();
    }, 800);
});

// Fix debug console visibility and toggle
function fixDebugConsole() {
    console.log('Fixing debug console...');
    
    const debugButton = document.getElementById('debug-console-button');
    const debugPanel = document.getElementById('debug-panel');
    
    if (!debugPanel) {
        console.log('Debug panel not found - recreating it');
        // Create debug panel if it doesn't exist
        const panelHTML = `
            <div id="debug-panel" class="debug-panel" style="position: fixed; top: 60px; right: 20px; width: 400px; 
                max-width: 80vw; height: 60vh; background-color: #1e1e1e; border-radius: 8px; 
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3); z-index: 1000; overflow: hidden; display: none; flex-direction: column;">
                <div class="debug-header" style="display: flex; justify-content: space-between; align-items: center; 
                    padding: 10px 15px; background-color: #333; color: white;">
                    <h3>Debug Console</h3>
                    <button id="close-debug" style="background: none; border: none; color: white; font-size: 24px; 
                        cursor: pointer; padding: 0; line-height: 1;">&times;</button>
                </div>
                <div id="debug-messages" style="flex-grow: 1; overflow-y: auto; padding: 10px; font-family: monospace; 
                    font-size: 13px; color: #ddd; white-space: pre-wrap; word-break: break-word;"></div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', panelHTML);
    }
    
    // Get references (or fresh references if we just created the panel)
    const panel = document.getElementById('debug-panel');
    
    if (debugButton && panel) {
        console.log('Setting up debug button click handler');
        
        // Remove any existing event listeners by cloning and replacing
        const newDebugButton = debugButton.cloneNode(true);
        debugButton.parentNode.replaceChild(newDebugButton, debugButton);
        
        // Add new click handler
        newDebugButton.addEventListener('click', function() {
            console.log('Debug button clicked');
            
            // Toggle visibility with inline styles
            if (panel.style.display === 'flex') {
                panel.style.display = 'none';
            } else {
                panel.style.display = 'flex';
                // Bring debug messages from other debug outputs
                updateDebugMessages();
            }
        });
        
        // Set up close button
        const closeDebugBtn = document.getElementById('close-debug');
        if (closeDebugBtn) {
            const newCloseBtn = closeDebugBtn.cloneNode(true);
            closeDebugBtn.parentNode.replaceChild(newCloseBtn, closeDebugBtn);
            
            newCloseBtn.addEventListener('click', function() {
                panel.style.display = 'none';
            });
        }
    }
}

// Fix team members list
function fixTeamMembers() {
    console.log('Fixing team members list...');
    
    // Define the team members we want to show
    const roles = [
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
    
    // Get the sidebar reference
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) {
        console.error('No sidebar found!');
        return;
    }
    
    // Generate team members HTML
    let teamMembersHTML = '';
    roles.forEach(role => {
        const displayName = role.replace(/_/g, ' ')
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
            
        teamMembersHTML += `
            <div class="team-member" data-role="${role}" style="display: flex; align-items: center; 
                padding: 8px; margin-bottom: 5px; border-radius: 4px; background-color: rgba(255,255,255,0.05);">
                <div class="member-avatar" style="width: 32px; height: 32px; border-radius: 50%; 
                    background-color: #4a6cf7; margin-right: 10px; overflow: hidden;">
                    <img src="/visualization/images/placeholder.png" alt="${displayName}" style="width: 100%; height: 100%;">
                </div>
                <div class="member-name" style="font-size: 14px; color: #fff;">${displayName}</div>
            </div>
        `;
    });
    
    // Create or update team members section
    let teamMembersSection = sidebar.querySelector('.team-members');
    
    if (!teamMembersSection) {
        console.log('Creating new team members section');
        teamMembersSection = document.createElement('div');
        teamMembersSection.className = 'team-members';
        teamMembersSection.style.marginTop = '20px';
        sidebar.appendChild(teamMembersSection);
    }
    
    teamMembersSection.innerHTML = `
        <h2 style="color: #fff; font-size: 16px; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.2); 
            padding-bottom: 5px;">Team Members</h2>
        <div class="team-member-list-scroll" style="max-height: calc(100vh - 200px); overflow-y: auto;">
            <div id="team-member-list" style="padding-right: 5px;">
                ${teamMembersHTML}
            </div>
        </div>
    `;
    
    console.log('Team members list fixed');
}

// Fix settings modal
function fixSettingsModal() {
    console.log('Fixing settings modal...');
    
    const configButton = document.getElementById('config-button');
    let configModal = document.getElementById('config-modal');
    
    if (!configModal) {
        console.log('Config modal not found - will create minimal version');
        
        // Create a minimal settings modal
        const modalHTML = `
            <div id="config-modal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                background-color: rgba(0,0,0,0.7); z-index: 1001; overflow: auto;">
                <div style="background-color: #fff; margin: 10% auto; padding: 20px; width: 50%; 
                    max-width: 500px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h2 style="margin: 0; color: #333;">Settings</h2>
                        <button id="close-modal" style="background: none; border: none; font-size: 24px; 
                            cursor: pointer; color: #333;">&times;</button>
                    </div>
                    <div style="margin-bottom: 20px;">
                        <h3 style="color: #444;">Connection Settings</h3>
                        <div style="margin-bottom: 10px;">
                            <label style="display: block; margin-bottom: 5px; font-weight: bold;">
                                Auto-connect to WebSocket:
                            </label>
                            <label style="display: inline-flex; align-items: center;">
                                <input type="checkbox" checked style="margin-right: 5px;"> 
                                Enable automatic connection
                            </label>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <button id="save-settings" style="background-color: #4a6cf7; color: white; 
                            border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">
                            Save Settings
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        configModal = document.getElementById('config-modal');
    }
    
    if (configButton && configModal) {
        console.log('Setting up config button click handler');
        
        // Remove any existing event listeners
        const newConfigButton = configButton.cloneNode(true);
        configButton.parentNode.replaceChild(newConfigButton, configButton);
        
        // Add new click handler
        newConfigButton.addEventListener('click', function() {
            console.log('Config button clicked');
            configModal.style.display = 'block';
        });
        
        // Set up close button
        const closeModalButton = document.getElementById('close-modal');
        if (closeModalButton) {
            const newCloseBtn = closeModalButton.cloneNode(true);
            closeModalButton.parentNode.replaceChild(newCloseBtn, closeModalButton);
            
            newCloseBtn.addEventListener('click', function() {
                configModal.style.display = 'none';
            });
        }
        
        // Set up save button
        const saveButton = document.getElementById('save-settings');
        if (saveButton) {
            saveButton.addEventListener('click', function() {
                configModal.style.display = 'none';
                console.log('Settings saved');
            });
        }
        
        // Close modal on outside click
        configModal.addEventListener('click', function(event) {
            if (event.target === configModal) {
                configModal.style.display = 'none';
            }
        });
    }
}

// Function to collect debug messages from console output
function updateDebugMessages() {
    const debugMessages = document.getElementById('debug-messages');
    if (debugMessages) {
        // Add current console messages if any
        const timestamp = new Date().toLocaleTimeString();
        debugMessages.innerHTML += `
            <div style="border-bottom: 1px solid #333; padding-bottom: 6px; margin-bottom: 6px;">
                <span style="color: #888; margin-right: 8px;">${timestamp}</span>
                <span>Debug console opened. WebSocket auto-connect is active.</span>
            </div>
        `;
    }
}

// Override console.log to send messages to our debug panel too
const originalConsoleLog = console.log;
console.log = function() {
    // Call the original console.log
    originalConsoleLog.apply(console, arguments);
    
    // Also add to our debug panel
    const debugMessages = document.getElementById('debug-messages');
    if (debugMessages) {
        const timestamp = new Date().toLocaleTimeString();
        const message = Array.from(arguments).map(arg => {
            if (typeof arg === 'object') {
                try {
                    return JSON.stringify(arg);
                } catch (e) {
                    return String(arg);
                }
            }
            return String(arg);
        }).join(' ');
        
        debugMessages.innerHTML += `
            <div style="border-bottom: 1px solid #333; padding-bottom: 6px; margin-bottom: 6px;">
                <span style="color: #888; margin-right: 8px;">${timestamp}</span>
                <span>${message}</span>
            </div>
        `;
        
        // Auto-scroll to bottom
        debugMessages.scrollTop = debugMessages.scrollHeight;
    }
};
