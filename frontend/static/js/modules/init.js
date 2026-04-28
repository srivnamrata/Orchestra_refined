import { activityFeed } from './feed.js';
import { switchView } from './navigation.js';
import { applyTheme } from './theme.js';
import { fetchTasks, runDemo } from './demos.js';
import { renderTaskGrid } from './renderers.js';

async function loadDashboardTasks() {
    const dashboardLabel = document.getElementById('dashboard-tasks-label');
    const dashboardGrid  = document.getElementById('dashboard-tasks-grid');
    const tasksLabel     = document.getElementById('tasks-source-label');
    const tasksTabCount   = document.getElementById('tasks-tab-count');
    if (dashboardLabel) dashboardLabel.textContent = 'Your Tasks · Loading…';
    if (tasksLabel) tasksLabel.textContent = 'Your Tasks · Loading…';
    if (tasksTabCount) tasksTabCount.textContent = '…';
    if (dashboardGrid) {
        renderTaskGrid(dashboardGrid, [], { emptyMessage: 'Loading your live tasks…' });
    }
    try {
        const tasks = await fetchTasks();
        const count  = tasks.length;
        const label  = `Your Tasks · ${count} item${count === 1 ? '' : 's'}`;
        if (dashboardLabel) dashboardLabel.textContent = label;
        if (tasksLabel) tasksLabel.textContent = label;
        if (tasksTabCount) tasksTabCount.textContent = String(count);
        if (dashboardGrid) {
            renderTaskGrid(dashboardGrid, tasks, { emptyMessage: 'No tasks found. Create a goal to generate active work.' });
        }
        if (typeof window.renderTasks === 'function') window.renderTasks(tasks);
        window._currentTasks = tasks;
    } catch (err) {
        const message = 'Unable to load tasks right now.';
        if (dashboardLabel) dashboardLabel.textContent = 'Your Tasks · Unavailable';
        if (tasksLabel) tasksLabel.textContent = 'Your Tasks · Unavailable';
        if (tasksTabCount) tasksTabCount.textContent = '!';
        if (dashboardGrid) {
            renderTaskGrid(dashboardGrid, [], { emptyMessage: `${message} Sign in again or refresh to retry.` });
        }
    }
}

export function initUI() {
    const greeting = document.getElementById('greetingLine');
    if (greeting) {
        const h = new Date().getHours();
        const period = h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';
        greeting.textContent = `Good ${period} · ${new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' })}`;
    }

    const saved = localStorage.getItem('orchestra-theme');
    applyTheme(saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches));


    const content = document.querySelector('.content');
    if (content && !document.getElementById('back-dash-bar')) {
        const bar = document.createElement('div');
        bar.id = 'back-dash-bar';
        bar.style.cssText = 'display:none;align-items:center;gap:8px;padding:8px 0 2px;flex-shrink:0';
        bar.innerHTML = `<button onclick="window.switchView('dashboard')" style="display:flex;align-items:center;gap:6px;background:none;border:1px solid var(--md-surface-2);border-radius:var(--radius-full);padding:5px 14px;font-size:12px;font-weight:600;color:var(--md-muted);cursor:pointer;transition:all 0.15s" onmouseover="this.style.color='var(--md-on-surface)'" onmouseout="this.style.color='var(--md-muted)'"><span class="ms" style="font-size:14px">arrow_back</span> Dashboard</button>`;
        content.insertBefore(bar, content.firstChild);
    }

    switchView('dashboard');
    activityFeed.log('System ready. Orchestra MD3.', 'status');
    window.setTimeout(() => { loadDashboardTasks(); }, 150);

    setTimeout(() => { runDemo('news'); runDemo('research'); }, 500);

    const healthData = { ah1: '72%', ah2: '55%', ah3: '88%', ah4: '40%' };
    Object.keys(healthData).forEach(id => { const el = document.getElementById(id); if (el) el.style.width = '0%'; });
    setTimeout(() => Object.keys(healthData).forEach(id => { const el = document.getElementById(id); if (el) el.style.width = healthData[id]; }), 300);
}

// ── Clock ────────────────────────────────────────────────────────────────────
const tick = () => {
    const clock = document.getElementById('clock');
    if (clock) clock.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};
setInterval(tick, 10000);
tick();

// ── Onboarding restart ───────────────────────────────────────────────────────
export function restartTour() {
    try { localStorage.removeItem('orch-onboarded'); } catch (e) { }
    if (window.orchOnboard) window.orchOnboard.open();
}

window.restartTour = restartTour;
window.fetchDashboardTasks = loadDashboardTasks;

// ── Bootstrap ────────────────────────────────────────────────────────────────
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initUI);
else initUI();
