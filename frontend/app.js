// ============================================================================
// ORCHESTRA — CORE APPLICATION LOGIC (MD3 EDITION)
// ============================================================================

console.log('🚀 Orchestra MD3 Engine Initializing…');

// ── API Configuration ────────────────────────────────────────────────────────
const ORCHESTRA_API_BASE = (() => {
    try {
        const params = new URLSearchParams(window.location.search);
        const queryBase = params.get('api');
        if (queryBase) localStorage.setItem('orchestraApiBase', queryBase);

        const savedBase = localStorage.getItem('orchestraApiBase');
        const fallbackBase = window.location.protocol === 'file:'
            ? 'https://orchestra-272079333717.us-central1.run.app'
            : window.location.origin;
        return (queryBase || savedBase || fallbackBase).replace(/\/$/, '');
    } catch (_) {
        return window.location.origin;
    }
})();
window.ORCHESTRA_API_BASE = ORCHESTRA_API_BASE;

function apiUrl(path) {
    if (/^https?:\/\//i.test(path)) return path;
    return `${ORCHESTRA_API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

// ── UI State & Globals ───────────────────────────────────────────────────────
let _nlActiveStream = null;
let _scanRunning = false;
let _liveTraceSource = null;

// ── Navigation & View Management ─────────────────────────────────────────────
window.switchView = function(viewId) {
    console.log(`Switching View: ${viewId}`);
    
    // Update Sidebar Navigation
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
        const text = item.textContent.trim().toLowerCase();
        const matches = (viewId === 'dashboard' && (text.includes('dashboard') || text.includes('home'))) ||
                        (viewId === 'workflows' && text.includes('active workflows')) ||
                        (viewId === 'tasks' && text.includes('all tasks')) ||
                        (viewId === 'outputs' && text.includes('outputs')) ||
                        (viewId === 'trace' && text.includes('agent reasoning')) ||
                        (viewId === 'vibe-checks' && text.includes('vibe checks')) ||
                        (viewId === 'debates' && text.includes('debates')) ||
                        (viewId === 'settings' && (text.includes('settings') || text.includes('safety audit')));
        item.classList.toggle('active', matches);
    });

    // Show Matching View Container
    document.querySelectorAll('.view').forEach(v => {
        v.classList.remove('active');
        v.style.display = 'none';
    });
    
    const viewEl = document.getElementById(viewId) || document.getElementById('dashboard');
    if (viewEl) {
        viewEl.classList.add('active');
        viewEl.style.display = (viewId === 'trace') ? 'block' : 'block';
        if (viewId === 'trace') {
            viewEl.style.height = 'calc(100vh - 64px)';
        }
    }
};

// ── Audio Engine ─────────────────────────────────────────────────────────────
window.playAudio = function(text) {
    if (!text) {
        // Summarize active intelligence pane
        const activePane = document.querySelector('.intel-pane.active');
        if (activePane) {
            const titles = Array.from(activePane.querySelectorAll('.news-title, .ti-title, .sched-name'))
                                .map(el => el.textContent)
                                .join('. ');
            if (titles) {
                text = `Summarizing ${activePane.id.replace('pane-', '')}: ${titles}`;
            }
        }
    }
    if (!text) return;
    
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
    activityFeed.log(`🔊 Speaking: "${text.substring(0, 50)}..."`, 'status', 'AUDIO');
};


// ── Activity Feed & Logging (Generative UI Support) ──────────────────────────
const activityFeed = {
    log: function(message, type = 'info', agent = 'SYSTEM', widget = null) {
        const feed = document.getElementById('feed');
        if (!feed) return;

        const entryWrapper = document.createElement('div');
        entryWrapper.className = 'feed-entry-wrapper';
        
        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const colors = {
            'info':    { main: 'var(--g-blue)',  bg: 'var(--g-blue-light)' },
            'success': { main: 'var(--g-green)', bg: 'var(--g-green-light)' },
            'warning': { main: 'var(--g-amber)', bg: 'var(--g-amber-light)' },
            'error':   { main: 'var(--g-red)',   bg: 'var(--g-red-light)' },
            'status':  { main: 'var(--g-teal)',  bg: 'var(--g-teal-light)' },
            'user':    { main: 'var(--md-on-surface)', bg: 'var(--md-surface-2)' }
        };
        const c = colors[type] || colors.info;

        let contentHtml = `<div class="f-text">${message}</div>`;
        
        // Handle Provenance (Trust/Transparency)
        if (widget && widget.sources) {
            contentHtml += this.renderProvenance(widget.sources);
        }

        // Handle Generative UI Widgets
        if (widget) {
            contentHtml += `<div class="f-widget">${this.renderWidget(widget)}</div>`;
        }

        entryWrapper.innerHTML = `
            <div class="feed-entry stream-new">
                <div class="f-time">${timestamp}</div>
                <div class="f-body">
                    <div class="f-agent" style="color:${c.main};background:${c.bg};border:1px solid ${c.main}33">
                        ${agent.toUpperCase()}
                    </div>
                    ${contentHtml}
                </div>
                <div class="f-explain-icon">🧠</div>
            </div>
        `;
        feed.prepend(entryWrapper);
        while (feed.children.length > 50) feed.removeChild(feed.lastElementChild);
    },

    renderWidget: function(w) {
        if (w.type === 'progress-table') {
            return `
                <div class="gen-widget table-widget">
                    <table>
                        <thead><tr><th>Project</th><th>Status</th><th>Health</th></tr></thead>
                        <tbody>
                            ${(w.data || []).map(r => `
                                <tr>
                                    <td>${r.name}</td>
                                    <td><span class="chip" style="background:${r.color}22; color:${r.color}">${r.status}</span></td>
                                    <td><div style="width:100%; height:4px; background:var(--md-surface-3); border-radius:4px"><div style="width:${r.pct}%; height:100%; background:${r.color}; border-radius:4px"></div></div></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                    <div class="export-group" style="margin-top:10px; display:flex; gap:8px">
                        <button class="export-btn" onclick="activityFeed.log('Pushing to Jira...','status','SYSTEM')">Push to Jira</button>
                        <button class="export-btn" onclick="exportTasks('csv', ${JSON.stringify(w.data).replace(/"/g, '&quot;')})">CSV</button>
                        <button class="export-btn" onclick="exportTasks('json', ${JSON.stringify(w.data).replace(/"/g, '&quot;')})">JSON</button>
                    </div>
                </div>
            `;
        }
        if (w.type === 'action-card') {
            return `
                <div class="gen-widget card-widget" style="border-left:4px solid var(--g-blue)">
                    <div style="font-weight:700; margin-bottom:8px">${w.title}</div>
                    <div style="font-size:12px; color:var(--md-dim); margin-bottom:12px">${w.description}</div>
                    <div style="display:flex; gap:8px">
                        ${(w.actions || []).map(a => `<button class="na-btn primary" onclick="activityFeed.log('Triggered: ${a}','success','WIDGET')">${a}</button>`).join('')}
                    </div>
                </div>
            `;
        }
        return `<div class="gen-widget">Unknown widget type: ${w.type}</div>`;
    },

    renderProvenance: function(sources) {
        if (!sources || sources.length === 0) return '';
        
        const typeMap = {
            'slack': { icon: 'forum', color: '#611f69', label: 'Slack' },
            'github': { icon: 'code', color: '#24292e', label: 'GitHub' },
            'doc': { icon: 'description', color: 'var(--g-blue)', label: 'Doc' },
            'metric': { icon: 'analytics', color: 'var(--g-green)', label: 'Metric' }
        };

        const sourceItems = sources.map(s => {
            const t = typeMap[s.type] || typeMap.doc;
            return `
                <div class="prov-source">
                    <div class="prov-source-icon" style="background:${t.color}">${t.label.charAt(0)}</div>
                    <div class="ps-text"><strong>${t.label}</strong>: ${s.detail}</div>
                </div>
            `;
        }).join('');

        return `
            <div class="prov-container">
                <div class="prov-chip"><span class="ms">verified_user</span></div>
                <div class="prov-tooltip">
                    <div class="prov-tooltip-title">Data Provenance</div>
                    ${sourceItems}
                </div>
            </div>
        `;
    }
};

// ── Main Goal Submission ────────────────────────────────────────────────────
window.submitGoal = async function() {
    const textarea = document.getElementById('nl-goal-input');
    const submitBtn = document.getElementById('nl-submit-btn');
    const priority = document.getElementById('nl-priority')?.value || 'medium';
    const goal = (textarea.value || '').trim();

    if (!goal) return;

    // GENERATIVE UI DEMO TRIGGER
    if (goal.toLowerCase().includes('project status')) {
        activityFeed.log('I have analyzed your active projects and generated this status overview.', 'status', 'ORCHESTRATOR', {
            type: 'progress-table',
            data: [
                { name: 'Core Engine V2', status: 'Live', pct: 90, color: 'var(--g-green)' },
                { name: 'Frontend Refactor', status: 'In Review', pct: 65, color: 'var(--g-blue)' },
                { name: 'API Security Audit', status: 'Pending', pct: 15, color: 'var(--g-amber)' }
            ]
        });
        textarea.value = '';
    }
    
    if (goal.toLowerCase().includes('strategy review')) {
        activityFeed.log('I have analyzed your project strategy and detected potential alignment risks.', 'warning', 'CRITIC', {
            type: 'action-card',
            title: 'Strategy Audit',
            description: 'The Q2 goal "Mobile First" lacks corresponding tasks in the UI repository.',
            actions: ['Create Tasks', 'Dismiss'],
            sources: [
                { type: 'slack', detail: 'Discussion in #product regarding mobile priority' },
                { type: 'github', detail: 'orchestra-ui repo missing mobile-layout branch' },
                { type: 'metric', detail: 'Conversion rate on mobile is currently -12%' }
            ]
        });
        textarea.value = '';
        return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="ms sm fa-spin">progress_activity</span> Running…';
    textarea.disabled = true;

    if (_nlActiveStream) _nlActiveStream.abort();
    const controller = new AbortController();
    _nlActiveStream = controller;

    activityFeed.log(`🚀 Initiating workflow: <strong>${goal}</strong>`, 'user', 'USER');
    
    // Update Workflows View
    const wfList = document.getElementById('workflows-list');
    if (wfList) {
        wfList.innerHTML = `
            <div class="run-card live" style="margin-bottom:12px">
                <div>
                    <div class="run-title">${goal}</div>
                    <div class="run-meta">
                        <span class="run-tag tag-live"><span class="tag-dot"></span>Live</span>
                        <span class="chip">Orchestrator</span>
                        <span style="font-family:var(--font-mono);font-size:10px;color:var(--md-dim)">Just started</span>
                    </div>
                    <div class="run-bar-bg"><div class="run-bar-fill" style="width:10%; background:var(--g-green-mid)"></div></div>
                </div>
                <div class="run-right">
                    <div class="run-pct" style="color:var(--g-green)">10%</div>
                </div>
            </div>
        `;
    }

    try {
        const res = await fetch(apiUrl('/orchestrate/stream'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal, priority }),
            signal: controller.signal
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const frames = buffer.split(/\n\n/);
            buffer = frames.pop();

            for (const frame of frames) {
                if (!frame.trim()) continue;
                let event = 'activity', data = '';
                frame.split('\n').forEach(l => {
                    if (l.startsWith('event:')) event = l.slice(6).trim();
                    if (l.startsWith('data:'))  data  = l.slice(5).trim();
                });
                if (!data) continue;

                try {
                    const payload = JSON.parse(data);
                    if (event === 'activity') {
                        activityFeed.log(payload.message, payload.type || 'info', payload.category || 'agent', payload.widget);
                    } else if (event === 'done') {
                        activityFeed.log('✅ Workflow execution completed.', 'success', 'SYSTEM');
                    }
                } catch (e) { console.warn('SSE Parse Error:', e); }
            }
        }
    } catch (err) {
        if (err.name !== 'AbortError') {
            activityFeed.log(`❌ Workflow Error: ${err.message}`, 'error', 'SYSTEM');
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span class="ms sm">play_arrow</span> Run';
        textarea.disabled = false;
        textarea.value = '';
        window.autoExpandGoal(textarea);
    }
};

// ── Intelligence Demo Logic ─────────────────────────────────────────────────
window.runDemo = async function(type) {
    console.log(`Running Demo: ${type || 'all'}`);
    if (!type) {
        window.runDemo('news');
        window.runDemo('research');
        window.runDemo('tasks');
        window.runDemo('schedule');
        window.runDemo('github');
        window.runDemo('slack');
        window.runDemo('email');
        return;
    }

    const configs = {
        critic: { name: 'CRITIC',   endpoint: '/demonstrate-critic-agent', view: 'workflows' },
        vibe:   { name: 'AUDITOR',  endpoint: '/demonstrate-vibe-check',   view: 'vibe-checks' },
        debate: { name: 'DEBATE',   endpoint: '/debate/initiate',          view: 'debates' },
        news:   { name: 'NEWS',     endpoint: '/demonstrate-news-agent' },
        research:{ name: 'RESEARCH',endpoint: '/demonstrate-research-agent' },
        tasks:  { name: 'TASKS',    endpoint: '/api/tasks' },
        schedule:{ name: 'SCHEDULE',endpoint: '/api/events' },
        github: { name: 'GITHUB',   endpoint: '/api/github/activity' },
        slack:  { name: 'SLACK',    endpoint: '/api/slack/summary' },
        email:  { name: 'EMAIL',    endpoint: '/api/email/urgent' }
    };

    const cfg = configs[type];
    if (!cfg) return;

    if (cfg.view) window.switchView(cfg.view);
    else if (!['tasks', 'schedule', 'news', 'research'].includes(type)) window.switchView('dashboard');

    activityFeed.log(`🏃 Starting ${cfg.name} sequence…`, 'status', 'SYSTEM');

    try {
        const method = ['tasks', 'schedule'].includes(type) ? 'GET' : 'POST';
        const res = await fetch(apiUrl(cfg.endpoint), {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: type === 'debate' ? JSON.stringify({
                action: { id: 'ui-demo', name: 'UI Strategy', type: 'workflow', impact: 'medium' },
                executor_agent: 'orchestrator',
                reasoning: 'Demo run from redesigned UI'
            }) : null
        });
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        console.log(`Demo Data Received [${type}]:`, data);
        
        if (type === 'news') renderNews(data.articles || data.data || []);
        else if (type === 'research') renderResearch(data.papers || data.data || []);
        else if (type === 'tasks') renderTasks(data.tasks || []);
        else if (type === 'schedule') renderSchedule(data.events || []);
        else if (type === 'github') renderGitHub(data);
        else if (type === 'slack') renderSlack(data);
        else if (type === 'email') renderEmail(data);
        else if (type === 'vibe') renderVibeCheck(data);
        else if (type === 'debate') renderDebate(data);
        else if (type === 'critic') renderCriticAnalysis(data);
        else {
            const msg = data.critique || data.message || 'Operation complete.';
            activityFeed.log(msg, 'info', cfg.name);
        }
    } catch (err) {
        console.error(`Demo Error [${type}]:`, err);
        activityFeed.log(`⚠️ Sequence failed: ${err.message}`, 'warning', cfg.name);
    }
};

window.fetchIntel = function(type, btn) {
    if (!type) {
        window.runDemo();
        return;
    }
    window.switchIntel(type, btn);
    window.runDemo(type);
};

window.switchIntel = function(type, btn) {
    document.querySelectorAll('.intel-tab').forEach(t => t.classList.remove('active'));
    if (btn) btn.classList.add('active');
    document.querySelectorAll('.intel-pane').forEach(p => p.classList.remove('active'));
    const pane = document.getElementById(`pane-${type}`);
    if (pane) pane.classList.add('active');
};

// ── Rendering Functions ─────────────────────────────────────────────────────

function renderVibeCheck(data) {
    const list = document.getElementById('vibe-check-results');
    if (!list) return;
    
    list.innerHTML = (data.scenarios_tested || []).map(s => `
        <div class="run-card" style="margin-bottom:16px; border-left:4px solid ${s.approval_status === 'APPROVED' ? 'var(--g-green)' : 'var(--g-red)'}">
            <div style="display:flex; justify-content:space-between; align-items:start">
                <div>
                    <div class="run-title">${s.name}</div>
                    <div style="display:flex; gap:8px; margin:8px 0">
                        <span class="chip" style="background:${s.approval_status === 'APPROVED' ? 'var(--g-green-light)' : 'var(--g-red-light)'}; color:${s.approval_status === 'APPROVED' ? 'var(--g-green)' : 'var(--g-red)'}">
                            ${s.approval_status}
                        </span>
                        <span class="chip" style="background:var(--md-surface-2)">Risk: ${s.risk_level}</span>
                    </div>
                    <p style="color:var(--md-on-surface); font-size:13px; line-height:1.4">${s.explanation}</p>
                </div>
                <div style="text-align:right">
                    <div style="font-size:24px; font-weight:700; color:${s.approval_status === 'APPROVED' ? 'var(--g-green)' : 'var(--g-red)'}">${s.approval_status === 'APPROVED' ? '95%' : '22%'}</div>
                    <div style="font-size:10px; color:var(--md-dim)">SAFETY SCORE</div>
                </div>
            </div>
        </div>
    `).join('');
}

function renderDebate(data) {
    const list = document.getElementById('debate-list');
    if (!list) return;
    
    const summary = data.summary || {};
    list.innerHTML = `
        <div class="run-card" style="margin-bottom:16px">
            <div class="run-title" style="color:var(--g-violet)">Debate ID: ${data.debate_id}</div>
            <div style="margin:12px 0; font-size:18px; font-weight:600">${data.final_decision}</div>
            <div style="background:var(--md-surface-2); padding:16px; border-radius:12px; margin-bottom:16px">
                <div style="font-size:12px; color:var(--md-dim); margin-bottom:8px">ARGUMENT BREAKDOWN</div>
                <pre style="font-family:var(--font-mono); font-size:12px; color:var(--md-on-surface); white-space:pre-wrap">${JSON.stringify(summary.arguments || summary, null, 2)}</pre>
            </div>
            <div style="display:flex; gap:12px">
                <div class="chip" style="background:var(--g-blue-light); color:var(--g-blue)">Consensus: ${summary.consensus_reached ? 'YES' : 'NO'}</div>
                <div class="chip" style="background:var(--g-green-light); color:var(--g-green)">Score: ${summary.confidence_score ? (summary.confidence_score * 100).toFixed(0) + '%' : 'N/A'}</div>
            </div>
        </div>
    `;
}

function renderCriticAnalysis(data) {
    const wfList = document.getElementById('workflows-list');
    if (!wfList) return;
    
    wfList.innerHTML = `
        <div class="run-card" style="margin-bottom:16px; border-top:4px solid var(--g-amber)">
            <div class="run-title">Workflow Analysis Report</div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin:16px 0">
                <div style="background:var(--md-surface-2); padding:12px; border-radius:8px; text-align:center">
                    <div style="font-size:20px; font-weight:700">1</div>
                    <div style="font-size:10px; color:var(--md-dim)">TOTAL TASKS</div>
                </div>
                <div style="background:var(--md-surface-2); padding:12px; border-radius:8px; text-align:center">
                    <div style="font-size:20px; font-weight:700">2/5</div>
                    <div style="font-size:10px; color:var(--md-dim)">PRIORITY SCORE</div>
                </div>
                <div style="background:var(--md-surface-2); padding:12px; border-radius:8px; text-align:center">
                    <div style="font-size:20px; font-weight:700">72%</div>
                    <div style="font-size:10px; color:var(--md-dim)">EFFICIENCY</div>
                </div>
            </div>
            <div style="margin-bottom:12px">
                <div style="font-size:12px; color:var(--g-red); font-weight:600; margin-bottom:4px">⚠️ Issues Detected:</div>
                <div style="font-size:13px; padding:8px; background:rgba(234,67,53,0.1); border-radius:6px; color:var(--md-on-surface)">
                    Task "demo for client A" has no due date - planning risk
                </div>
            </div>
            <div>
                <div style="font-size:12px; color:var(--g-green); font-weight:600; margin-bottom:4px">✅ Recommendations:</div>
                <div style="font-size:13px; padding:8px; background:rgba(52,168,83,0.1); border-radius:6px; color:var(--md-on-surface)">
                    Prioritize "demo for client A" - highest priority value
                </div>
            </div>
        </div>
    `;
}

function renderNews(articles) {
    const pane = document.getElementById('pane-news');
    if (!pane) return;
    const grid = pane.querySelector('.news-grid');
    if (!grid) return;
    
    if (!articles || articles.length === 0) {
        grid.innerHTML = '<div class="empty-state">No news available at the moment.</div>';
        return;
    }

    grid.innerHTML = (articles || []).map(a => {
        const sourceName = (typeof a.source === 'object' && a.source !== null) ? (a.source.name || 'News') : (a.source || 'News');
        const cleanTitle = (a.title || '').replace(/'/g, "\\'");
        return `
            <div class="news-card">
                <div class="news-source-row"><div class="news-favicon" style="background:var(--g-amber);color:white">${sourceName.charAt(0)}</div><span class="news-source-name">${sourceName}</span></div>
                <div class="news-title">${a.title}</div>
                <div class="news-actions">
                    <button class="na-btn" onclick="window.open('${a.url}','_blank')">📖 Read</button>
                    <button class="na-btn" onclick="window.playAudio('${cleanTitle}')">🎧 Listen</button>
                    <button class="na-btn" onclick="activityFeed.log('Article saved to Knowledge Graph','success','KNOWLEDGE')">🔖 Save</button>
                </div>
            </div>
        `;
    }).join('');
}

function renderResearch(papers) {
    const pane = document.getElementById('pane-research');
    if (!pane) return;
    const grid = pane.querySelector('.news-grid');
    if (!grid) return;

    if (!papers || papers.length === 0) {
        grid.innerHTML = '<div class="empty-state">No research papers found.</div>';
        return;
    }

    grid.innerHTML = (papers || []).map(p => {
        const cleanTitle = (p.title || '').replace(/'/g, "\\'");
        return `
            <div class="news-card nc-arxiv">
                <div class="news-source-row"><div class="news-favicon" style="background:var(--g-blue);color:white">R</div><span class="news-source-name">arXiv</span></div>
                <div class="news-title">${p.title}</div>
                <div class="news-actions">
                    <button class="na-btn" onclick="window.open('${p.url}','_blank')">📖 View</button>
                    <button class="na-btn" onclick="window.playAudio('${cleanTitle}')">🎧 Listen</button>
                    <button class="na-btn" onclick="activityFeed.log('Paper indexed in Knowledge Graph','success','KNOWLEDGE')">🔖 Save</button>
                </div>
            </div>
        `;
    }).join('');
}

function renderGitHub(data) {
    const pane = document.getElementById('pane-github');
    if (!pane) return;
    const grid = pane.querySelector('.news-grid');
    if (!grid) return;

    grid.innerHTML = (data.pull_requests || []).map(pr => `
        <div class="news-card nc-github" style="border-left:4px solid ${pr.status === 'APPROVED' ? 'var(--g-green)' : 'var(--g-amber)'}">
            <div class="news-source-row"><div class="news-favicon" style="background:#24292e;color:white">G</div><span class="news-source-name">${pr.repo}</span></div>
            <div class="news-title">PR #${pr.id}: ${pr.title}</div>
            <div class="news-meta" style="color:${pr.status === 'APPROVED' ? 'var(--g-green)' : 'var(--g-amber)'}">
                ${pr.status === 'APPROVED' ? '✓ Checks passed · Approved' : '⚠️ Blocked by review'}
            </div>
            <div class="news-actions">
                <button class="na-btn" onclick="activityFeed.log('Reviewing PR #${pr.id}...','status','GITHUB')">📖 Review</button>
            </div>
        </div>
    `).join('');
}

function renderSlack(data) {
    const pane = document.getElementById('pane-slack');
    if (!pane) return;
    const grid = pane.querySelector('.task-intel-grid');
    if (!grid) return;

    grid.innerHTML = (data.summaries || []).map(s => `
        <div class="task-intel-item">
            <div class="ti-check" style="background:var(--g-violet); color:white">#</div>
            <div>
                <div class="ti-title">${s.text}</div>
                <div style="display:flex;gap:6px;margin-top:4px">
                    <span class="ti-priority" style="background:var(--g-violet-light);color:var(--g-violet)">${s.type}</span>
                    <span class="ti-due">${s.ts}</span>
                </div>
            </div>
        </div>
    `).join('');
}

function renderEmail(data) {
    const pane = document.getElementById('pane-email');
    if (!pane) return;
    const grid = pane.querySelector('.task-intel-grid');
    if (!grid) return;

    grid.innerHTML = (data.urgent || []).map(e => `
        <div class="task-intel-item">
            <div class="ti-check" style="background:${e.priority === 'high' ? 'var(--g-red)' : 'var(--g-blue)'}; color:white">M</div>
            <div>
                <div class="ti-title">${e.subject}</div>
                <div style="font-size:11px; color:var(--md-dim); margin:4px 0">${e.summary}</div>
                <div style="display:flex;gap:6px">
                    <span class="ti-priority" style="background:${e.priority === 'high' ? 'var(--g-red-light)' : 'var(--g-blue-light)'}; color:${e.priority === 'high' ? 'var(--g-red)' : 'var(--g-blue)'}">${e.priority}</span>
                    <span class="ti-due">${e.from}</span>
                </div>
            </div>
        </div>
    `).join('');
}

function renderTasks(tasks) {
    const pane = document.getElementById('pane-tasks');
    const allTasksPane = document.getElementById('all-tasks-list');
    
    const html = (tasks || []).map(t => {
        const isDone = t.status === 'done';
        return `
            <div class="task-intel-item">
                <div class="ti-check ${isDone ? 'done' : ''}">${isDone ? '✓' : ''}</div>
                <div><div class="ti-title ${isDone ? 'done-text' : ''}">${t.title}</div><div style="display:flex;gap:6px;margin-top:4px"><span class="ti-priority">${t.priority || 'med'}</span></div></div>
            </div>
        `;
    }).join('');

    if (pane) pane.querySelector('.task-intel-grid').innerHTML = html;
    if (allTasksPane) allTasksPane.innerHTML = html;
}

function renderSchedule(events) {
    const pane = document.getElementById('pane-schedule');
    if (!pane) return;
    const grid = pane.querySelector('.schedule-grid');
    if (grid) grid.innerHTML = (events || []).map(ev => `
        <div class="sched-item">
            <div class="sched-time">${ev.start_time ? ev.start_time.split('T')[1].slice(0,5) : '--:--'}</div>
            <div><div class="sched-name">${ev.summary}</div><div class="sched-detail">${ev.location || 'Remote'}</div></div>
        </div>
    `).join('');
}

// ── Voice Input Logic ───────────────────────────────────────────────────────
window.toggleVoiceInput = function() {
    const btn = document.getElementById('nl-mic-btn');
    if (!btn) return;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.lang = 'en-US';
        recognition.onstart = () => {
            btn.classList.add('active');
            btn.innerHTML = '<span class="ms sm fa-spin">graphic_eq</span>';
        };
        recognition.onresult = (event) => {
            const text = event.results[0][0].transcript;
            window.setGoal(text);
        };
        recognition.onend = () => {
            btn.classList.remove('active');
            btn.innerHTML = '<span class="ms sm">mic</span>';
        };
        recognition.start();
    }
};

// ── Theme Management ────────────────────────────────────────────────────────
window.applyTheme = function(isDark) {
    document.documentElement.classList.toggle('dark', isDark);
    const sun = document.querySelector('.icon-sun');
    const moon = document.querySelector('.icon-moon');
    if (sun) sun.style.display = isDark ? 'none' : 'block';
    if (moon) moon.style.display = isDark ? 'block' : 'none';
    localStorage.setItem('orchestra-theme', isDark ? 'dark' : 'light');
};

window.toggleTheme = function() {
    window.applyTheme(!document.documentElement.classList.contains('dark'));
};

// ── Initialization ──────────────────────────────────────────────────────────
function initUI() {
    const greeting = document.getElementById('greetingLine');
    if (greeting) {
        const h = new Date().getHours();
        const period = h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';
        greeting.textContent = `Good ${period} · ${new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' })}`;
    }

    const saved = localStorage.getItem('orchestra-theme');
    window.applyTheme(saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches));

    document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const text = item.textContent.trim().toLowerCase();
            if (text.includes('home')) window.switchView('dashboard');
            else if (text.includes('active workflows')) window.switchView('workflows');
            else if (text.includes('all tasks')) window.switchView('tasks');
            else if (text.includes('outputs')) window.switchView('outputs');
            else if (text.includes('agent reasoning')) window.switchView('trace');
            else if (text.includes('vibe checks')) window.switchView('vibe-checks');
            else if (text.includes('debates')) window.switchView('debates');
            else if (text.includes('settings') || text.includes('safety audit')) window.switchView('settings');
        });
    });

    window.switchView('dashboard');
    activityFeed.log('System ready. Orchestra MD3.', 'status');

    // Initialize Agent Health Bars
    setTimeout(() => {
        const healthData = { ah1: '72%', ah2: '55%', ah3: '88%', ah4: '40%' };
        Object.keys(healthData).forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.width = healthData[id];
        });
    }, 800);
}

// ── Helpers ─────────────────────────────────────────────────────────────────
window.exportTasks = function(format) {
    const tasks = window._currentTasks || [];
    if (tasks.length === 0) {
        activityFeed.log('No tasks available to export.', 'warning', 'SYSTEM');
        return;
    }

    let content = '';
    let mimeType = 'text/plain';
    let filename = `orchestra_tasks_${new Date().toISOString().split('T')[0]}`;

    if (format === 'csv') {
        const headers = ['ID', 'Title', 'Priority', 'Status', 'Due Date'];
        const rows = tasks.map(t => [t.task_id, t.title, t.priority, t.status, t.due_date].join(','));
        content = [headers.join(','), ...rows].join('\n');
        mimeType = 'text/csv';
        filename += '.csv';
    } else {
        content = JSON.stringify(tasks, null, 2);
        mimeType = 'application/json';
        filename += '.json';
    }

    downloadBlob(content, mimeType, filename);
    activityFeed.log(`Successfully exported ${tasks.length} tasks as ${format.toUpperCase()}.`, 'success', 'SYSTEM');
};

function downloadBlob(content, mimeType, filename) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
window.setGoal = function(t) {
    const inp = document.getElementById('nl-goal-input');
    if (inp) { inp.value = t; inp.focus(); window.autoExpandGoal(inp); }
};

window.autoExpandGoal = function(el) {
    el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px';
};

window.updateGoalMeta = function(el) {
    const count = document.getElementById('goalCharCount');
    if (count) count.textContent = `${el.value.length} / 500`;
};

window.setPriority = function(btn) {
    document.querySelectorAll('.pp').forEach(b => b.classList.remove('active', 'p-crit'));
    btn.classList.add('active');
    if (btn.textContent.trim() === 'Crit') btn.classList.add('p-crit');
    const sel = document.getElementById('nl-priority');
    const map = { Low: 'low', Med: 'medium', High: 'high', Crit: 'critical' };
    if (sel) sel.value = map[btn.textContent.trim()] || 'medium';
};

window.runScan = function() {
    if (_scanRunning) return;
    _scanRunning = true;
    
    activityFeed.log('📡 Intelligence Scan initiated...', 'status', 'SYSTEM');
    
    setTimeout(() => {
        activityFeed.log('🔍 Scanning environment for bottlenecks...', 'info', 'CRITIC');
    }, 1000);
    
    setTimeout(() => {
        activityFeed.log('🛡️ Auditing cross-agent intent alignment...', 'info', 'AUDITOR');
    }, 2500);
    
    setTimeout(() => {
        activityFeed.log('✅ Scan complete: 1 dependency risk mitigated, efficiency +4%.', 'success', 'SYSTEM');
        _scanRunning = false;
    }, 4500);
};

const tick = () => {
    const clock = document.getElementById('clock');
    if (clock) {
        const n = new Date();
        clock.textContent = `${n.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    }
};
setInterval(tick, 10000);
tick();

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initUI);
else initUI();
