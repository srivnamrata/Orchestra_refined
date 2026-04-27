import { apiUrl, apiFetch } from './api.js';
import { activityFeed } from './feed.js';
import { renderVibeCheck, renderDebate, renderCriticAnalysis, renderNews, renderResearch, renderGitHub, renderSlack, renderEmail, renderTasks, renderSchedule } from './renderers.js';

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
        github:   { name: 'GITHUB',   endpoint: '/api/github/activity' },
        slack:    { name: 'SLACK',    endpoint: '/api/slack/summary' },
        email:    { name: 'EMAIL',    endpoint: '/api/email/urgent' },
    };
    const cfg = configs[type];
    if (!cfg) return;
    if (cfg.view) window.switchView(cfg.view);
    activityFeed.log(`🏃 Starting ${cfg.name} sequence…`, 'status', 'SYSTEM');
    try {
        const method = ['tasks','schedule'].includes(type) ? 'GET' : 'POST';
        const res = await apiFetch(cfg.endpoint, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: type === 'debate' ? JSON.stringify({
                action: { id: 'ui-demo', name: 'UI Strategy', type: 'workflow', impact: 'medium' },
                executor_agent: 'orchestrator', reasoning: 'Demo run from redesigned UI',
            }) : null,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if      (type === 'news')     renderNews(data.articles || data.data || []);
        else if (type === 'research') renderResearch(data.papers || data.data || []);
        else if (type === 'tasks')    renderTasks(data.tasks || []);
        else if (type === 'schedule') renderSchedule(data.events || []);
        else if (type === 'github')   renderGitHub(data);
        else if (type === 'slack')    renderSlack(data);
        else if (type === 'email')    renderEmail(data);
        else if (type === 'vibe')     renderVibeCheck(data);
        else if (type === 'debate')   renderDebate(data);
        else if (type === 'critic')   renderCriticAnalysis(data);
        else activityFeed.log(data.critique || data.message || 'Operation complete.', 'info', cfg.name);
    } catch (err) {
        activityFeed.log(`⚠️ Sequence failed: ${err.message}`, 'warning', cfg.name);
    }
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
    switchIntel(type, btn);
    runDemo(type);
}

window.runDemo    = runDemo;
window.fetchIntel = fetchIntel;
window.switchIntel = switchIntel;
