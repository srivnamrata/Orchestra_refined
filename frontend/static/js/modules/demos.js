import { apiUrl, apiFetch } from './api.js';
import { activityFeed } from './feed.js';
import { renderVibeCheck, renderDebate, renderCriticAnalysis, renderNews, renderResearch, renderTasks, renderSchedule } from './renderers.js';

export function switchIntel(type, btn) {
    document.querySelectorAll('.intel-tab').forEach(t => t.classList.remove('active'));
    if (btn) btn.classList.add('active');
    else document.querySelectorAll('.intel-tab').forEach(t => { if (t.textContent.toLowerCase().includes(type)) t.classList.add('active'); });
    document.querySelectorAll('.intel-pane').forEach(p => p.classList.remove('active'));
    const pane = document.getElementById(`pane-${type}`);
    if (pane) pane.classList.add('active');
}

export async function runDemo(type) {
    if (!type) {
        ['news','research','tasks','schedule','github','slack','email'].forEach(t => runDemo(t));
        return;
    }
    const configs = {
        critic:   { name: 'CRITIC',   endpoint: '/demonstrate-critic-agent',    view: 'workflows' },
        vibe:     { name: 'AUDITOR',  endpoint: '/demonstrate-vibe-check',      view: 'vibe-checks' },
        debate:   { name: 'DEBATE',   endpoint: '/debate/initiate',             view: 'debates' },
        news:     { name: 'NEWS',     endpoint: '/demonstrate-news-agent' },
        research: { name: 'RESEARCH', endpoint: '/demonstrate-research-agent' },
        tasks:    { name: 'TASKS',    endpoint: '/api/tasks' },
        schedule: { name: 'SCHEDULE', endpoint: '/api/events' },
    };
    const cfg = configs[type];
    if (!cfg) return;
    if (cfg.view) window.switchView(cfg.view);
    activityFeed.log(`🏃 Starting ${cfg.name} sequence…`, 'status', 'SYSTEM');
    try {
        const method  = ['tasks','schedule'].includes(type) ? 'GET' : 'POST';
        const hasBody = type === 'debate';
        const res = await apiFetch(cfg.endpoint, {
            method,
            ...(hasBody ? {
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: { id: 'ui-demo', name: 'UI Strategy', type: 'workflow', impact: 'medium' },
                    executor_agent: 'orchestrator', reasoning: 'Demo run from redesigned UI',
                }),
            } : {}),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if      (type === 'news')     renderNews(data.articles || data.data || []);
        else if (type === 'research') renderResearch(data.papers || data.data || []);
        else if (type === 'tasks')    renderTasks(data.tasks || []);
        else if (type === 'schedule') renderSchedule(data.events || []);
        else if (type === 'vibe')     renderVibeCheck(data);
        else if (type === 'debate')   renderDebate(data);
        else if (type === 'critic')   renderCriticAnalysis(data);
        else activityFeed.log(data.critique || data.message || 'Operation complete.', 'info', cfg.name);
    } catch (err) {
        activityFeed.log(`⚠️ Sequence failed: ${err.message}`, 'warning', cfg.name);
    }
}

export async function fetchTasks() {
    const res = await apiFetch('/api/tasks', { method: 'GET' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.tasks || [];
}

export function fetchIntel(type, btn) {
    if (!type) {
        const newsTab = document.querySelector('.intel-tab');
        switchIntel('news', newsTab);
        const grid = document.getElementById('hn-news-grid');
        if (grid) grid.innerHTML = `<div style="grid-column:1/-1;padding:16px;text-align:center;color:var(--md-dim);font-size:12px"><span class="ms" style="font-size:20px;display:block;margin-bottom:6px">refresh</span>Refreshing…</div>`;
        const label = document.getElementById('news-source-label');
        if (label) label.textContent = 'Fetching latest AI & ML news…';
        runDemo('news'); runDemo('research'); runDemo('tasks'); runDemo('schedule');
        return;
    }
    // Integration panes fetch from real APIs
    if (['github','slack','gmail','email'].includes(type)) {
        const paneId = type === 'email' ? 'gmail' : type;
        switchIntel(paneId, btn);
        if (window.fetchIntegrationPane) window.fetchIntegrationPane(type === 'email' ? 'gmail' : type);
        return;
    }
    switchIntel(type, btn);
    if (type === 'tasks') {
        activityFeed.log('🏃 Starting TASKS sequence…', 'status', 'SYSTEM');
        const pane = document.getElementById('pane-tasks');
        const paneGrid = pane ? pane.querySelector('.task-intel-grid') : null;
        if (paneGrid) {
            paneGrid.innerHTML = `<div style="grid-column:1/-1;padding:24px;text-align:center;color:var(--md-dim);font-size:13px">
                <span class="ms" style="font-size:24px;display:block;margin-bottom:8px">hourglass_top</span>
                Fetching your live tasks…
            </div>`;
        }
        fetchTasks().then(tasks => {
            renderTasks(tasks);
            const label = document.getElementById('tasks-source-label');
            const tabCount = document.getElementById('tasks-tab-count');
            if (label) label.textContent = `Your Tasks · ${tasks.length} item${tasks.length === 1 ? '' : 's'}`;
            const dashboardLabel = document.getElementById('dashboard-tasks-label');
            if (dashboardLabel) dashboardLabel.textContent = `Your Tasks · ${tasks.length} item${tasks.length === 1 ? '' : 's'}`;
            if (tabCount) tabCount.textContent = String(tasks.length);
            const dashboardGrid = document.getElementById('dashboard-tasks-grid');
            if (dashboardGrid && window.renderTaskGrid) {
                window.renderTaskGrid(dashboardGrid, tasks, { emptyMessage: 'No tasks found. Create a goal to generate active work.' });
            }
            window._currentTasks = tasks;
        }).catch(err => {
            activityFeed.log(`⚠️ Sequence failed: ${err.message}`, 'warning', 'TASKS');
        });
        return;
    }
    runDemo(type);
}

window.runDemo    = runDemo;
window.fetchIntel = fetchIntel;
window.switchIntel = switchIntel;
window.fetchTasks  = fetchTasks;
