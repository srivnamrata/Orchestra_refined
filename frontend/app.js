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
                        (viewId === 'trace' && text.includes('agent reasoning')) ||
                        (viewId === 'settings' && text.includes('settings'));
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
        viewEl.style.display = 'block';
    }
};

// ── Activity Feed & Logging ──────────────────────────────────────────────────
const activityFeed = {
    log: function(message, type = 'info', agent = 'SYSTEM') {
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

        entryWrapper.innerHTML = `
            <div class="feed-entry stream-new">
                <div class="f-time">${timestamp}</div>
                <div class="f-body">
                    <div class="f-agent" style="color:${c.main};background:${c.bg};border:1px solid ${c.main}33">
                        ${agent.toUpperCase()}
                    </div>
                    <div class="f-text">${message}</div>
                </div>
                <div class="f-explain-icon">🧠</div>
            </div>
        `;
        feed.prepend(entryWrapper);
        while (feed.children.length > 50) feed.removeChild(feed.lastElementChild);
    }
};

// ── Main Goal Submission ────────────────────────────────────────────────────
window.submitGoal = async function() {
    const textarea = document.getElementById('nl-goal-input');
    const submitBtn = document.getElementById('nl-submit-btn');
    const priority = document.getElementById('nl-priority')?.value || 'medium';
    const goal = (textarea.value || '').trim();

    if (!goal) return;

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
                        activityFeed.log(payload.message, payload.type || 'info', payload.category || 'agent');
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
    const configs = {
        critic: { name: 'CRITIC', endpoint: '/demonstrate-critic-agent' },
        vibe:   { name: 'AUDITOR', endpoint: '/demonstrate-vibe-check' },
        debate: { name: 'DEBATE',  endpoint: '/debate/initiate' },
        news:   { name: 'NEWS',    endpoint: '/demonstrate-news-agent' },
        research:{ name: 'RESEARCH',endpoint: '/demonstrate-research-agent' },
        tasks:  { name: 'TASKS',   endpoint: '/api/tasks' },
        schedule:{ name: 'SCHEDULE',endpoint: '/api/events' }
    };

    const cfg = configs[type];
    if (!cfg) return;

    if (!['tasks', 'schedule', 'news', 'research'].includes(type)) {
        window.switchView('dashboard');
    }

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
        const data = await res.json();
        
        if (type === 'news') renderNews(data.articles);
        else if (type === 'research') renderResearch(data.papers);
        else if (type === 'tasks') renderTasks(data.tasks);
        else if (type === 'schedule') renderSchedule(data.events);
        else {
            const msg = data.critique || data.message || (data.scenarios_tested ? `Validated ${data.scenarios_tested.length} scenarios` : 'Operation complete.');
            activityFeed.log(msg, 'info', cfg.name);
        }
    } catch (err) {
        activityFeed.log(`⚠️ Sequence failed: ${err.message}`, 'warning', cfg.name);
    }
};

window.fetchIntel = function(type, btn) {
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

// ── Rendering ───────────────────────────────────────────────────────────────
function renderNews(articles) {
    const pane = document.getElementById('pane-news');
    if (!pane) return;
    const grid = pane.querySelector('.news-grid');
    if (grid) grid.innerHTML = (articles || []).map(a => `
        <div class="news-card">
            <div class="news-source-row"><div class="news-favicon" style="background:var(--g-amber);color:white">N</div><span class="news-source-name">${a.source || 'News'}</span></div>
            <div class="news-title">${a.title}</div>
            <div class="news-actions"><button class="na-btn" onclick="window.open('${a.url}','_blank')">📖 Read</button></div>
        </div>
    `).join('');
}

function renderResearch(papers) {
    const pane = document.getElementById('pane-research');
    if (!pane) return;
    const grid = pane.querySelector('.news-grid');
    if (grid) grid.innerHTML = (papers || []).map(p => `
        <div class="news-card nc-arxiv">
            <div class="news-source-row"><div class="news-favicon" style="background:var(--g-blue);color:white">R</div><span class="news-source-name">arXiv</span></div>
            <div class="news-title">${p.title}</div>
            <div class="news-actions"><button class="na-btn" onclick="window.open('${p.url}','_blank')">📖 View</button></div>
        </div>
    `).join('');
}

function renderTasks(tasks) {
    const pane = document.getElementById('pane-tasks');
    if (!pane) return;
    const grid = pane.querySelector('.task-intel-grid');
    if (grid) grid.innerHTML = (tasks || []).map(t => {
        const isDone = t.status === 'done';
        return `
            <div class="task-intel-item">
                <div class="ti-check ${isDone ? 'done' : ''}">${isDone ? '✓' : ''}</div>
                <div><div class="ti-title ${isDone ? 'done-text' : ''}">${t.title}</div><div style="display:flex;gap:6px;margin-top:4px"><span class="ti-priority">${t.priority || 'med'}</span></div></div>
            </div>
        `;
    }).join('');
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
            else if (text.includes('agent reasoning')) window.switchView('trace');
            else if (text.includes('settings')) window.switchView('settings');
        });
    });

    window.switchView('dashboard');
    activityFeed.log('System ready. Orchestra MD3.', 'status');
}

// ── Helpers ─────────────────────────────────────────────────────────────────
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
    activityFeed.log('📡 Scan initiated...', 'status');
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
