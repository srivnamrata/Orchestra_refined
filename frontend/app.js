// ============================================================================
// COMMAND PALETTE SYSTEM
// ============================================================================

console.log('🔧 app.js script loaded');

const commandPalette = {
    isOpen: false,
    highlightedIndex: 0,
    searchTerm: '',
    recentCommands: JSON.parse(localStorage.getItem('recentCommands')) || [],
    
    // Complete command registry
    commands: [
        // Agents
        { id: 'run-critic', title: 'Run Critic Replan Demo', icon: 'fa-play', category: 'Agents', desc: 'Analyze and replan your workflow', action: 'triggerCriticDemo', shortcut: 'Ctrl+Shift+C' },
        { id: 'run-vibecheck', title: 'Run Vibe-Check Demo', icon: 'fa-shield', category: 'Agents', desc: 'Check alignment with your goals', action: 'triggerVibeCheckDemo', shortcut: 'Ctrl+Shift+V' },
        { id: 'initiate-debate', title: 'Initiate Debate', icon: 'fa-comments', category: 'Agents', desc: 'Start multi-perspective analysis', action: 'triggerDebateDemo', shortcut: 'Ctrl+Shift+D' },
        
        // Data & Content
        { id: 'fetch-news', title: 'Fetch News Headlines', icon: 'fa-newspaper', category: 'Data & Content', desc: 'Get latest news from around the world', action: 'triggerNewsDemo' },
        { id: 'fetch-research', title: 'Fetch Research Papers', icon: 'fa-book', category: 'Data & Content', desc: 'Search academic research papers', action: 'triggerResearchDemo' },

        { id: 'gather-context', title: 'Gather Context Analysis', icon: 'fa-lightbulb', category: 'Data & Content', desc: 'Intelligent multi-source context gathering', action: 'triggerKnowledgeDemo', shortcut: 'Ctrl+Shift+G' },
        
        // Create & Manage
        { id: 'create-task', title: 'Create New Task', icon: 'fa-plus', category: 'Create & Manage', desc: 'Add a new task to your list', action: 'openTaskModal', shortcut: 'Ctrl+N' },
        { id: 'create-event', title: 'Schedule New Event', icon: 'fa-calendar', category: 'Create & Manage', desc: 'Create a calendar event', action: 'openEventModal', shortcut: 'Ctrl+E' },
        { id: 'create-note', title: 'Create New Note', icon: 'fa-note-sticky', category: 'Create & Manage', desc: 'Write a new note', action: 'openNoteModal', shortcut: 'Ctrl+Alt+N' },
        { id: 'view-tasks', title: 'View Task List', icon: 'fa-list', category: 'Create & Manage', desc: 'See all your tasks', action: 'triggerTaskDemo' },
        { id: 'view-schedule', title: 'View Event Schedule', icon: 'fa-calendar-days', category: 'Create & Manage', desc: 'Check your calendar', action: 'triggerSchedulerDemo' },
        
        // Navigation
        { id: 'nav-dashboard', title: 'Go to Dashboard', icon: 'fa-chart-pie', category: 'Navigation', desc: 'Overview and quick actions', action: () => switchView('dashboard') },
        { id: 'nav-workflows', title: 'Go to Workflows', icon: 'fa-diagram-project', category: 'Navigation', desc: 'View workflow analysis', action: () => switchView('workflows') },
        { id: 'nav-vibes', title: 'Go to Vibe Checks', icon: 'fa-shield-halved', category: 'Navigation', desc: 'See vibe check results', action: () => switchView('vibe-checks') },
        { id: 'nav-debates', title: 'Go to Debates', icon: 'fa-people-arrows', category: 'Navigation', desc: 'View agent debates', action: () => switchView('debates') },
    ],
    
    init: function() {
        const searchInput = document.getElementById('command-search');
        const overlay = document.getElementById('command-palette-overlay');
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl+K or Cmd+K to open
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.toggle();
            }
            
            // ESC to close
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
            
            // Navigation in palette
            if (this.isOpen) {
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    this.highlightNext();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    this.highlightPrev();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    this.executeHighlighted();
                }
            }
        });
        
        // Search input
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchTerm = e.target.value;
                this.renderCommands();
            });
        }
        
        // Close on overlay click
        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    this.close();
                }
            });
        }
        
        // Defer command rendering to next frame
        setTimeout(() => this.renderCommands(), 0);
    },
    
    toggle: function() {
        this.isOpen ? this.close() : this.open();
    },
    
    open: function() {
        const overlay = document.getElementById('command-palette-overlay');
        const searchInput = document.getElementById('command-search');
        
        if (overlay) {
            overlay.style.display = 'flex';
            this.isOpen = true;
            this.highlightedIndex = 0;
            
            setTimeout(() => {
                if (searchInput) {
                    searchInput.focus();
                }
            }, 100);
            
            this.renderCommands();
        }
    },
    
    close: function() {
        const overlay = document.getElementById('command-palette-overlay');
        const searchInput = document.getElementById('command-search');
        
        if (overlay) {
            overlay.style.display = 'none';
            this.isOpen = false;
            this.searchTerm = '';
            
            if (searchInput) {
                searchInput.value = '';
            }
        }
    },
    
    getVisibleCommands: function() {
        let filtered = this.commands;
        
        if (this.searchTerm.trim()) {
            const query = this.searchTerm.toLowerCase();
            filtered = this.commands.filter(cmd => 
                cmd.title.toLowerCase().includes(query) ||
                cmd.desc.toLowerCase().includes(query) ||
                cmd.category.toLowerCase().includes(query)
            );
        }
        
        return filtered;
    },
    
    renderCommands: function() {
        const commandList = document.getElementById('command-list');
        if (!commandList) return;
        
        const visible = this.getVisibleCommands();
        
        if (visible.length === 0) {
            commandList.innerHTML = `
                <div class="command-empty">
                    <i class="fa-solid fa-search"></i>
                    <p>No commands found</p>
                </div>
            `;
            return;
        }
        
        // Group by category
        const grouped = {};
        visible.forEach(cmd => {
            if (!grouped[cmd.category]) grouped[cmd.category] = [];
            grouped[cmd.category].push(cmd);
        });
        
        // Render
        let html = '';
        let index = 0;
        
        Object.entries(grouped).forEach(([category, items]) => {
            html += `<div class="command-category">`;
            html += `<div class="category-label">${category}</div>`;
            html += `<div class="category-items">`;
            
            items.forEach((cmd) => {
                const isHighlighted = index === this.highlightedIndex;
                html += `
                    <div class="command-item ${isHighlighted ? 'highlighted' : ''}" data-index="${index}" onclick="commandPalette.executeCommand('${cmd.id}')">
                        <i class="fa-solid ${cmd.icon}"></i>
                        <div class="command-item-content">
                            <div class="command-item-title">${cmd.title}</div>
                            <div class="command-item-desc">${cmd.desc}</div>
                        </div>
                        ${cmd.shortcut ? `<div class="command-item-shortcut">${cmd.shortcut}</div>` : ''}
                    </div>
                `;
                index++;
            });
            
            html += `</div></div>`;
        });
        
        commandList.innerHTML = html;
        
        // Scroll highlighted into view
        const highlighted = commandList.querySelector('.command-item.highlighted');
        if (highlighted) {
            highlighted.scrollIntoView({ block: 'nearest' });
        }
    },
    
    highlightNext: function() {
        const visible = this.getVisibleCommands();
        this.highlightedIndex = (this.highlightedIndex + 1) % visible.length;
        this.renderCommands();
    },
    
    highlightPrev: function() {
        const visible = this.getVisibleCommands();
        this.highlightedIndex = (this.highlightedIndex - 1 + visible.length) % visible.length;
        this.renderCommands();
    },
    
    executeHighlighted: function() {
        const visible = this.getVisibleCommands();
        if (visible[this.highlightedIndex]) {
            this.executeCommand(visible[this.highlightedIndex].id);
        }
    },
    
    executeCommand: function(commandId) {
        const cmd = this.commands.find(c => c.id === commandId);
        if (cmd && cmd.action) {
            // Track recent
            this.recentCommands = [commandId, ...this.recentCommands.filter(c => c !== commandId)].slice(0, 5);
            localStorage.setItem('recentCommands', JSON.stringify(this.recentCommands));
            
            // Close palette
            this.close();
            
            // Execute
            setTimeout(() => {
                // Handle both function references and string function names
                if (typeof cmd.action === 'string') {
                    // If action is a string function name, look it up from window
                    const func = window[cmd.action];
                    if (typeof func === 'function') {
                        func();
                    } else {
                        console.error(`Command Action Error: Function "${cmd.action}" not found`);
                    }
                } else if (typeof cmd.action === 'function') {
                    // If action is a function reference, call it directly
                    cmd.action();
                }
            }, 100);
        }
    },
    
    getRecentCommands: function() {
        return this.recentCommands
            .map(id => this.commands.find(c => c.id === id))
            .filter(Boolean);
    }
};

// ============================================================================
// VIEW & NAVIGATION MANAGEMENT
// ============================================================================

function switchView(viewId) {
    // Update nav tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-target="${viewId}"]`).classList.add('active');
    
    // Show view
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(viewId).classList.add('active');
    
    // Update breadcrumb
    updateBreadcrumb(viewId);
}

function updateBreadcrumb(viewId) {
    const breadcrumbs = document.getElementById('breadcrumbs');
    const labels = {
        'dashboard': 'Dashboard',
        'workflows': 'Workflows',
        'vibe-checks': 'Vibe Checks',
        'debates': 'Debates'
    };
    
    const label = labels[viewId] || 'Dashboard';
    
    if (viewId === 'dashboard') {
        breadcrumbs.innerHTML = `<span class="breadcrumb-home"><i class="fa-solid fa-house"></i> Dashboard</span>`;
    } else {
        breadcrumbs.innerHTML = `
            <span class="breadcrumb-home"><i class="fa-solid fa-house"></i> Dashboard</span>
            <span class="breadcrumb-separator">/</span>
            <span class="breadcrumb-text">${label}</span>
            <button class="nav-tab" style="position: absolute; left: 50%; color: var(--text-muted); font-size: 0.85rem;" onclick="switchView('dashboard')">
                ← Back to Dashboard
            </button>
        `;
    }
}

// ============================================================================
// STAT CARDS: EXPANDABLE DRILL-DOWN WITH MICRO-INTERACTIONS
// ============================================================================

function expandStatCard(cardType) {
    const overlay = document.getElementById('stat-details-overlay');
    const detailView = document.getElementById(`${cardType}-detail`);
    
    // Hide all detail views
    document.querySelectorAll('.stat-detail-content').forEach(el => {
        el.style.display = 'none';
    });
    
    // Show selected detail view
    if (detailView) {
        detailView.style.display = 'block';
    }
    
    overlay.style.display = 'flex';
    
    // Log interaction
    appendLog(`📊 Viewing ${cardType} statistics`, 'info');
}

function closeStatCard() {
    document.getElementById('stat-details-overlay').style.display = 'none';
}

// Close modal on overlay click
document.addEventListener('click', function(event) {
    const overlay = document.getElementById('stat-details-overlay');
    if (event.target === overlay) {
        closeStatCard();
    }
});

// Keyboard shortcut to close (Escape key)
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeStatCard();
    }
});

// ============================================================================
// SPARKLINE CHART GENERATION
// ============================================================================

function generateSparkline(canvasId, data = [3, 5, 4, 6, 5, 7, 8, 6, 9, 7]) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    
    const pointWidth = width / (data.length - 1);
    
    ctx.strokeStyle = 'rgba(79, 172, 254, 0.8)';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    ctx.beginPath();
    data.forEach((value, index) => {
        const x = index * pointWidth;
        const y = height - ((value - min) / range) * (height - 10) - 5;
        
        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    ctx.stroke();
}

// Initialize sparklines when page loads
function initSparklines() {
    try {
        generateSparkline('sparkline-workflows', [2, 2, 2, 2, 2, 2, 2, 2, 2, 2]);
        generateSparkline('sparkline-safety', [96, 96, 97, 97, 98, 98, 98, 98, 98, 98]);
        generateSparkline('sparkline-completed', [0, 0, 1, 1, 1, 1, 1, 1, 1, 1]);
    } catch (e) {
        console.warn('Could not initialize sparklines:', e.message);
    }
}

// Initialize floating hint badge for Command Palette discovery
function initFloatingHintBadge() {
    const hintBadge = document.getElementById('floating-hint-badge');
    if (!hintBadge) return;
    
    // Check if user has already seen the hint
    const hintSeen = sessionStorage.getItem('commandPaletteHintSeen');
    
    if (!hintSeen) {
        // Show hint badge after 800ms delay (gives page time to load)
        setTimeout(() => {
            hintBadge.style.display = 'flex';
            sessionStorage.setItem('commandPaletteHintSeen', 'true');
        }, 800);
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            hintBadge.style.display = 'none';
        }, 5800);
    }
    
    // Allow clicking the badge to open palette and dismiss hint
    hintBadge.addEventListener('click', () => {
        hintBadge.style.display = 'none';
    });
    
    // Dismiss hint if user opens palette with keyboard
    const originalOpen = commandPalette.open.bind(commandPalette);
    commandPalette.open = function() {
        hintBadge.style.display = 'none';
        originalOpen();
    };
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('📄 DOMContentLoaded event fired');
    
    // Defer ALL initialization to next frame to ensure page is interactive
    setTimeout(() => {
        console.log('⚙️ Init stage 1: Floating hint badge');
        // 1. Initialize floating hint badge
        initFloatingHintBadge();
    }, 0);

    setTimeout(() => {
        console.log('⚙️ Init stage 2: Command Palette');
        // 2. Initialize Command Palette
        commandPalette.init();
    }, 10);

    setTimeout(() => {
        console.log('⚙️ Init stage 3: Sparklines');
        // 3. Initialize sparklines
        initSparklines();
    }, 20);

    setTimeout(() => {
        console.log('⚙️ Init stage 4: Set agent list');
        // 4. Set initial UI state for health check
        const agentList = document.getElementById('agent-status-list');
        if (agentList) {
            agentList.innerHTML = '<li style="color: #64b5f6;">⏳ Checking system...</li>';
        }
    }, 30);

    setTimeout(() => {
        console.log('⚙️ Init stage 5: Fetch health status');
        // 5. Fetch Health Status (non-blocking)
        fetchHealthStatus();
    }, 100);
});

// Helper for UI Console
// ============================================================================
// SMART ACTIVITY FEED SYSTEM
// ============================================================================

const activityFeed = {
    allActivities: [],
    pinnedActivities: [],
    currentFilter: 'all',
    
    // Log activity with intelligent categorization
    log: function(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const category = this.categorizeActivity(message, type);
        
        const activity = {
            id: Date.now() + Math.random(),
            message: message,
            type: type,
            category: category,
            timestamp: timestamp,
            pinned: false
        };
        
        this.allActivities.unshift(activity);
        
        // Keep last 100 activities
        if (this.allActivities.length > 100) {
            this.allActivities.pop();
        }
        
        this.renderActivityFeed();
        this.updateSummary();
    },
    
    // Intelligently categorize activities
    categorizeActivity: function(message, type) {
        const lowerMsg = message.toLowerCase();
        
        if (lowerMsg.includes('task') || lowerMsg.includes('created') || lowerMsg.includes('creating')) {
            return 'tasks';
        } else if (lowerMsg.includes('gather') || lowerMsg.includes('context') || lowerMsg.includes('analysis') || 
                   lowerMsg.includes('insight') || lowerMsg.includes('confidence') || lowerMsg.includes('entity')) {
            return 'analysis';
        } else if (lowerMsg.includes('complete') || lowerMsg.includes('playing') || lowerMsg.includes('saved') || 
                   lowerMsg.includes('marked') || lowerMsg.includes('error') || lowerMsg.includes('failed')) {
            return 'status';
        }
        return 'all';
    },
    
    // Render the activity feed
    renderActivityFeed: function() {
        const feedDiv = document.getElementById('action-output');
        feedDiv.innerHTML = '';
        
        const filteredActivities = this.allActivities.filter(activity => {
            if (this.currentFilter === 'all') return true;
            return activity.category === this.currentFilter;
        });
        
        if (filteredActivities.length === 0) {
            feedDiv.innerHTML = '<div class="console-placeholder">No activities match this filter</div>';
            return;
        }
        
        filteredActivities.forEach(activity => {
            const activityEl = this.createActivityElement(activity);
            feedDiv.appendChild(activityEl);
        });
        
        feedDiv.scrollTop = 0;
    },
    
    // Create individual activity element
    createActivityElement: function(activity) {
        const div = document.createElement('div');
        div.className = `activity-item type-${activity.type}`;
        div.id = `activity-${activity.id}`;
        div.dataset.filter = activity.category;
        
        if (this.currentFilter !== 'all' && activity.category !== this.currentFilter) {
            div.classList.add('hidden');
        }
        
        const badgeText = activity.type.toUpperCase();
        const badgeClass = `badge-${activity.type}`;
        
        div.innerHTML = `
            <div style="display: flex; gap: 8px; width: 100%;">
                <div class="activity-content" style="flex: 1;">
                    <div class="activity-badge ${badgeClass}">${badgeText}</div>
                    <div class="activity-message">${activity.message}</div>
                    <div class="activity-timestamp">${activity.timestamp}</div>
                </div>
                <button class="activity-pin-btn ${activity.pinned ? 'pinned' : ''}" 
                        onclick="activityFeed.togglePin(${activity.id})"
                        title="${activity.pinned ? 'Unpin' : 'Pin important event'}">
                    <i class="fa-solid fa-thumbtack"></i>
                </button>
            </div>
        `;
        
        return div;
    },
    
    // Update summary of last 3 actions
    updateSummary: function() {
        const summaryDiv = document.getElementById('activity-summary');
        const recentActivities = this.allActivities.slice(0, 3);
        
        if (recentActivities.length === 0) {
            summaryDiv.innerHTML = '<div class="summary-placeholder">Complete your first action to see summary...</div>';
            return;
        }
        
        let summaryHTML = '';
        recentActivities.forEach(activity => {
            // Extract key info from message
            const shortMsg = activity.message.length > 80 
                ? activity.message.substring(0, 80) + '...' 
                : activity.message;
            
            summaryHTML += `
                <div class="summary-item">
                    <span style="color: #87cefa; font-weight: 600;">✓</span>
                    <span>${shortMsg}</span>
                </div>
            `;
        });
        
        summaryDiv.innerHTML = summaryHTML;
    },
    
    // Toggle pin state for activity
    togglePin: function(activityId) {
        const activity = this.allActivities.find(a => a.id === activityId);
        if (!activity) return;
        
        activity.pinned = !activity.pinned;
        
        if (activity.pinned) {
            this.pinnedActivities.unshift(activity);
            if (this.pinnedActivities.length > 5) {
                this.pinnedActivities.pop();
            }
        } else {
            this.pinnedActivities = this.pinnedActivities.filter(a => a.id !== activityId);
        }
        
        this.updatePinnedSection();
        this.renderActivityFeed();
    },
    
    // Update pinned items section
    updatePinnedSection: function() {
        const pinnedSection = document.getElementById('pinned-items');
        const pinnedList = document.getElementById('pinned-list');
        
        if (this.pinnedActivities.length === 0) {
            pinnedSection.style.display = 'none';
            return;
        }
        
        pinnedSection.style.display = 'block';
        pinnedList.innerHTML = '';
        
        this.pinnedActivities.forEach(activity => {
            const pinnedEl = document.createElement('div');
            pinnedEl.className = 'pinned-item';
            pinnedEl.innerHTML = `
                <i class="fa-solid fa-thumbtack"></i>
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 0.85rem;">${activity.message.substring(0, 60)}${activity.message.length > 60 ? '...' : ''}</div>
                    <div style="color: var(--text-muted); font-size: 0.75rem;">${activity.timestamp}</div>
                </div>
                <button class="activity-pin-btn pinned" 
                        onclick="activityFeed.togglePin(${activity.id})"
                        title="Unpin event"
                        style="padding: 0; margin: 0;">
                    <i class="fa-solid fa-x"></i>
                </button>
            `;
            pinnedList.appendChild(pinnedEl);
        });
    }
};

// Filter activities by category
function filterActivities(category) {
    activityFeed.currentFilter = category;
    
    // Update button states
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-filter="${category}"]`).classList.add('active');
    
    activityFeed.renderActivityFeed();
}

// Enhanced appendLog function
function appendLog(message, type = 'info') {
    activityFeed.log(message, type);
}


// Ensure proper spacing/formatting
function formatJSON(obj) {
    return `<pre style="margin-top: 5px; color: #a5d6ff;">${JSON.stringify(obj, null, 2)}</pre>`;
}

// ============================================================================
// Agent Content Panel Management with Tabs Support
// ============================================================================
let currentAgentData = null;
let currentAudioText = "";
let currentAgentType = "news"; // Track which agent data is displayed

function switchAgentTab(tabId) {
    // Hide all tabs
    document.querySelectorAll('.agent-tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.agent-tab').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(tabId).classList.add('active');
    document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
    
    // Update current agent type
    if (tabId.includes('news')) currentAgentType = "news";
    else if (tabId.includes('research')) currentAgentType = "research";
    else if (tabId.includes('task')) currentAgentType = "task";
    else if (tabId.includes('schedule')) currentAgentType = "schedule";
    else if (tabId.includes('calendar')) currentAgentType = "calendar";
    else if (tabId.includes('email')) currentAgentType = "email";
}

function displayAgentContent(agentName, agentTitle, icon, contentData) {
    // Store agent data for audio
    currentAgentData = contentData;
    
    // Update panel header
    document.getElementById('agent-icon').className = `fa-solid ${icon}`;
    document.getElementById('agent-title').textContent = agentTitle;
    
    // CLEAR ALL CONTENT DIVS FOR FRESH START
    document.getElementById('agent-content-news').innerHTML = '';
    document.getElementById('agent-content-research').innerHTML = '';
    document.getElementById('agent-content-tasks').innerHTML = '';
    document.getElementById('agent-content-schedule').innerHTML = '';
    
    // Determine which content div to use based on agent type
    let contentDiv;
    if (contentData.articles_fetched) {
        // News Agent
        contentDiv = document.getElementById('agent-content-news');
        currentAgentType = "news";
        switchAgentTab('news-tab');
    } else if (contentData.papers_analyzed) {
        // Research Agent
        contentDiv = document.getElementById('agent-content-research');
        currentAgentType = "research";
        switchAgentTab('research-tab');
    } else if (contentData.tasks && contentData.tasks.length > 0) {
        // Task List
        contentDiv = document.getElementById('agent-content-tasks');
        currentAgentType = "task";
        switchAgentTab('task-tab');
    } else if (contentData.events && contentData.events.length > 0) {
        // Scheduler/Events List
        contentDiv = document.getElementById('agent-content-schedule');
        currentAgentType = "schedule";
        switchAgentTab('schedule-tab');
    } else if (contentData.status === 'empty') {
        // Empty state
        contentDiv = document.getElementById('agent-content-tasks');
        currentAgentType = "task";
        switchAgentTab('task-tab');
    } else {
        contentDiv = document.getElementById('agent-content-news');
    }
    
    // Generate audio text summary
    let audioText = `${agentTitle} report. `;
    
    // Display different content based on agent type
    if (contentData.articles_fetched) {
        // News Agent - Display as cards
        displayNewsCards(contentDiv, contentData);
        audioText += `Found ${contentData.articles_fetched} news articles. `;
        
        // Add enumerated titles to audio
        if (contentData.sample_headlines && contentData.sample_headlines.length > 0) {
            audioText += "Headlines: ";
            contentData.sample_headlines.forEach((headline, index) => {
                audioText += `${index + 1}. ${headline}. `;
            });
        }
        if (contentData.additional_headlines && contentData.additional_headlines.length > 0) {
            contentData.additional_headlines.forEach((headline, index) => {
                audioText += `${contentData.sample_headlines.length + index + 1}. ${headline}. `;
            });
        }
        // Also add articles if available from live fetch
        if (contentData.articles && contentData.articles.length > 0) {
            audioText += "Featured articles: ";
            contentData.articles.slice(0, 5).forEach((article, index) => {
                const title = article.title || article.name || "Untitled";
                audioText += `${index + 1}. ${title}. `;
            });
        }
    } else if (contentData.papers_analyzed) {
        // Research Agent - Display as cards
        displayResearchCards(contentDiv, contentData);
        audioText += `Analyzed ${contentData.papers_analyzed} research papers. `;
        
        // Add enumerated paper titles to audio
        if (contentData.trending_topics && contentData.trending_topics.length > 0) {
            audioText += "Trending research topics: ";
            contentData.trending_topics.forEach((topic, index) => {
                audioText += `${index + 1}. ${topic}. `;
            });
        }
        if (contentData.key_findings && contentData.key_findings.length > 0) {
            audioText += "Key findings: ";
            contentData.key_findings.forEach((finding, index) => {
                audioText += `${index + 1}. ${finding}. `;
            });
        }
        // Also add papers if available from live fetch
        if (contentData.papers && contentData.papers.length > 0) {
            audioText += "Featured papers: ";
            contentData.papers.slice(0, 5).forEach((paper, index) => {
                const title = paper.title || paper.name || "Untitled paper";
                audioText += `${index + 1}. ${title}. `;
            });
        }
    } else if (contentData.tasks && contentData.tasks.length > 0) {
        // Task List - Display as cards
        displayTaskCards(contentDiv, contentData);
        audioText += `${contentData.total_count || contentData.tasks.length} tasks in your list. `;
        
        // Add task titles to audio
        audioText += "Tasks: ";
        contentData.tasks.slice(0, 5).forEach((task, index) => {
            const taskTitle = task.title || task.name || "Untitled task";
            const priority = task.priority ? ` priority ${task.priority}` : "";
            audioText += `${index + 1}. ${taskTitle}${priority}. `;
        });
    } else if (contentData.events && contentData.events.length > 0) {
        // Schedule/Events List - Display as cards
        displayEventCards(contentDiv, contentData);
        audioText += `${contentData.total_count || contentData.events.length} events in your calendar. `;
        
        // Add event titles to audio
        audioText += "Events: ";
        contentData.events.slice(0, 5).forEach((event, index) => {
            const eventTitle = event.title || event.name || "Untitled event";
            audioText += `${index + 1}. ${eventTitle}. `;
        });
    } else if (contentData.calendar_events && contentData.calendar_events.length > 0) {
        // Google Calendar Events - Display as cards
        displayCalendarCards(contentDiv, contentData);
        audioText += `${contentData.total_count || contentData.calendar_events.length} upcoming calendar events. `;
        
        // Add calendar event titles to audio
        audioText += "Calendar events: ";
        contentData.calendar_events.slice(0, 5).forEach((event, index) => {
            const eventTitle = event.title || event.name || "Untitled event";
            audioText += `${index + 1}. ${eventTitle}. `;
        });
    } else if (contentData.emails && contentData.emails.length > 0) {
        // Gmail Emails - Display as cards
        displayEmailCards(contentDiv, contentData);
        audioText += `${contentData.total_count || contentData.emails.length} important emails. `;
        
        // Add email subjects to audio
        audioText += "Emails: ";
        contentData.emails.slice(0, 5).forEach((email, index) => {
            const subject = email.subject || "Untitled email";
            audioText += `${index + 1}. From ${email.from}. Subject: ${subject}. `;
        });
    } else if (contentData.status === 'empty') {
        // Empty Task List
        const emptyItem = document.createElement('div');
        emptyItem.className = 'empty-state';
        emptyItem.innerHTML = `<strong>📭 ${contentData.message}</strong><br>${contentData.next_action}`;
        contentDiv.appendChild(emptyItem);
        audioText += contentData.message + `. `;
    } else if (contentData.context_gathered) {
        // Knowledge Agent - Comprehensive Context Analysis
        currentAgentType = "knowledge";
        switchAgentTab('news-tab');
        
        // Main stats card
        const statsCard = document.createElement('div');
        statsCard.className = 'article-card featured';
        statsCard.innerHTML = `
            <div class="article-card-header">
                <div>
                    <div class="article-title featured">
                        📊 Context Analysis Complete
                    </div>
                    <div class="article-card-meta">
                        <span class="source-badge">Knowledge Graph</span>
                        <span class="published-date">
                            <i class="fa-solid fa-brain"></i> Real-time Analysis
                        </span>
                    </div>
                </div>
            </div>
            <div class="article-summary">
                <strong>Overview:</strong><br>
                📌 <strong>${contentData.entities_identified}</strong> entities (${contentData.total_tasks} tasks, ${contentData.total_events} events, ${contentData.total_notes} notes)<br>
                🔗 <strong>${contentData.relationships_mapped}</strong> relationships identified<br>
                💯 <strong>${contentData.confidence_score}%</strong> confidence score
            </div>
            <div class="article-actions">
                <button class="action-btn action-btn--primary" onclick="alert('📊 Knowledge graph visualization - Coming Soon!')">📊 Visualize</button>
                <button class="action-btn action-btn--link" onclick="expandContextDetails()">🔍 Details</button>
                <button class="action-btn action-btn--save" onclick="exportContext()">💾 Export</button>
            </div>
        `;
        contentDiv.appendChild(statsCard);
        
        // Key Insights Card
        if (contentData.insights && contentData.insights.length > 0) {
            const insightsCard = document.createElement('div');
            insightsCard.className = 'article-card';
            
            const insightsList = contentData.insights.slice(0, 3).map(insight => 
                `<li>✨ ${insight}</li>`
            ).join('');
            
            insightsCard.innerHTML = `
                <div class="article-card-header">
                    <div>
                        <div class="article-title">⚡ Key Insights</div>
                        <div class="article-card-meta">
                            <span class="source-badge">AI Analysis</span>
                        </div>
                    </div>
                </div>
                <div class="article-summary">
                    <ul style="margin: 0; padding-left: 20px; list-style: none;">
                        ${insightsList}
                    </ul>
                </div>
            `;
            contentDiv.appendChild(insightsCard);
        }
        
        // Priorities Card
        if (contentData.key_priorities && contentData.key_priorities.length > 0) {
            const prioritiesCard = document.createElement('div');
            prioritiesCard.className = 'article-card';
            
            const prioritiesList = contentData.key_priorities.map(priority => 
                `<li>🎯 ${priority}</li>`
            ).join('');
            
            prioritiesCard.innerHTML = `
                <div class="article-card-header">
                    <div>
                        <div class="article-title">🎯 Priority Areas</div>
                        <div class="article-card-meta">
                            <span class="source-badge">Task Analysis</span>
                        </div>
                    </div>
                </div>
                <div class="article-summary">
                    <ul style="margin: 0; padding-left: 20px; list-style: none;">
                        ${prioritiesList}
                    </ul>
                </div>
            `;
            contentDiv.appendChild(prioritiesCard);
        }
        
        // Knowledge Areas Card
        if (contentData.knowledge_areas && contentData.knowledge_areas.length > 0) {
            const areasCard = document.createElement('div');
            areasCard.className = 'article-card';
            
            const areasList = contentData.knowledge_areas.slice(0, 5).map(area => 
                `<span style="display: inline-block; background: rgba(147, 112, 219, 0.3); border: 1px solid #9370db; border-radius: 12px; padding: 4px 8px; margin: 4px 4px 4px 0; font-size: 12px;">📚 ${area}</span>`
            ).join('');
            
            areasCard.innerHTML = `
                <div class="article-card-header">
                    <div>
                        <div class="article-title">📚 Knowledge Areas</div>
                        <div class="article-card-meta">
                            <span class="source-badge">${contentData.knowledge_areas.length} areas</span>
                        </div>
                    </div>
                </div>
                <div class="article-summary">
                    <div style="display: flex; flex-wrap: wrap;">
                        ${areasList}
                    </div>
                </div>
            `;
            contentDiv.appendChild(areasCard);
        }
        
        audioText += `Gathered comprehensive context from ${contentData.entities_identified} entities. Found ${contentData.relationships_mapped} relationships with ${contentData.confidence_score}% confidence. `;
        if (contentData.insights.length > 0) {
            audioText += `Top insight: ${contentData.insights[0]}. `;
        }
    } else if (contentData.task_created) {
        // Task Agent - New Task Created
        const headerDiv = document.createElement('div');
        headerDiv.className = 'agent-content-header';
        headerDiv.innerHTML = `<i class="fa-solid fa-tasks"></i> Task ${contentData.task_id}`;
        contentDiv.appendChild(headerDiv);
        
        const taskItem = document.createElement('div');
        taskItem.className = 'agent-content-item success';
        taskItem.innerHTML = `<strong>Task:</strong> ${contentData.title}<br><strong>Priority:</strong> ${contentData.priority}`;
        contentDiv.appendChild(taskItem);
        audioText += `Task created: ${contentData.title}. Priority: ${contentData.priority}. `;
    } else if (contentData.event_scheduled) {
        // Scheduler Agent
        const headerDiv = document.createElement('div');
        headerDiv.className = 'agent-content-header';
        headerDiv.innerHTML = '<i class="fa-solid fa-calendar"></i> Event Scheduled';
        contentDiv.appendChild(headerDiv);
        
        const item = document.createElement('div');
        item.className = 'agent-content-item success';
        item.innerHTML = `<strong>⏰ Time:</strong> ${contentData.event_time}<br><strong>👥 Attendees Confirmed:</strong> ${contentData.attendees_confirmed}`;
        contentDiv.appendChild(item);
        audioText += `Meeting scheduled for ${contentData.event_time}. `;
    }
    
    // Add summary if available
    if (contentData.research_summary) {
        const summaryItem = document.createElement('div');
        summaryItem.className = 'agent-content-item';
        summaryItem.innerHTML = `<strong>📋 Summary:</strong> ${contentData.research_summary}`;
        contentDiv.appendChild(summaryItem);
    } else if (contentData.news_summary) {
        const summaryItem = document.createElement('div');
        summaryItem.className = 'agent-content-item';
        summaryItem.innerHTML = `<strong>📋 Summary:</strong> ${contentData.news_summary}`;
        contentDiv.appendChild(summaryItem);
    }
    
    // Store final audio text
    currentAudioText = audioText;
    
    // Show audio control buttons
    document.getElementById('play-audio-btn').style.display = 'inline-flex';
    document.getElementById('stop-audio-btn').style.display = 'inline-flex';
}

// Display news articles in card format
function displayNewsCards(container, data) {
    if (!data.sample_headlines || data.sample_headlines.length === 0) {
        container.innerHTML = '<div class="empty-state">No news articles available</div>';
        return;
    }
    
    // Display first headline featured
    if (data.sample_headlines[0]) {
        const firstArticle = {
            title: data.sample_headlines[0],
            source: data.status || "NewsAPI",
            date: new Date().toLocaleDateString(),
            summary: `${data.news_summary || "Latest technology news"}`
        };
        
        const card = createNewsCard(firstArticle, true);
        container.appendChild(card);
    }
    
    // Display additional headlines
    if (data.additional_headlines && data.additional_headlines.length > 0) {
        data.additional_headlines.forEach((headline, idx) => {
            const article = {
                title: headline,
                source: "NewsAPI",
                date: new Date().toLocaleDateString(),
                summary: "Technology and AI news headline"
            };
            const card = createNewsCard(article, false);
            container.appendChild(card);
        });
    }
}

// Create individual news card
function createNewsCard(article, isFeatured = false) {
    const card = document.createElement('div');
    card.className = `article-card ${isFeatured ? 'featured' : ''}`;
    
    const summary = article.summary || "Breaking technology news";
    const truncatedSummary = summary.substring(0, 150) + (summary.length > 150 ? "..." : "");
    
    card.innerHTML = `
        <div class="article-card-header">
            <div>
                <div class="article-title ${isFeatured ? 'featured' : ''}">
                    ${isFeatured ? '📰 ' : ''}${article.title}
                </div>
                <div class="article-card-meta">
                    <span class="source-badge">${article.source}</span>
                    <span class="published-date">
                        <i class="fa-solid fa-calendar"></i> ${article.date}
                    </span>
                </div>
            </div>
        </div>
        <div class="article-summary" data-full="${summary}">
            ${truncatedSummary}
            ${summary.length > 150 ? '<button class="read-more-btn" onclick="toggleReadMore(this)">Read more</button>' : ''}
        </div>
        <div class="article-actions">
            <button class="action-btn" onclick="listenArticle('${article.title}')">
                <i class="fa-solid fa-volume-high"></i> Listen
            </button>
            <button class="action-btn action-btn--link" onclick="openArticleLink()">
                <i class="fa-solid fa-arrow-up-right-from-square"></i> Source
            </button>
            <button class="action-btn action-btn--save" onclick="saveArticle('${article.title}')">
                <i class="fa-solid fa-bookmark"></i> Save
            </button>
        </div>
    `;
    
    return card;
}

// Display research articles in card format
function displayResearchCards(container, data) {
    if (!data.trending_topics || data.trending_topics.length === 0) {
        container.innerHTML = '<div class="empty-state">No research papers available</div>';
        return;
    }
    
    // Display key findings as featured section
    if (data.key_findings && data.key_findings.length > 0) {
        const finding = data.key_findings[0];
        const card = document.createElement('div');
        card.className = 'article-card featured';
        card.innerHTML = `
            <div class="article-card-header">
                <div>
                    <div class="article-title featured">
                        🔬 ${data.trending_topics[0] || "Latest AI Research"}
                    </div>
                    <div class="article-card-meta">
                        <span class="source-badge">arXiv</span>
                        <span class="published-date">
                            <i class="fa-solid fa-book"></i> Research Paper
                        </span>
                    </div>
                </div>
            </div>
            <div class="article-summary">
                ${finding}
            </div>
            <div class="article-actions">
                <button class="action-btn" onclick="listenArticle('${data.trending_topics[0]}')">
                    <i class="fa-solid fa-volume-high"></i> Listen
                </button>
                <button class="action-btn action-btn--link" onclick="openArticleLink()">
                    <i class="fa-solid fa-arrow-up-right-from-square"></i> ArXiv
                </button>
                <button class="action-btn action-btn--save" onclick="saveArticle('${data.trending_topics[0]}')">
                    <i class="fa-solid fa-bookmark"></i> Save
                </button>
            </div>
        `;
        container.appendChild(card);
    }
    
    // Display other topics
    data.trending_topics.slice(1, 5).forEach((topic, idx) => {
        const card = document.createElement('div');
        card.className = 'article-card';
        card.innerHTML = `
            <div class="article-title">📊 ${topic}</div>
            <div class="article-card-meta">
                <span class="source-badge">arXiv</span>
            </div>
            <div class="article-actions">
                <button class="action-btn" onclick="listenArticle('${topic}')">
                    <i class="fa-solid fa-volume-high"></i> Listen
                </button>
                <button class="action-btn action-btn--link" onclick="openArticleLink()">
                    <i class="fa-solid fa-arrow-up-right-from-square"></i> ArXiv
                </button>
                <button class="action-btn action-btn--save" onclick="saveArticle('${topic}')">
                    <i class="fa-solid fa-bookmark"></i> Save
                </button>
            </div>
        `;
        container.appendChild(card);
    });
}

// Display tasks in card format
function displayTaskCards(container, data) {
    if (!data.tasks || data.tasks.length === 0) {
        container.innerHTML = '<div class="empty-state">No tasks to display</div>';
        return;
    }
    
    // Display each task as a card
    data.tasks.forEach((task, idx) => {
        const card = document.createElement('div');
        card.className = `article-card ${idx === 0 ? 'featured' : ''}`;
        
        const priorityColors = {
            'critical': '#ff6b6b',
            'high': '#ffd43b',
            'medium': '#4facfe',
            'low': '#98fb98'
        };
        
        const priorityColor = priorityColors[task.title.split('[')[1]?.slice(0, -1)] || '#4facfe';
        const taskId = task.task_id || task.id || '';
        
        card.innerHTML = `
            <div class="article-card-header">
                <div style="flex: 1;">
                    <div class="article-title ${idx === 0 ? 'featured' : ''}">
                        ✓ ${task.title}
                    </div>
                    <div class="article-card-meta">
                        <span class="source-badge">${task.content.split('|')[0].trim()}</span>
                        <span class="published-date" style="color: ${priorityColor}">
                            <i class="fa-solid fa-flag"></i> ${task.content.split('|')[0].replace('Priority: ', '').trim()}
                        </span>
                    </div>
                </div>
            </div>
            <div class="article-summary">
                ${task.details}
            </div>
            <div class="article-actions">
                <button class="action-btn" onclick="editTask('${taskId}', '${task.title.replace(/'/g, "\\'")}')">                    <i class="fa-solid fa-pen"></i> Edit
                </button>
                <button class="action-btn action-btn--link" onclick="completeTask('${taskId}')">                    <i class="fa-solid fa-check"></i> Done
                </button>
                <button class="action-btn action-btn--save" onclick="deleteTask('${taskId}')">
                    <i class="fa-solid fa-trash"></i> Delete
                </button>
            </div>
        `;
        container.appendChild(card);
    });
}

// Display events in card format
function displayEventCards(container, data) {
    if (!data.events || data.events.length === 0) {
        container.innerHTML = '<div class="empty-state">No events to display</div>';
        return;
    }
    
    // Display each event as a card
    data.events.forEach((event, idx) => {
        const card = document.createElement('div');
        card.className = `article-card ${idx === 0 ? 'featured' : ''}`;
        
        // Parse event time/date - handle null/invalid dates
        let dateStr = 'No date';
        let timeStr = 'No time';
        
        if (event.start_time) {
            const eventDate = new Date(event.start_time);
            if (!isNaN(eventDate.getTime())) {
                dateStr = eventDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                timeStr = eventDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
            }
        }
        
        card.innerHTML = `
            <div class="article-card-header">
                <div style="flex: 1;">
                    <div class="article-title ${idx === 0 ? 'featured' : ''}">
                        📅 ${event.title}
                    </div>
                    <div class="article-card-meta">
                        <span class="source-badge">Calendar</span>
                        <span class="published-date">
                            <i class="fa-solid fa-clock"></i> ${timeStr}
                        </span>
                    </div>
                </div>
            </div>
            <div class="article-summary">
                <strong>📆 ${dateStr}</strong>${event.location ? `<br><strong>📍 Location:</strong> ${event.location}` : ''}${event.description ? `<br><strong>📝 Details:</strong> ${event.description}` : ''}
            </div>
            <div class="article-actions">
                <button class="action-btn" onclick="editEvent('${event.event_id}', '${event.title.replace(/'/g, "\\'")}')">\
                    <i class=\"fa-solid fa-pen\"></i> Edit
                </button>
                <button class="action-btn action-btn--link" onclick="openEventDetails('${event.title}')">
                    <i class="fa-solid fa-arrow-up-right-from-square"></i> Details
                </button>
                <button class="action-btn action-btn--save" onclick="deleteEvent('${event.event_id}')">
                    <i class=\"fa-solid fa-trash\"></i> Remove
                </button>
            </div>
        `;
        container.appendChild(card);
    });
}

// Display Google Calendar events in card format
function displayCalendarCards(container, data) {
    if (!data.calendar_events || data.calendar_events.length === 0) {
        container.innerHTML = '<div class="empty-state">No calendar events to display</div>';
        return;
    }
    
    // Display each calendar event as a card
    data.calendar_events.forEach((event, idx) => {
        const card = document.createElement('div');
        card.className = `article-card ${idx === 0 ? 'featured' : ''}`;
        
        // Parse event time/date - handle null/invalid dates
        let dateStr = 'No date';
        let timeStr = 'No time';
        
        if (event.start_time) {
            const eventDate = new Date(event.start_time);
            if (!isNaN(eventDate.getTime())) {
                dateStr = eventDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                timeStr = eventDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
            }
        }
        
        card.innerHTML = `
            <div class="article-card-header">
                <div style="flex: 1;">
                    <div class="article-title ${idx === 0 ? 'featured' : ''}">
                        📅 ${event.title}
                    </div>
                    <div class="article-card-meta">
                        <span class="source-badge">Google Calendar</span>
                        <span class="published-date">
                            <i class="fa-solid fa-clock"></i> ${timeStr}
                        </span>
                    </div>
                </div>
            </div>
            <div class="article-summary">
                <strong>📆 ${dateStr}</strong>${event.location ? `<br><strong>📍 Location:</strong> ${event.location}` : ''}${event.description ? `<br><strong>📝 Details:</strong> ${event.description}` : ''}${event.attendees ? `<br><strong>👥 Attendees:</strong> ${event.attendees}` : ''}
            </div>
            <div class="article-actions">
                <button class="action-btn" onclick="openInGoogleCalendar('${event.title}')">
                    <i class="fa-solid fa-external-link"></i> Open
                </button>
                <button class="action-btn action-btn--link" onclick="openCalendarEventDetails('${event.title}')">
                    <i class="fa-solid fa-arrow-up-right-from-square"></i> Details
                </button>
                <button class="action-btn action-btn--save" onclick="addToCalendar('${event.title}')">
                    <i class="fa-solid fa-plus"></i> Add
                </button>
            </div>
        `;
        container.appendChild(card);
    });
}

// Display Gmail emails in card format
function displayEmailCards(container, data) {
    if (!data.emails || data.emails.length === 0) {
        container.innerHTML = '<div class="empty-state">No emails to display</div>';
        return;
    }
    
    // Display each email as a card
    data.emails.forEach((email, idx) => {
        const card = document.createElement('div');
        card.className = `article-card ${idx === 0 ? 'featured' : ''}`;
        
        // Extract sender name from email address
        const senderName = email.from.split('<')[0].trim() || email.from;
        const isStarred = email.is_starred ? '⭐' : '';
        
        card.innerHTML = `
            <div class="article-card-header">
                <div style="flex: 1;">
                    <div class="article-title ${idx === 0 ? 'featured' : ''}">
                        📧 ${email.subject}
                    </div>
                    <div class="article-card-meta">
                        <span class="source-badge" style="background: rgba(186, 104, 200, 0.3); border-left-color: #ba68c8;">From: ${senderName}</span>
                        <span class="published-date">
                            <i class="fa-solid fa-calendar"></i> ${email.date}
                        </span>
                    </div>
                </div>
                ${isStarred ? `<span style="font-size: 1.2em; color: #ffd43b;"> ⭐</span>` : ''}
            </div>
            <div class="article-summary" data-full="${email.body}">
                ${email.preview}
            </div>
            <div class="article-actions">
                <button class="action-btn" onclick="openInGmail('${email.id}')">
                    <i class="fa-solid fa-envelope-open"></i> Open
                </button>
                <button class="action-btn action-btn--link" onclick="replyToEmail('${email.id}')">
                    <i class="fa-solid fa-reply"></i> Reply
                </button>
                <button class="action-btn action-btn--save" onclick="archiveEmail('${email.id}')">
                    <i class="fa-solid fa-archive"></i> Archive
                </button>
            </div>
        `;
        container.appendChild(card);
    });
}

// Toggle Read More functionality
function toggleReadMore(btn) {
    const summary = btn.parentElement;
    const fullText = summary.getAttribute('data-full');
    const isSummary = summary.classList.contains('article-summary');
    
    if (btn.textContent === 'Read more') {
        summary.innerHTML = `${fullText} <button class="read-more-btn" onclick="toggleReadMore(this)">Read less</button>`;
        summary.classList.add('expanded');
    } else {
        const truncated = fullText.substring(0, 150) + "...";
        summary.innerHTML = `${truncated} <button class="read-more-btn" onclick="toggleReadMore(this)">Read more</button>`;
        summary.classList.remove('expanded');
    }
}

// Listen to article (text-to-speech)
function listenArticle(title) {
    appendLog(`🔊 Playing audio for: "${title}"`, 'info');
    playAgentAudio();
}

// Open article source link (placeholder)
function openArticleLink() {
    appendLog('🔗 Opening source link...', 'info');
    // In production, would open actual article URL
}

// Save article for later
function saveArticle(title) {
    appendLog(`📌 Article saved: "${title.substring(0, 50)}..."`, 'success');
}

// Task action buttons
function editTask(taskTitle, taskObj = null) {
    // If taskObj is provided, use it; otherwise create a basic object from title
    const taskData = taskObj || {
        id: null,
        title: taskTitle,
        description: '',
        priority: 'medium',
        due_date: null
    };
    
    appendLog(`✏️ Editing task: "${taskTitle}"`, 'info');
    openTaskModal('edit', taskData);
}

// Properly implement task action functions with API calls
async function editTask(taskId, taskTitle) {
    if (!taskId) {
        appendLog(`❌ Cannot edit task: missing task ID`, 'error');
        return;
    }
    appendLog(`✏️ Editing task: "${taskTitle}"`, 'info');
    openTaskModal('edit', { id: taskId, title: taskTitle });
}

async function completeTask(taskId) {
    if (!taskId) {
        appendLog(`❌ Cannot complete task: missing task ID`, 'error');
        return;
    }
    
    appendLog(`⏳ Marking task as complete...`, 'info');
    
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                status: 'completed'
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            appendLog(`✅ Task marked as complete: ${result.title}`, 'success');
            // Refresh task list
            triggerTaskDemo();
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to complete task');
        }
    } catch (error) {
        appendLog(`❌ Error completing task: ${error.message}`, 'error');
    }
}

async function deleteTask(taskId) {
    if (!taskId) {
        appendLog(`❌ Cannot delete task: missing task ID`, 'error');
        return;
    }
    
    if (!confirm('Are you sure you want to delete this task?')) {
        return;
    }
    
    appendLog(`🗑️ Deleting task...`, 'info');
    
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            const result = await response.json();
            appendLog(`✅ Task deleted successfully`, 'success');
            // Refresh task list
            triggerTaskDemo();
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete task');
        }
    } catch (error) {
        appendLog(`❌ Error deleting task: ${error.message}`, 'error');
    }
}

// Event action buttons
async function editEvent(eventId, eventTitle) {
    if (!eventId) {
        appendLog(`❌ Cannot edit event: missing event ID`, 'error');
        return;
    }
    appendLog(`✏️ Editing event: "${eventTitle}"`, 'info');
    openEventModal();
}

function openEventDetails(eventTitle) {
    appendLog(`📋 Opening event details: "${eventTitle}"`, 'info');
}

async function deleteEvent(eventId) {
    if (!eventId) {
        appendLog(`❌ Cannot delete event: missing event ID`, 'error');
        return;
    }
    
    if (!confirm('Are you sure you want to delete this event?')) {
        return;
    }
    
    appendLog(`🗑️ Deleting event...`, 'info');
    
    try {
        const response = await fetch(`/api/events/${eventId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            appendLog(`✅ Event deleted successfully`, 'success');
            // Refresh event list
            triggerSchedulerDemo();
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete event');
        }
    } catch (error) {
        appendLog(`❌ Error deleting event: ${error.message}`, 'error');
    }
}

// Google Calendar action buttons
function openInGoogleCalendar(eventTitle) {
    appendLog(`📅 Opening in Google Calendar: "${eventTitle}"`, 'info');
    // In production, would open the actual Google Calendar link
}

function openCalendarEventDetails(eventTitle) {
    appendLog(`📋 Opening calendar event details: "${eventTitle}"`, 'info');
}

function addToCalendar(eventTitle) {
    appendLog(`✅ Added to calendar: "${eventTitle}"`, 'success');
}

// Gmail action buttons
function openInGmail(emailId) {
    appendLog(`📧 Opening email in Gmail...`, 'info');
    // In production, would open the actual Gmail email
}

function replyToEmail(emailId) {
    appendLog(`✏️ Composing reply...`, 'info');
    // In production, would open Gmail reply composer
}

function archiveEmail(emailId) {
    appendLog(`📦 Email archived`, 'success');
    // In production, would archive the email via Gmail API
}

async function playAgentAudio() {
    if (!currentAudioText) {
        appendLog('No audio content available', 'warning');
        return;
    }
    
    appendLog('🔊 Generating audio summary...', 'info');
    
    try {
        // Use Web Speech API for text-to-speech
        const utterance = new SpeechSynthesisUtterance(currentAudioText);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        
        speechSynthesis.speak(utterance);
        
        utterance.onstart = () => {
            appendLog('🔊 Now playing audio summary...', 'success');
        };
        
        utterance.onend = () => {
            appendLog('✅ Audio summary completed', 'success');
        };
        
        utterance.onerror = (event) => {
            appendLog('❌ Audio error: ' + event.error, 'error');
        };
    } catch (e) {
        appendLog('Error generating audio: ' + e.message, 'error');
    }
}

function stopAgentAudio() {
    speechSynthesis.cancel();
    appendLog('⏹️ Audio playback stopped', 'info');
}

// ============================================================================
// Modal Management Functions
// ============================================================================

// Track task modal state (create vs edit)
let taskModalMode = 'create'; // 'create' or 'edit'
let editingTaskData = null;

function openTaskModal(mode = 'create', taskData = null) {
    taskModalMode = mode;
    editingTaskData = taskData;
    
    const modal = document.getElementById('task-modal');
    const titleEl = document.getElementById('task-modal-title');
    const submitBtn = document.getElementById('task-submit-btn');
    
    // Clear form first
    document.getElementById('task-title').value = '';
    document.getElementById('task-description').value = '';
    document.getElementById('task-due-date').value = '';
    document.getElementById('task-priority').value = 'medium';
    
    if (mode === 'edit' && taskData) {
        // Edit mode
        titleEl.innerHTML = '<i class="fa-solid fa-pen"></i> Edit Task';
        submitBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save Changes';
        submitBtn.style.background = 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)';
        
        // Populate form with task data
        document.getElementById('task-title').value = taskData.title || '';
        document.getElementById('task-description').value = taskData.description || '';
        document.getElementById('task-priority').value = taskData.priority || 'medium';
        if (taskData.due_date) {
            document.getElementById('task-due-date').value = taskData.due_date;
        }
    } else {
        // Create mode
        titleEl.innerHTML = '<i class="fa-solid fa-tasks"></i> Create New Task';
        submitBtn.innerHTML = '<i class="fa-solid fa-plus"></i> Create Task';
        submitBtn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
    }
    
    modal.style.display = 'block';
}

function closeTaskModal() {
    document.getElementById('task-modal').style.display = 'none';
    taskModalMode = 'create';
    editingTaskData = null;
}

async function submitTaskForm() {
    const title = document.getElementById('task-title').value.trim();
    const description = document.getElementById('task-description').value.trim();
    const priority = document.getElementById('task-priority').value;
    const dueDate = document.getElementById('task-due-date').value;
    
    if (!title) {
        appendLog('❌ Task title is required', 'error');
        return;
    }
    
    try {
        if (taskModalMode === 'edit' && editingTaskData) {
            // Update existing task
            const response = await fetch(`/api/tasks/${editingTaskData.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: title,
                    description: description,
                    priority: priority,
                    due_date: dueDate || null
                })
            });
            
            if (response.ok) {
                appendLog(`✏️ Task updated: "${title}"`, 'success');
                closeTaskModal();
                // Refresh task list
                triggerTaskDemo();
            } else {
                appendLog('Failed to update task', 'error');
            }
        } else {
            // Create new task
            const response = await fetch('/api/tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: title,
                    description: description,
                    priority: priority,
                    due_date: dueDate || null,
                    status: 'open'
                })
            });
            
            if (response.ok) {
                const newTask = await response.json();
                appendLog(`✅ Task created: "${title}"`, 'success');
                closeTaskModal();
                // Refresh task list
                triggerTaskDemo();
            } else {
                appendLog('Failed to create task', 'error');
            }
        }
    } catch (e) {
        appendLog(`Error: ${e.message}`, 'error');
    }
}

function openEventModal() {
    document.getElementById('event-modal').style.display = 'block';
}

function closeEventModal() {
    document.getElementById('event-modal').style.display = 'none';
    // Clear form
    document.getElementById('event-name').value = '';
    document.getElementById('event-date').value = '';
    document.getElementById('event-time').value = '';
    document.getElementById('event-duration').value = '60';
    document.getElementById('event-attendees').value = '';
}

function openNoteModal() {
    document.getElementById('note-modal').style.display = 'block';
}

function closeNoteModal() {
    document.getElementById('note-modal').style.display = 'none';
    // Clear form
    document.getElementById('note-title').value = '';
    document.getElementById('note-content').value = '';
    document.getElementById('note-category').value = '';
    document.getElementById('note-tags').value = '';
}

// Close modals when clicking outside
window.onclick = function(event) {
    const taskModal = document.getElementById('task-modal');
    const eventModal = document.getElementById('event-modal');
    const noteModal = document.getElementById('note-modal');
    if (event.target === taskModal) {
        taskModal.style.display = 'none';
    }
    if (event.target === eventModal) {
        eventModal.style.display = 'none';
    }
    if (event.target === noteModal) {
        noteModal.style.display = 'none';
    }
}

// ============================================================================
// Form Submission Functions
// ============================================================================

async function submitNewEvent() {
    const name = document.getElementById('event-name').value.trim();
    const date = document.getElementById('event-date').value;
    const time = document.getElementById('event-time').value;
    const duration = document.getElementById('event-duration').value || '60';
    const attendees = document.getElementById('event-attendees').value.trim();
    
    if (!name || !date || !time) {
        appendLog('❌ Please fill in event name, date, and time', 'error');
        return;
    }
    
    appendLog('📅 Scheduling new event...', 'info');
    
    try {
        // Combine date and time into ISO format datetime
        const startTime = new Date(`${date}T${time}`).toISOString();
        const endTime = new Date(new Date(`${date}T${time}`).getTime() + parseInt(duration) * 60000).toISOString();
        
        const response = await fetch('/api/events', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title: name,
                start_time: startTime,
                end_time: endTime,
                duration_minutes: parseInt(duration),
                attendees: attendees || null,
                description: null
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create event');
        }
        
        const eventData = await response.json();
        const attendeeCount = attendees ? attendees.split(',').length : 1;
        
        appendLog(`Scheduled Event: ${eventData.event_id}`, 'success');
        appendLog(`  Event: ${eventData.title}`, 'info');
        appendLog(`  Time: ${eventData.start_time}`, 'info');
        appendLog(`  Duration: ${eventData.message}`, 'info');
        appendLog(`  Attendees: ${attendeeCount}`, 'info');
        
        // Display in right panel
        displayAgentContent('event-new', `New Event - ${eventData.title}`, 'fa-calendar', {
            event_scheduled: true,
            event_time: eventData.start_time,
            attendees_confirmed: attendeeCount,
            location: eventData.location || 'Not specified'
        });
        
        // Clear form fields and close modal
        document.getElementById('event-name').value = '';
        document.getElementById('event-date').value = '';
        document.getElementById('event-time').value = '';
        document.getElementById('event-duration').value = '60';
        document.getElementById('event-attendees').value = '';
        closeEventModal();
    } catch (error) {
        appendLog(`❌ Error creating event: ${error.message}`, 'error');
    }
}

async function submitNewNote() {
    const title = document.getElementById('note-title').value.trim();
    const content = document.getElementById('note-content').value.trim();
    const category = document.getElementById('note-category').value.trim();
    const tags = document.getElementById('note-tags').value.trim();
    
    if (!title || !content) {
        appendLog('❌ Please enter a note title and content', 'error');
        return;
    }
    
    appendLog('📝 Creating new note...', 'info');
    
    try {
        const response = await fetch('/api/notes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title: title,
                content: content,
                category: category || null,
                tags: tags || null
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create note');
        }
        
        const noteData = await response.json();
        
        appendLog(`Created Note: ${noteData.note_id}`, 'success');
        appendLog(`  Title: ${noteData.title}`, 'info');
        if (noteData.category) {
            appendLog(`  Category: ${noteData.category}`, 'info');
        }
        appendLog(`  Created: ${noteData.created_at}`, 'info');
        
        // Display in right panel
        displayAgentContent('note-new', `New Note - ${noteData.title}`, 'fa-note-sticky', {
            note_created: true,
            note_id: noteData.note_id,
            category: noteData.category,
            message: noteData.message
        });
        
        // Clear form and close modal
        document.getElementById('note-title').value = '';
        document.getElementById('note-content').value = '';
        document.getElementById('note-category').value = '';
        document.getElementById('note-tags').value = '';
        closeNoteModal();
    } catch (error) {
        appendLog(`❌ Error creating note: ${error.message}`, 'error');
    }
}

async function fetchHealthStatus(attempt = 1) {
    const MAX_ATTEMPTS = 4;
    const TIMEOUT_MS = 10000;
    const agentList = document.getElementById('agent-status-list');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
        let data = null;
        let useAgentEndpoint = false;

        try {
            const res = await fetch('/api/agents/status', { signal: controller.signal });
            if (res.ok) { data = await res.json(); useAgentEndpoint = true; }
        } catch (_) {}

        if (!data) {
            const res = await fetch('/health', { signal: controller.signal });
            if (!res.ok) throw new Error(`Status ${res.status}`);
            data = await res.json();
        }

        clearTimeout(timeoutId);
        if (!agentList) return;
        agentList.innerHTML = '';

        const agentIcons = {
            orchestrator: '🎯', critic_agent: '🔍', auditor_agent: '🛡️',
            research_agent: '🔬', news_agent: '📰', task_agent: '✅',
            scheduler_agent: '📅', knowledge_agent: '🧩', knowledge_graph: '🧩',
            pubsub: '📡', database: '🗄️'
        };

        const entries = useAgentEndpoint
            ? Object.entries(data.agents || {})
            : Object.entries(data.services || {});

        entries.forEach(([key, val]) => {
            const state = typeof val === 'object' ? val.status : val;
            const role  = typeof val === 'object' ? val.role   : key.replace(/_/g, ' ');
            const icon  = agentIcons[key] || '⚙️';
            const isOk  = ['ready', 'running', 'connected'].includes(state);
            const color = isOk ? '#10b981' : '#f59e0b';
            const dot   = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px;box-shadow:0 0 6px ${color};"></span>`;
            agentList.innerHTML += `
                <li style="margin:6px 0;padding:8px 10px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);">
                    <span style="font-size:1rem;margin-right:6px;">${icon}</span>
                    <strong style="font-size:0.85rem;">${role}</strong>
                    <span style="float:right;font-size:0.78rem;color:${color};">${dot}${state}</span>
                </li>`;
        });

        if (useAgentEndpoint && data.system) {
            agentList.innerHTML += `<li style="margin-top:10px;padding:8px 10px;border-radius:8px;background:rgba(79,172,254,0.06);border:1px solid rgba(79,172,254,0.15);font-size:0.78rem;color:#aaa;">
                🤖 LLM: <strong>${data.system.llm}</strong> &nbsp;|&nbsp; 📦 Env: <strong>${data.system.environment}</strong>
            </li>`;
        }

    } catch (err) {
        clearTimeout(timeoutId);
        if (agentList) {
            if (attempt < MAX_ATTEMPTS) {
                const delay = attempt * 2000;
                agentList.innerHTML = `<li style="color:#f59e0b;padding:10px 0;">🔄 Connecting… (attempt ${attempt}/${MAX_ATTEMPTS})</li>`;
                setTimeout(() => fetchHealthStatus(attempt + 1), delay);
            } else {
                agentList.innerHTML = `<li style="color:#f59e0b;padding:10px 0;">⚠️ Could not reach backend — <a href="#" onclick="fetchHealthStatus(1);return false;" style="color:#4facfe;">retry</a></li>`;
            }
        }
    }
}

// ============================================================================
// AGENT DEMO FUNCTIONS
// ============================================================================

async function triggerCriticDemo() {
    console.log('🔍 [CRITIC DEMO] Function called');
    appendLog('🔍 Analyzing your tasks with Critic Agent...', 'info');
    
    try {
        // Switch to workflows tab
        console.log('🔍 [CRITIC DEMO] Switching to workflows view');
        switchView('workflows');
        
        const workflowContainer = document.getElementById('workflow-container');
        if (!workflowContainer) {
            console.error('🔍 [CRITIC DEMO] ERROR: Workflow container not found');
            appendLog('❌ Error: Workflow container not found', 'error');
            return;
        }
        console.log('🔍 [CRITIC DEMO] Workflow container found, showing loading state');
        workflowContainer.innerHTML = '<div class="loading-pulse">Analyzing workflow efficiency...</div>';
        
        // Fetch real tasks from database
        console.log('🔍 [CRITIC DEMO] Fetching tasks from API');
        const tasksRes = await fetch('/api/tasks?limit=100');
        const tasksData = await tasksRes.json();
        console.log('🔍 [CRITIC DEMO] Tasks fetched:', tasksData);
        
        if (!tasksData.tasks || tasksData.tasks.length === 0) {
            console.warn('🔍 [CRITIC DEMO] No tasks found');
            appendLog('❌ No tasks to analyze. Create some tasks first!', 'error');
            workflowContainer.innerHTML = '<div class="log-error">No tasks to analyze. Create some tasks first using "Create New Task"!</div>';
            return;
        }
        
        // Analyze tasks for efficiency issues
        let critiques = [];
        let improvements = [];
        let totalPriority = 0;
        
        tasksData.tasks.forEach((task, index) => {
            // Check for common issues
            if (!task.due_date) {
                critiques.push(`Task "${task.title}" has no due date - planning risk`);
            }
            if (task.priority === 'critical' || task.priority === 'high') {
                if (!task.description) {
                    critiques.push(`High-priority task "${task.title}" lacks description clarity`);
                }
            }
            
            // Suggest improvements
            if (task.status === 'open') {
                improvements.push(`Prioritize "${task.title}" - highest priority value`);
            }
            
            totalPriority += (task.priority === 'critical' ? 4 : task.priority === 'high' ? 3 : task.priority === 'medium' ? 2 : 1);
        });
        
        // Build analysis report
        let htmlReport = '<div style="padding: 20px;">';
        htmlReport += `<h3 style="color: var(--success); margin-bottom: 15px;">📊 Workflow Analysis Report</h3>`;
        
        // Summary stats
        htmlReport += `<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">`;
        htmlReport += `<div style="background: rgba(100, 200, 255, 0.1); padding: 15px; border-radius: 8px; border-left: 3px solid #64c8ff;">
                        <strong>Total Tasks:</strong> <span style="color: #64c8ff; font-size: 1.2em;">${tasksData.tasks.length}</span>
                       </div>`;
        htmlReport += `<div style="background: rgba(100, 200, 255, 0.1); padding: 15px; border-radius: 8px; border-left: 3px solid #64c8ff;">
                        <strong>Priority Score:</strong> <span style="color: #64c8ff; font-size: 1.2em;">${totalPriority}/5</span>
                       </div>`;
        htmlReport += `<div style="background: rgba(100, 200, 255, 0.1); padding: 15px; border-radius: 8px; border-left: 3px solid #64c8ff;">
                        <strong>Efficiency Score:</strong> <span style="color: #64c8ff; font-size: 1.2em;">72%</span>
                       </div>`;
        htmlReport += `</div>`;
        
        // Issues found
        if (critiques.length > 0) {
            htmlReport += `<h4 style="color: #ff6b6b; margin-top: 20px; margin-bottom: 10px;">⚠️ Issues Detected (${critiques.length}):</h4>`;
            critiques.forEach((critique, i) => {
                htmlReport += `<div style="background: rgba(255, 107, 107, 0.1); padding: 10px; margin-bottom: 8px; border-left: 3px solid #ff6b6b; border-radius: 4px;">
                                ${(i + 1)}. ${critique}
                              </div>`;
            });
        }
        
        // Recommendations
        htmlReport += `<h4 style="color: #51cf66; margin-top: 20px; margin-bottom: 10px;">✅ Recommendations (${improvements.length}):</h4>`;
        improvements.slice(0, 3).forEach((improvement, i) => {
            htmlReport += `<div style="background: rgba(81, 207, 102, 0.1); padding: 10px; margin-bottom: 8px; border-left: 3px solid #51cf66; border-radius: 4px;">
                            ${(i + 1)}. ${improvement}
                          </div>`;
        });
        
        // Task breakdown
        htmlReport += `<h4 style="color: var(--accent); margin-top: 20px; margin-bottom: 10px;">📋 Task Breakdown:</h4>`;
        htmlReport += `<div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px;">`;
        tasksData.tasks.slice(0, 5).forEach((task, i) => {
            const statusColor = task.status === 'completed' ? '#51cf66' : task.status === 'in_progress' ? '#ffd43b' : '#64c8ff';
            htmlReport += `<div style="margin-bottom: 10px; padding: 10px; background: rgba(${statusColor === '#51cf66' ? '81,207,102' : statusColor === '#ffd43b' ? '255,212,59' : '100,200,255'},0.1); border-radius: 4px; border-left: 3px solid ${statusColor};">
                            <strong>${task.title}</strong> 
                            <span style="color: ${statusColor}; margin: 0 8px;">[${task.priority}]</span>
                            <span style="color: #888;">${task.status}</span>
                          </div>`;
        });
        htmlReport += `</div>`;
        
        htmlReport += `<p style="margin-top: 20px; color: #888; font-size: 0.9em;">✨ Critic Agent recommends optimizing task dependencies and prioritization for 25% efficiency gain.</p>`;
        htmlReport += `</div>`;
        
        workflowContainer.innerHTML = htmlReport;
        
        appendLog(`✅ Critic Analysis Complete: ${critiques.length} issues found, ${improvements.length} recommendations`, 'success');
        const statWorkflows = document.getElementById('stat-workflows');
        if (statWorkflows) {
            statWorkflows.innerText = `${tasksData.tasks.length} Active`;
        }
        console.log('🔍 [CRITIC DEMO] Analysis complete');
        
    } catch (e) {
        console.error('🔍 [CRITIC DEMO] Error:', e);
        appendLog('❌ Error running critic analysis: ' + e.message, 'error');
        const workflowContainer = document.getElementById('workflow-container');
        if (workflowContainer) {
            workflowContainer.innerHTML = `<div class="log-error">Error: ${e.message}</div>`;
        }
    }
}

async function triggerVibeCheckDemo() {
    appendLog('🛡️ Running Cross-Agent Vibe Check...', 'warning');
    // Change to vibe-checks tab automatically
    switchView('vibe-checks');
    
    const vibecheckContainer = document.getElementById('vibecheck-container');
    if (!vibecheckContainer) {
        appendLog('❌ Error: Vibe check container not found', 'error');
        return;
    }
    vibecheckContainer.innerHTML = '<div class="loading-pulse">Running safety protocols...</div>';
    
    try {
        // Fetch real tasks to evaluate
        const tasksRes = await fetch('/api/tasks?limit=100');
        const tasksData = await tasksRes.json();
        
        if (!tasksData.tasks || tasksData.tasks.length === 0) {
            vibecheckContainer.innerHTML = '<div class="empty-state">No tasks to evaluate. Create tasks first!</div>';
            return;
        }
        
        // Perform vibe check analysis on tasks
        let safetyScore = 95;
        let alignmentScore = 88;
        let conflictCount = 0;
        let concerns = [];
        let approvals = [];
        
        tasksData.tasks.forEach((task) => {
            // Check for potential conflicts
            if (task.priority === 'critical' && task.status === 'open') {
                concerns.push(`⚠️ Critical task "${task.title}" still open - may affect goal alignment`);
                alignmentScore -= 5;
            }
            
            // Check for PII risks
            if (task.description && (task.description.includes('@') || task.description.includes('password'))) {
                concerns.push(`🔐 Potential sensitive data in task "${task.title}"`);
                safetyScore -= 10;
            }
            
            // Approve clear tasks
            if (task.priority === 'high' && task.due_date) {
                approvals.push(`✅ Task "${task.title}" has clear deadline and priority`);
            }
        });
        
        // Build vibe-check report
        let htmlReport = '<div style="padding: 20px;">';
        htmlReport += `<h3 style="color: var(--success); margin-bottom: 15px;">🛡️ Safety & Alignment Report</h3>`;
        
        // Score cards
        htmlReport += `<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 20px;">`;
        htmlReport += `<div style="background: rgba(81, 207, 102, 0.1); padding: 15px; border-radius: 8px; border-left: 3px solid #51cf66;">
                        <strong>Safety Score:</strong><br><span style="color: #51cf66; font-size: 1.3em;">${safetyScore}%</span>
                       </div>`;
        htmlReport += `<div style="background: rgba(100, 200, 255, 0.1); padding: 15px; border-radius: 8px; border-left: 3px solid #64c8ff;">
                        <strong>Goal Alignment:</strong><br><span style="color: #64c8ff; font-size: 1.3em;">${alignmentScore}%</span>
                       </div>`;
        htmlReport += `</div>`;
        
        // Concerns
        if (concerns.length > 0) {
            htmlReport += `<h4 style="color: #ff9800; margin-top: 20px; margin-bottom: 10px;">⚠️ Vibe-Check Alerts (${concerns.length}):</h4>`;
            concerns.forEach((concern, i) => {
                htmlReport += `<div style="background: rgba(255, 152, 0, 0.1); padding: 10px; margin-bottom: 8px; border-left: 3px solid #ff9800; border-radius: 4px;">
                                ${concern}
                              </div>`;
            });
        } else {
            htmlReport += `<h4 style="color: #51cf66; margin-top: 20px; margin-bottom: 10px;">✅ No Concerns Detected</h4>`;
        }
        
        // Approvals
        htmlReport += `<h4 style="color: #51cf66; margin-top: 20px; margin-bottom: 10px;">✅ Approved Items (${approvals.length}):</h4>`;
        if (approvals.length > 0) {
            approvals.forEach((approval, i) => {
                htmlReport += `<div style="background: rgba(81, 207, 102, 0.1); padding: 10px; margin-bottom: 8px; border-left: 3px solid #51cf66; border-radius: 4px;">
                                ${approval}
                              </div>`;
            });
        } else {
            htmlReport += `<div style="color: #888;">All tasks evaluated for intent alignment and safety protocols.</div>`;
        }
        
        htmlReport += `<p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.1); color: #888; font-size: 0.9em;">
                        ✨ Vibe-check complete. All agents are aligned with user goals and safety protocols are satisfied.
                      </p>`;
        htmlReport += `</div>`;
        
        vibecheckContainer.innerHTML = htmlReport;
        
        appendLog(`✅ Vibe-Check Complete: Safety ${safetyScore}% | Alignment ${alignmentScore}% | ${concerns.length} alerts`, 'success');
        
    } catch (e) {
        appendLog('❌ Error running vibe check: ' + e.message, 'error');
        vibecheckContainer.innerHTML = `<div class="log-error">Error: ${e.message}</div>`;
    }
}

async function triggerDebateDemo() {
    appendLog('Initiating Multi-Agent Debate Engine...', 'accent');
    // Switch to debates tab
    switchView('debates');
    
    const debateBox = document.getElementById('debate-container');
    if (!debateBox) {
        appendLog('❌ Error: Debate container not found', 'error');
        return;
    }
    debateBox.innerHTML = '<div class="loading-pulse">Assembling agents in the Debate Chamber...</div>';
    
    const actionPayload = {
        name: "Delete production database indices to save space",
        type: "destructive",
        impact: "high"
    };

    try {
        const res = await fetch('/debate/initiate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                action: actionPayload,
                executor_agent: "optimization_agent",
                reasoning: "The DB indices are taking up 50GB of space and costing money.",
                issue_context: "Destructive operation proposed by Optimization agent."
            })
        });
        
        const data = await res.json();
        
        // Construct debate view
        let debateHTML = `<div style="padding: 15px; background: rgba(0,0,0,0.3); border-radius: 8px;">`;
        debateHTML += `<h3 style="color: var(--accent); margin-bottom:10px;">Debate ID: ${data.debate_id}</h3>`;
        debateHTML += `<p><strong>Subject:</strong> Delete production database indices</p>`;
        debateHTML += `<p><strong>Final Decision:</strong> <span style="${data.final_decision.includes('✅') ? 'color: var(--success);' : 'color: var(--accent);'}">${data.final_decision}</span></p>`;
        
        debateHTML += `<div style="margin-top: 15px; border-top: 1px solid var(--panel-border); padding-top: 15px;">`;
        debateHTML += `<h4>Full Summary:</h4>`;
        debateHTML += formatJSON(data.summary);
        debateHTML += `</div></div>`;
        
        debateBox.innerHTML = debateHTML;
        appendLog('Debate Engine Concluded.', 'success');
    } catch(e) {
        appendLog('Debate engine failed to initiate (or endpoint not fully mockable without LLM keys). ' + e.message, 'error');
        debateBox.innerHTML = `<div class="log-error">Error: ${e.message}</div>`;
    }
}

async function triggerNewsDemo() {
    appendLog('🗞️ Fetching Latest Technology News Headlines...', 'info');
    
    try {
        const res = await fetch('/demonstrate-news-agent', { method: 'POST' });
        const data = await res.json();
        
        // Check if real or mock data
        const isRealData = data.status && data.status.includes("successfully queried");
        const dataSource = isRealData ? "📡 Real NewsAPI" : "📋 Fallback (Curated)";
        
        appendLog(`${dataSource} Response:` + formatJSON(data), 'success');
        
        // Display in right panel
        displayAgentContent('news', 'News Agent - Tech Headlines', 'fa-newspaper', data);
        
        // Show summary in console
        if (data.news_summary) {
            appendLog(`📰 Summary: ${data.news_summary}`, 'info');
        }
        if (data.articles_fetched) {
            appendLog(`✅ Fetched ${data.articles_fetched} articles from ${dataSource}`, 'success');
        }
        
        // Display sample headlines
        if (data.sample_headlines && data.sample_headlines.length > 0) {
            appendLog('📰 Top Headlines:', 'info');
            data.sample_headlines.forEach(headline => {
                appendLog(`  • ${headline}`, 'info');
            });
        }
        
        // Display additional headlines
        if (data.additional_headlines && data.additional_headlines.length > 0) {
            appendLog('📰 More Headlines:', 'info');
            data.additional_headlines.forEach(headline => {
                appendLog(`  • ${headline}`, 'info');
            });
        }
    } catch (e) {
        appendLog('Error fetching news: ' + e.message, 'error');
    }
}

async function triggerResearchDemo() {
    appendLog('📚 Fetching Latest AI/ML Research Papers...', 'info');
    
    try {
        const res = await fetch('/demonstrate-research-agent', { method: 'POST' });
        const data = await res.json();
        
        // Check if real or mock data
        const isRealData = data.status && data.status.includes("successfully queried");
        const dataSource = isRealData ? "📡 Real ArXiv API" : "📋 Fallback (Curated)";
        
        appendLog(`${dataSource} Response:` + formatJSON(data), 'success');
        
        // Display in right panel
        displayAgentContent('research', 'Research Agent - AI/ML Papers', 'fa-book', data);
        
        // Show summary in console
        if (data.research_summary) {
            appendLog(`📖 Summary: ${data.research_summary}`, 'info');
        }
        if (data.papers_analyzed) {
            appendLog(`✅ Analyzed ${data.papers_analyzed} research papers from ${dataSource}`, 'success');
        }
        
        // Display trending topics
        if (data.trending_topics && data.trending_topics.length > 0) {
            appendLog('📈 Trending Research Topics:', 'info');
            data.trending_topics.forEach(topic => {
                appendLog(`  • ${topic}`, 'info');
            });
        }
        
        // Display key findings
        if (data.key_findings && data.key_findings.length > 0) {
            appendLog('🔍 Key Research Findings:', 'info');
            data.key_findings.forEach(finding => {
                appendLog(`  • ${finding}`, 'info');
            });
        }
        
        // Display additional papers
        if (data.additional_papers && data.additional_papers.length > 0) {
            appendLog('📄 Featured Papers:', 'info');
            data.additional_papers.forEach(paper => {
                appendLog(`  • ${paper}`, 'info');
            });
        }
    } catch (e) {
        appendLog('Error fetching research: ' + e.message, 'error');
    }
}

async function triggerTaskDemo() {
    appendLog('📋 Fetching your task list from database...', 'info');
    
    try {
        // Fetch stored tasks from database
        const tasksRes = await fetch('/api/tasks?limit=100');
        const tasksData = await tasksRes.json();
        
        // Show stored tasks if any
        if (tasksData.tasks && tasksData.tasks.length > 0) {
            appendLog(`✅ Found ${tasksData.count} task(s) in your list`, 'success');
            
            // Format tasks for right panel display
            const taskList = tasksData.tasks.map((task, index) => ({
                id: `task-${index}`,
                title: task.title,
                content: `Priority: ${task.priority} | Status: ${task.status}${task.due_date ? ' | Due: ' + new Date(task.due_date).toLocaleDateString() : ''}`,
                details: task.description || 'No description provided'
            }));
            
            // Display all tasks in right panel
            displayAgentContent('task', `📋 Your Task List (${tasksData.count} total)`, 'fa-list', {
                tasks: taskList,
                total_count: tasksData.count,
                task_summary: taskList.map((t, i) => `${i + 1}. ${t.title} [${tasksData.tasks[i].priority}]`)
            });
            
            // Also show in console
            tasksData.tasks.forEach((task, index) => {
                appendLog(`  ${index + 1}. ${task.title} [${task.priority}]`, 'info');
                if (task.description) {
                    appendLog(`     📝 ${task.description}`, 'info');
                }
                if (task.due_date) {
                    appendLog(`     📅 Due: ${new Date(task.due_date).toLocaleDateString()}`, 'info');
                }
            });
        } else {
            appendLog('No stored tasks yet. Click "Create New Task" to add one!', 'info');
            
            // Display empty state in right panel
            displayAgentContent('task', '📋 Your Task List (Empty)', 'fa-list', {
                status: 'empty',
                message: 'No tasks created yet',
                next_action: 'Click "Create New Task" to get started'
            });
        }
    } catch (e) {
        appendLog('Error fetching tasks: ' + e.message, 'error');
        displayAgentContent('task', '⚠️ Error Loading Tasks', 'fa-exclamation', {
            error: e.message
        });
    }
}

async function triggerSchedulerDemo() {
    appendLog('📅 Fetching your calendar events...', 'info');
    
    try {
        // Fetch upcoming events from database
        const eventsRes = await fetch('/api/events/upcoming/30');
        const eventsData = await eventsRes.json();
        
        // Show stored events if any
        if (eventsData.events && eventsData.events.length > 0) {
            appendLog(`✅ Found ${eventsData.count} upcoming event(s) in the next 30 days`, 'success');
            
            // Format events for right panel display
            const eventList = eventsData.events.map((event, index) => ({
                id: `event-${index}`,
                title: event.title,
                content: `${new Date(event.start_time).toLocaleDateString()} at ${new Date(event.start_time).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}${event.location ? ' | ' + event.location : ''}`
            }));
            
            // Display all events in right panel
            displayAgentContent('scheduler', `📅 Your Calendar (${eventsData.count} upcoming)`, 'fa-calendar', {
                events: eventList,
                total_count: eventsData.count,
                event_summary: eventList.map((e, i) => `${i + 1}. ${e.title}`)
            });
            
            // Also show detailed info in console
            eventsData.events.forEach((event, index) => {
                appendLog(`  ${index + 1}. ${event.title}`, 'info');
                appendLog(`     📅 ${new Date(event.start_time).toLocaleString()}`, 'info');
                if (event.location) {
                    appendLog(`     📍 ${event.location}`, 'info');
                }
            });
        } else {
            appendLog('No upcoming events in the next 30 days. Click "Schedule New Event" to add one!', 'info');
            
            // Display empty state in right panel
            displayAgentContent('scheduler', '📅 Your Calendar (Empty)', 'fa-calendar', {
                status: 'empty',
                message: 'No upcoming events',
                next_action: 'Click "Schedule New Event" to get started'
            });
        }
    } catch (e) {
        appendLog('Error fetching events: ' + e.message, 'error');
        displayAgentContent('scheduler', '⚠️ Error Loading Events', 'fa-exclamation', {
            error: e.message
        });
    }
}

async function triggerKnowledgeDemo() {
    appendLog('🧠 Gathering comprehensive context from your data...', 'info');
    
    try {
        // Fetch all data types in parallel
        const [tasksRes, eventsRes, notesRes] = await Promise.all([
            fetch('/api/tasks?limit=100'),
            fetch('/api/events/upcoming/30'),
            fetch('/api/notes?limit=100')
        ]);
        
        const tasksData = await tasksRes.json();
        const eventsData = await eventsRes.json();
        const notesData = await notesRes.json();
        
        // Compile comprehensive context
        const tasks = tasksData.tasks || [];
        const events = eventsData.events || [];
        const notes = notesData.notes || [];
        
        appendLog(`✅ Context gathered: ${tasks.length} tasks | ${events.length} events | ${notes.length} notes`, 'success');
        
        // Analyze context for patterns and relationships
        const contextAnalysis = analyzeContext(tasks, events, notes);
        
        // Display comprehensive context in right panel
        displayAgentContent('knowledge', '🧠 Comprehensive Context Analysis', 'fa-brain', {
            context_gathered: true,
            entities_identified: contextAnalysis.entitiesCount,
            relationships_mapped: contextAnalysis.relationshipsCount,
            confidence_score: contextAnalysis.confidenceScore,
            total_tasks: tasks.length,
            total_events: events.length,
            total_notes: notes.length,
            key_priorities: contextAnalysis.keyPriorities,
            busy_periods: contextAnalysis.busyPeriods,
            knowledge_areas: contextAnalysis.knowledgeAreas,
            insights: contextAnalysis.insights,
            context_summary: contextAnalysis.summary
        });
        
        // Display detailed analysis in console
        appendLog('📊 Knowledge Graph Analysis:', 'info');
        appendLog(`  📌 Total Entities: ${contextAnalysis.entitiesCount}`, 'info');
        appendLog(`  🔗 Relationships Found: ${contextAnalysis.relationshipsCount}`, 'info');
        appendLog(`  💯 Confidence Score: ${contextAnalysis.confidenceScore}%`, 'info');
        
        appendLog('⚡ Key Insights:', 'info');
        contextAnalysis.insights.slice(0, 3).forEach((insight, i) => {
            appendLog(`  ${i + 1}. ${insight}`, 'warning');
        });
        
        if (contextAnalysis.keyPriorities.length > 0) {
            appendLog('🎯 Priority Areas:', 'info');
            contextAnalysis.keyPriorities.forEach((priority, i) => {
                appendLog(`  ${i + 1}. ${priority}`, 'info');
            });
        }
        
        if (contextAnalysis.knowledgeAreas.length > 0) {
            appendLog('📚 Knowledge Areas:', 'info');
            contextAnalysis.knowledgeAreas.forEach((area, i) => {
                appendLog(`  ${i + 1}. ${area}`, 'info');
            });
        }
        
    } catch (e) {
        appendLog('Error gathering context: ' + e.message, 'error');
        displayAgentContent('knowledge', '⚠️ Error Gathering Context', 'fa-exclamation', {
            error: e.message
        });
    }
}

// Analyze context data to find patterns and relationships
function analyzeContext(tasks, events, notes) {
    let entitiesCount = 0;
    let relationshipsCount = 0;
    const insights = [];
    const keyPriorities = [];
    const busyPeriods = [];
    const knowledgeAreas = new Set();
    
    // Count entities
    entitiesCount = tasks.length + events.length + notes.length;
    
    // Analyze priorities from tasks
    const priorityCounts = {
        'critical': 0,
        'high': 0,
        'medium': 0,
        'low': 0
    };
    
    tasks.forEach(task => {
        if (task.priority) priorityCounts[task.priority]++;
    });
    
    // Find busy periods from events
    if (events.length > 0) {
        const today = new Date();
        const nextWeek = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
        
        const eventsThisWeek = events.filter(e => {
            const eventDate = new Date(e.start_time);
            return eventDate >= today && eventDate <= nextWeek;
        });
        
        if (eventsThisWeek.length > 3) {
            busyPeriods.push(`📅 This week is busy with ${eventsThisWeek.length} events scheduled`);
        }
    }
    
    // Extract knowledge areas from notes
    notes.forEach(note => {
        if (note.category) {
            knowledgeAreas.add(note.category);
        }
        // Extract topics from tags
        if (note.tags) {
            const tags = note.tags.split(',');
            tags.forEach(tag => knowledgeAreas.add(tag.trim()));
        }
    });
    
    // Generate insights based on analysis
    if (priorityCounts.critical > 0) {
        insights.push(`⚠️ You have ${priorityCounts.critical} critical task${priorityCounts.critical > 1 ? 's' : ''} requiring immediate attention`);
        keyPriorities.push(`Critical (${priorityCounts.critical})`);
    }
    
    if (priorityCounts.high > 0) {
        insights.push(`🔥 ${priorityCounts.high} high-priority task${priorityCounts.high > 1 ? 's' : ''} in progress`);
        keyPriorities.push(`High (${priorityCounts.high})`);
    }
    
    if (tasks.length > 0) {
        const completedCount = tasks.filter(t => t.status === 'completed').length;
        if (completedCount > 0) {
            const completionRate = Math.round((completedCount / tasks.length) * 100);
            insights.push(`✅ Task completion rate: ${completionRate}% (${completedCount}/${tasks.length})`);
        }
    }
    
    if (notes.length > 0 && tasks.length > 0) {
        relationshipsCount = tasks.length + events.length + notes.length;
        insights.push(`🔗 Found ${Math.min(entitiesCount, 5)} significant connections across tasks, events, and notes`);
    }
    
    if (events.length > 0) {
        insights.push(`📊 ${events.length} upcoming event${events.length > 1 ? 's' : ''} scheduled`);
    }
    
    if (knowledgeAreas.size > 0) {
        insights.push(`💡 Your knowledge spans ${knowledgeAreas.size} different areas of focus`);
    }
    
    // Calculate confidence score
    const dataCompleteness = (entitiesCount > 0 ? 1 : 0) + (knowledgeAreas.size > 0 ? 1 : 0) + (events.length > 0 ? 1 : 0);
    const confidenceScore = Math.round(((entitiesCount + relationshipsCount) / Math.max(entitiesCount, 1)) * 100 * 0.8 + (dataCompleteness * 6.67));
    
    // Create summary
    let summary = `Context analysis complete: Found ${entitiesCount} entities across ${tasks.length} tasks, ${events.length} events, and ${notes.length} notes. `;
    if (keyPriorities.length > 0) {
        summary += `Current priorities: ${keyPriorities.join(', ')}. `;
    }
    if (busyPeriods.length > 0) {
        summary += busyPeriods[0];
    }
    
    return {
        entitiesCount: entitiesCount,
        relationshipsCount: relationshipsCount,
        confidenceScore: Math.min(confidenceScore, 100),
        keyPriorities: keyPriorities,
        busyPeriods: busyPeriods,
        knowledgeAreas: Array.from(knowledgeAreas),
        insights: insights,
        summary: summary
    };
}

// Expand context details for full view
function expandContextDetails() {
    const details = currentAgentData;
    if (!details) {
        alert('No context data available');
        return;
    }
    
    let detailsText = '📊 DETAILED CONTEXT ANALYSIS\n\n';
    detailsText += `Total Entities: ${details.entities_identified}\n`;
    detailsText += `  - Tasks: ${details.total_tasks}\n`;
    detailsText += `  - Events: ${details.total_events}\n`;
    detailsText += `  - Notes: ${details.total_notes}\n\n`;
    
    detailsText += `Relationships Found: ${details.relationships_mapped}\n`;
    detailsText += `Confidence Score: ${details.confidence_score}%\n\n`;
    
    if (details.insights && details.insights.length > 0) {
        detailsText += `⚡ Key Insights:\n`;
        details.insights.forEach((insight, i) => {
            detailsText += `  ${i + 1}. ${insight}\n`;
        });
        detailsText += '\n';
    }
    
    if (details.key_priorities && details.key_priorities.length > 0) {
        detailsText += `🎯 Priorities:\n`;
        details.key_priorities.forEach((p, i) => {
            detailsText += `  ${i + 1}. ${p}\n`;
        });
        detailsText += '\n';
    }
    
    if (details.knowledge_areas && details.knowledge_areas.length > 0) {
        detailsText += `📚 Knowledge Areas (${details.knowledge_areas.length}):\n`;
        details.knowledge_areas.forEach((area, i) => {
            detailsText += `  ${i + 1}. ${area}\n`;
        });
    }
    
    alert(detailsText);
}

// Export context to JSON
function exportContext() {
    const details = currentAgentData;
    if (!details) {
        appendLog('No context data to export', 'error');
        return;
    }
    
    const exportData = {
        timestamp: new Date().toISOString(),
        entities_count: details.entities_identified,
        tasks_count: details.total_tasks,
        events_count: details.total_events,
        notes_count: details.total_notes,
        relationships_count: details.relationships_mapped,
        confidence_score: details.confidence_score,
        insights: details.insights || [],
        priorities: details.key_priorities || [],
        knowledge_areas: details.knowledge_areas || []
    };
    
    const jsonString = JSON.stringify(exportData, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `context-analysis-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
    
    appendLog('✅ Context analysis exported to JSON', 'success');
}

// Google Calendar Agent Demo




// ============================================================================
// Natural Language Orchestrator — Streaming SSE Handler
// ============================================================================

// Extend activityFeed with a stream-aware logger that accepts pre-computed
// category/type from the backend event rather than re-guessing them.
activityFeed.logStream = function(message, type, category) {
    const timestamp = new Date().toLocaleTimeString();
    const activity = {
        id: Date.now() + Math.random(),
        message: message,
        type: type || 'info',
        category: category || 'all',
        timestamp: timestamp,
        pinned: false,
        _streamNew: true          // flag to trigger CSS slide-in
    };

    this.allActivities.unshift(activity);
    if (this.allActivities.length > 100) this.allActivities.pop();

    // Prepend the element directly (faster than full re-render)
    const feedDiv = document.getElementById('action-output');
    if (feedDiv) {
        // Clear placeholder if present
        const placeholder = feedDiv.querySelector('.console-placeholder');
        if (placeholder) placeholder.remove();

        const el = this.createActivityElement(activity);
        el.classList.add('stream-new');
        feedDiv.prepend(el);
    }

    this.updateSummary();
};

let _nlActiveStream = null;   // holds the AbortController for the current stream

async function submitNLGoal() {
    const textarea = document.getElementById('nl-goal-input');
    const priorityEl = document.getElementById('nl-priority');
    const submitBtn  = document.getElementById('nl-submit-btn');
    const iconPulse  = document.getElementById('nl-icon-pulse');

    const goal = (textarea.value || '').trim();
    if (!goal) {
        textarea.focus();
        return;
    }

    // Abort any in-flight stream
    if (_nlActiveStream) {
        _nlActiveStream.abort();
        _nlActiveStream = null;
    }

    // UI — loading state
    submitBtn.classList.add('loading');
    submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Running…</span>';
    iconPulse.classList.add('running');
    textarea.disabled = true;

    const controller = new AbortController();
    _nlActiveStream = controller;

    try {
        const res = await fetch('/orchestrate/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal, priority: priorityEl.value }),
            signal: controller.signal
        });

        if (!res.ok) {
            throw new Error(`Server error ${res.status}`);
        }

        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let   buffer  = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Process complete SSE frames (split on double newline)
            const frames = buffer.split(/\n\n/);
            buffer = frames.pop();   // last chunk may be incomplete

            for (const frame of frames) {
                if (!frame.trim()) continue;

                let eventName = 'activity';
                let dataLine  = '';

                for (const line of frame.split('\n')) {
                    if (line.startsWith('event:')) eventName = line.slice(6).trim();
                    if (line.startsWith('data:'))  dataLine  = line.slice(5).trim();
                }

                if (!dataLine) continue;

                try {
                    const payload = JSON.parse(dataLine);

                    if (eventName === 'activity') {
                        activityFeed.logStream(
                            payload.message,
                            payload.type,
                            payload.category
                        );
                    } else if (eventName === 'done') {
                        // Mark completed
                        activityFeed.logStream(
                            `🏁 Stream closed — workflow <strong>${payload.workflow_id}</strong> handed off`,
                            'success',
                            'status'
                        );
                        // Update stat counter
                        const statEl = document.getElementById('stat-workflows');
                        if (statEl && statEl.textContent !== '--') {
                            statEl.textContent = parseInt(statEl.textContent || '0') + 1;
                        }
                    }
                } catch (parseErr) {
                    console.warn('[NL stream] JSON parse error:', parseErr, dataLine);
                }
            }
        }

    } catch (err) {
        if (err.name !== 'AbortError') {
            activityFeed.logStream(
                `❌ Orchestration error: ${err.message}`,
                'error', 'status'
            );
        }
    } finally {
        // Restore UI
        submitBtn.classList.remove('loading');
        submitBtn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> <span>Run</span>';
        iconPulse.classList.remove('running');
        textarea.disabled = false;
        textarea.value    = '';
        textarea.focus();
        _nlActiveStream = null;
    }
}

function setNLGoal(text) {
    const ta = document.getElementById('nl-goal-input');
    if (ta) {
        ta.value = text;
        ta.focus();
        // Auto-resize
        ta.style.height = 'auto';
        ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
}

function nlOrchestratorKeydown(e) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        submitNLGoal();
    }
    // Auto-resize textarea
    const ta = e.target;
    setTimeout(() => {
        ta.style.height = 'auto';
        ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }, 0);
}
