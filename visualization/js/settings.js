/**
 * settings.js - User settings management for MetaGPT visualization
 */

// User settings with defaults
let userSettings = {
    theme: 'light',
    fontSize: 'medium',
    maxReconnectAttempts: 5,
    reconnectInterval: 3000,
    logLevel: 'info',
    autoDebugOnErrors: true,
    recentJobs: []
};

// Save original console methods to restore when needed
const originalConsoleLog = console.log;
const originalConsoleInfo = console.info;
const originalConsoleWarn = console.warn;
const originalConsoleError = console.error;

/**
 * Function to load settings from localStorage
 */
function loadSettings() {
    try {
        const savedSettings = localStorage.getItem('metagpt_visualization_settings');
        if (savedSettings) {
            userSettings = JSON.parse(savedSettings);
            debugLog('Loaded settings from localStorage');
            
            // Apply the loaded settings
            applySettings();
        }
        
        // Load recent jobs
        const recentJobs = localStorage.getItem('metagpt_recent_jobs');
        if (recentJobs) {
            userSettings.recentJobs = JSON.parse(recentJobs);
            updateRecentJobsList();
        }
    } catch (e) {
        debugLog('Error loading settings:', e);
        // Use default settings if there's an error
    }
}

/**
 * Function to save settings to localStorage
 */
function saveSettings() {
    try {
        // Update settings from form inputs
        userSettings.theme = document.getElementById('theme-selector').value;
        userSettings.fontSize = document.getElementById('font-size').value;
        userSettings.maxReconnectAttempts = parseInt(document.getElementById('reconnect-attempts').value);
        userSettings.reconnectInterval = parseInt(document.getElementById('reconnect-interval').value);
        userSettings.logLevel = document.getElementById('log-level').value;
        userSettings.autoDebugOnErrors = document.getElementById('auto-debug').checked;
        
        // Save to localStorage
        localStorage.setItem('metagpt_visualization_settings', JSON.stringify(userSettings));
        
        // Apply the new settings
        applySettings();
        
        // Close the modal
        closeConfigModal();
        
        // Show confirmation
        appendResult({
            role: 'system',
            content: 'Settings saved successfully.'
        });
    } catch (e) {
        debugLog('Error saving settings:', e);
        alert('Failed to save settings. Please try again.');
    }
}

/**
 * Function to apply settings to the UI
 */
function applySettings() {
    // Apply theme
    document.body.className = userSettings.theme === 'dark' ? 'dark-theme' : '';
    
    // Apply font size
    document.documentElement.style.setProperty('--base-font-size', 
        userSettings.fontSize === 'small' ? '12px' : 
        userSettings.fontSize === 'large' ? '16px' : '14px');
    
    // Update form values
    document.getElementById('theme-selector').value = userSettings.theme;
    document.getElementById('font-size').value = userSettings.fontSize;
    document.getElementById('reconnect-attempts').value = userSettings.maxReconnectAttempts;
    document.getElementById('reconnect-interval').value = userSettings.reconnectInterval;
    document.getElementById('log-level').value = userSettings.logLevel;
    document.getElementById('auto-debug').checked = userSettings.autoDebugOnErrors;
    
    // Update debug logging level based on settings
    switch(userSettings.logLevel) {
        case 'error':
            console.error = originalConsoleError;
            console.warn = function() {};
            console.info = function() {};
            console.log = function() {};
            break;
        case 'warning':
            console.error = originalConsoleError;
            console.warn = originalConsoleWarn;
            console.info = function() {};
            console.log = function() {};
            break;
        case 'info':
            console.error = originalConsoleError;
            console.warn = originalConsoleWarn;
            console.info = originalConsoleInfo;
            console.log = function() {};
            break;
        case 'debug':
            console.error = originalConsoleError;
            console.warn = originalConsoleWarn;
            console.info = originalConsoleInfo;
            console.log = originalConsoleLog;
            break;
    }
}

/**
 * Function to reset settings to defaults
 */
function resetSettings() {
    userSettings = {
        theme: 'light',
        fontSize: 'medium',
        maxReconnectAttempts: 5,
        reconnectInterval: 3000,
        logLevel: 'info',
        autoDebugOnErrors: true,
        recentJobs: userSettings.recentJobs // Keep recent jobs
    };
    
    applySettings();
    
    // Save to localStorage
    localStorage.setItem('metagpt_visualization_settings', JSON.stringify(userSettings));
    
    // Show confirmation
    appendResult({
        role: 'system',
        content: 'Settings reset to defaults.'
    });
}

/**
 * Function to add a job to recent jobs
 * @param {string} jobId - The job ID to add
 */
function addToRecentJobs(jobId) {
    // Don't add empty or test job IDs
    if (!jobId || jobId === 'test_connection') return;
    
    // Remove the job if it already exists
    userSettings.recentJobs = userSettings.recentJobs.filter(job => job.id !== jobId);
    
    // Add to the beginning of the array
    userSettings.recentJobs.unshift({
        id: jobId,
        timestamp: new Date().toISOString(),
        displayName: jobId
    });
    
    // Keep only the 10 most recent jobs
    if (userSettings.recentJobs.length > 10) {
        userSettings.recentJobs = userSettings.recentJobs.slice(0, 10);
    }
    
    // Save to localStorage
    localStorage.setItem('metagpt_recent_jobs', JSON.stringify(userSettings.recentJobs));
    
    // Update the UI
    updateRecentJobsList();
}

/**
 * Function to update the recent jobs list in the UI
 */
function updateRecentJobsList() {
    const recentJobsList = document.getElementById('recent-jobs-list');
    if (!recentJobsList) return;
    
    if (userSettings.recentJobs.length === 0) {
        recentJobsList.innerHTML = '<div class="empty-state">No recent jobs</div>';
        return;
    }
    
    recentJobsList.innerHTML = '';
    
    userSettings.recentJobs.forEach(job => {
        const jobElement = document.createElement('div');
        jobElement.className = 'recent-job-item';
        
        const timestamp = new Date(job.timestamp);
        const formattedDate = timestamp.toLocaleDateString();
        const formattedTime = timestamp.toLocaleTimeString();
        
        jobElement.innerHTML = `
            <div class="job-info">
                <div class="job-id">${job.displayName}</div>
                <div class="job-timestamp">${formattedDate} ${formattedTime}</div>
            </div>
            <button class="load-job-btn" data-job-id="${job.id}">Load</button>
        `;
        
        recentJobsList.appendChild(jobElement);
        
        // Add click handler for the load button
        jobElement.querySelector('.load-job-btn').addEventListener('click', function() {
            const jobId = this.getAttribute('data-job-id');
            document.getElementById('input-field').value = jobId;
            submitPrompt();
            closeConfigModal();
        });
    });
}
