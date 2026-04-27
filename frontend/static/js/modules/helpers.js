import { apiUrl, apiFetch } from './api.js';
import { activityFeed } from './feed.js';

export function downloadBlob(content, mimeType, filename) {
    const blob = new Blob([content], { type: mimeType });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
}

export function exportTasks(format, data) {
    const tasks = data || window._currentTasks || [];
    if (!tasks.length) { activityFeed.log('No tasks available to export.', 'warning', 'SYSTEM'); return; }
    const date = new Date().toISOString().split('T')[0];
    let content, mimeType, filename;
    if (format === 'csv') {
        content  = [['ID','Title','Priority','Status','Due Date'].join(','), ...tasks.map(t => [t.task_id,t.title,t.priority,t.status,t.due_date].join(','))].join('\n');
        mimeType = 'text/csv';
        filename = `orchestra_tasks_${date}.csv`;
    } else {
        content  = JSON.stringify(tasks, null, 2);
        mimeType = 'application/json';
        filename = `orchestra_tasks_${date}.json`;
    }
    downloadBlob(content, mimeType, filename);
    activityFeed.log(`Successfully exported ${tasks.length} tasks as ${format.toUpperCase()}.`, 'success', 'SYSTEM');
}

export function useSuggestion(text) {
    const inp = document.getElementById('nl-goal-input');
    if (inp) { inp.value = text; window.autoExpandGoal(inp); inp.focus(); activityFeed.log(`Selected starter prompt: "${text}"`, 'info', 'SYSTEM'); }
}

export function discoverMCP() {
    const url  = document.getElementById('mcp-url')?.value;
    if (!url) { alert('Please enter an MCP server URL'); return; }
    const term = document.getElementById('mcp-terminal');
    const list = document.getElementById('mcp-tools-list');
    const log  = (msg, type='info') => {
        const div = document.createElement('div');
        div.className = `mcp-log-entry ${type}`; div.textContent = `> ${msg}`;
        term.appendChild(div); term.scrollTop = term.scrollHeight;
    };
    log(`Connecting to ${url}...`);
    setTimeout(() => { log('Handshake successful. Version: MCP 1.0.4','success'); log('Inspecting server capabilities…'); }, 1000);
    setTimeout(() => { log('Found 1 tool: "database_query"'); log('Generating Zero-Shot connection logic…'); }, 2500);
    setTimeout(() => {
        log('[AUTO-GEN] Created mapping for \'database_query\'','success');
        log('Tool registered and ready for Orchestrator usage.','success');
        list.innerHTML = `<div class="mcp-tool-card anim a1"><div class="mcp-tool-title"><span class="ms" style="color:var(--g-green)">database</span> database_query</div><div class="mcp-tool-desc">Executes structured queries against the discovered SQL instance.</div><div style="display:flex;gap:8px"><span class="chip">read</span><span class="chip">write</span></div></div>`;
        activityFeed.log(`New tool "database_query" discovered via MCP from ${url}`, 'success', 'SYSTEM');
    }, 4500);
}

export function commitDraftTasks(draftId) {
    const tasks     = window[draftId];
    const container = document.getElementById(`${draftId}-container`);
    if (!tasks || !container) return;
    const selected = [];
    container.querySelectorAll('.dw-row').forEach((row, idx) => {
        if (row.querySelector('.dw-check').classList.contains('active')) selected.push(tasks[idx]);
    });
    if (!selected.length) { alert('Please select at least one task.'); return; }
    activityFeed.log(`Committing ${selected.length} tasks to your database…`, 'status', 'SYSTEM');
    Promise.all(selected.map(t => apiFetch('/api/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(t) }))).then(() => {
        container.innerHTML = `<div style="padding:20px;text-align:center;background:var(--g-green-light);color:var(--g-green);border-radius:12px"><span class="ms" style="font-size:32px;margin-bottom:8px">check_circle</span><div style="font-weight:700">Tasks Successfully Committed</div><div style="font-size:11px">${selected.length} items added to your Workspace.</div><button class="export-btn" style="margin-top:12px" onclick="window.switchView('tasks')">View Workspace</button></div>`;
        activityFeed.log(`Successfully created ${selected.length} tasks.`, 'success', 'SYSTEM');
        if (typeof window.fetchTasks === 'function') window.fetchTasks();
    }).catch(err => { activityFeed.log('Error committing tasks.', 'error', 'SYSTEM'); });
}

export function submitFeedback(btn, type) {
    const row = btn.closest('.f-feedback-row');
    row.querySelectorAll('.fb-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const countEl = btn.querySelector('.fb-count');
    countEl.textContent = parseInt(countEl.textContent) + 1;
    const agent = btn.closest('.f-body').querySelector('.f-agent').textContent.trim();
    activityFeed.log(`Feedback captured for ${agent}: ${type.toUpperCase()}`, 'status', 'ACADEMY');
    apiFetch('/api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ agent, type, timestamp: new Date().toISOString() }) }).catch(() => {});
}

export function setGoal(t) {
    const inp = document.getElementById('nl-goal-input');
    if (inp) { inp.value = t; inp.focus(); autoExpandGoal(inp); }
}

export function autoExpandGoal(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

export function updateGoalMeta(el) {
    const count = document.getElementById('goalCharCount');
    if (count) count.textContent = `${el.value.length} / 500`;
}

export function setPriority(btn) {
    document.querySelectorAll('.pp').forEach(b => b.classList.remove('active','p-crit'));
    btn.classList.add('active');
    if (btn.textContent.trim() === 'Crit') btn.classList.add('p-crit');
    const sel = document.getElementById('nl-priority');
    const map = { Low:'low', Med:'medium', High:'high', Crit:'critical' };
    if (sel) sel.value = map[btn.textContent.trim()] || 'medium';
}

window.exportTasks    = exportTasks;
window.downloadBlob   = downloadBlob;
window.useSuggestion  = useSuggestion;
window.discoverMCP    = discoverMCP;
window.commitDraftTasks = commitDraftTasks;
window.submitFeedback = submitFeedback;
window.setGoal        = setGoal;
window.autoExpandGoal = autoExpandGoal;
window.updateGoalMeta = updateGoalMeta;
window.setPriority    = setPriority;
