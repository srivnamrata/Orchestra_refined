export function showCompletionToast(taskTitle) {
    const toast = document.getElementById('completionToast');
    const el    = document.getElementById('ct-goal-text');
    if (el)    el.textContent = taskTitle;
    if (!toast) return;
    toast.classList.add('show');
    clearTimeout(toast._hideTimer);
    toast._hideTimer = setTimeout(() => toast.classList.remove('show'), 3000);
}

export function switchView(viewId) {
    // Update nav item active state — prefer data-view match, fall back to text
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    let navItem = document.querySelector(`.nav-item[data-view="${viewId}"]`);
    if (!navItem) {
        const label = viewId.replace(/-/g, ' ').toLowerCase();
        navItem = Array.from(document.querySelectorAll('.nav-item'))
            .find(i => i.textContent.trim().toLowerCase().includes(label));
    }
    if (navItem) navItem.classList.add('active');

    // Show target view (CSS: .view { display:none } .view.active { display:block })
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const target = document.getElementById(viewId);
    if (target) target.classList.add('active');

    // Update page title
    const titleEl = document.querySelector('.page-title');
    if (titleEl) {
        const label = viewId.replace(/-/g, ' ');
        titleEl.textContent = label.charAt(0).toUpperCase() + label.slice(1);
    }

    const bar = document.getElementById('back-dash-bar');
    if (bar) bar.style.display = viewId === 'dashboard' ? 'none' : 'flex';

    if (viewId === 'integrations-settings' && window.loadIntegrationStatuses) {
        window.loadIntegrationStatuses();
    }

    if (target && typeof target.scrollIntoView === 'function') {
        target.scrollIntoView({ block: 'start', behavior: 'auto' });
    }
}

export function openWorkflowsPage() {
    switchView('workflows');
    const panel = document.getElementById('workflows');
    if (panel && typeof panel.scrollIntoView === 'function') {
        panel.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }
}

export function closeActiveWorkflows() {
    const panel = document.getElementById('workflowsPanel');
    const backdrop = document.getElementById('workflowsBackdrop');
    if (panel && backdrop) {
        panel.classList.remove('open');
        backdrop.classList.remove('open');
    }
}

export async function toggleActiveWorkflows() {
    const panel = document.getElementById('workflowsPanel');
    const backdrop = document.getElementById('workflowsBackdrop');
    if (!panel || !backdrop) return;

    if (panel.classList.contains('open')) {
        closeActiveWorkflows();
        return;
    }

    panel.classList.add('open');
    backdrop.classList.add('open');

    const list = document.getElementById('activeWorkflowsList');
    list.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--md-muted); font-size: 12px;">Loading active tasks...</div>';

    try {
        const token = localStorage.getItem('orch-session-token');
        const res = await fetch('/api/tasks', { headers: { 'X-Session-Token': token } });
        const data = await res.json();
        const inProgress = (data.tasks || []).filter(t => t.status === 'in_progress');

        if (inProgress.length === 0) {
            list.innerHTML = '<div style="padding: 32px; text-align: center; color: var(--md-muted);"><span class="ms" style="font-size: 32px; display: block; margin-bottom: 8px; opacity: 0.3;">inventory_2</span>No workflows currently running.</div>';
            return;
        }

        list.innerHTML = inProgress.map(wf => `
            <div class="notif-item" onclick="window.switchView('workflows'); window.closeActiveWorkflows();">
                <div class="ni-icon" style="background: var(--g-blue-light); color: var(--g-blue);"><span class="ms">bolt</span></div>
                <div class="ni-body">
                    <div class="ni-title">${wf.title}</div>
                    <div class="ni-desc">Priority: ${wf.priority.toUpperCase()} • Status: In Progress</div>
                    <div class="ni-time">Target: ${wf.due_date ? new Date(wf.due_date).toLocaleDateString() : 'No deadline'}</div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--g-red);">Error loading active workflows.</div>';
    }
}

export function openPalette() {
    const p   = document.getElementById('palette');
    const b   = document.getElementById('paletteBackdrop');
    const inp = document.getElementById('paletteInput');
    if (p && b) {
        p.classList.add('open');
        b.classList.add('open');
        if (inp) { inp.value = ''; setTimeout(() => inp.focus(), 50); }
    }
}

export function closePalette() {
    const p = document.getElementById('palette');
    const b = document.getElementById('paletteBackdrop');
    if (p && b) { p.classList.remove('open'); b.classList.remove('open'); }
}

document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); openPalette(); }
    if (e.key === 'Escape') closePalette();
});

// ── Task completion toast ─────────────────────────────────────────────────────
document.addEventListener('click', e => {
    const check = e.target.closest('.ti-check');
    if (!check) return;
    const wasDown = check.classList.contains('done');
    check.classList.toggle('done');
    check.textContent = wasDown ? '' : '✓';
    const titleEl = check.closest('.task-intel-item')?.querySelector('.ti-title');
    if (titleEl) titleEl.classList.toggle('done-text', !wasDown);
    const priorityEl = check.closest('.task-intel-item')?.querySelector('.ti-priority');
    if (priorityEl && !wasDown) {
        priorityEl.style.background = 'var(--g-green-light)';
        priorityEl.style.color = 'var(--g-green)';
        priorityEl.textContent = 'done';
    }
    if (!wasDown) showCompletionToast(titleEl?.textContent || 'Task');
});

window.switchView        = switchView;
window.openWorkflowsPage = openWorkflowsPage;
window.openPalette       = openPalette;
window.closePalette      = closePalette;
window.toggleActiveWorkflows = toggleActiveWorkflows;
window.closeActiveWorkflows = closeActiveWorkflows;
window.showCompletionToast = showCompletionToast;
