/**
 * main.js - Main entry point for the MetaGPT visualization application
 */

// Global initialization
document.addEventListener('DOMContentLoaded', async function() {
    debugLog('Application initializing...');
    
    // Load user settings
    loadSettings();
    
    // Set up event listeners
    setupEventListeners();
    
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
    
    // Load job from URL if present
    loadJobFromUrl();
    
    debugLog('Application initialized');
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
