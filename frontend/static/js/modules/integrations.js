import { apiFetch } from './api.js';
import { activityFeed } from './feed.js';

// ── Connect / disconnect ──────────────────────────────────────────────────────

export async function connectIntegration(service) {
    let body = {};
    if (service === 'github') {
        const token = document.getElementById('github-token-input')?.value?.trim();
        if (!token) { alert('Please enter your GitHub Personal Access Token'); return; }
        body = { token };
    } else if (service === 'slack') {
        const token = document.getElementById('slack-token-input')?.value?.trim();
        if (!token) { alert('Please enter your Slack OAuth Token'); return; }
        body = { token };
    } else if (service === 'gmail') {
        const client_id     = document.getElementById('gmail-client-id')?.value?.trim();
        const client_secret = document.getElementById('gmail-client-secret')?.value?.trim();
        const refresh_token = document.getElementById('gmail-refresh-token')?.value?.trim();
        if (!client_id || !client_secret || !refresh_token) {
            alert('Please fill in all Gmail fields'); return;
        }
        body = { client_id, client_secret, refresh_token };
    }

    try {
        const res  = await apiFetch(`/api/integrations/${service}/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Connection failed');
        }
        activityFeed.log(`✅ ${service.charAt(0).toUpperCase()+service.slice(1)} connected`, 'success', 'SYSTEM');
        setConnected(service, true);
        refreshNavBadge();
    } catch (e) {
        alert(`Could not connect ${service}: ${e.message}`);
    }
}

export async function disconnectIntegration(service) {
    if (!confirm(`Disconnect ${service}? Orchestra will stop fetching data from it.`)) return;
    await apiFetch(`/api/integrations/${service}/connect`, { method: 'DELETE' });
    setConnected(service, false);
    activityFeed.log(`${service} disconnected`, 'status', 'SYSTEM');
    refreshNavBadge();
}

function refreshNavBadge() {
    if (window.loadIntegrationStatuses) window.loadIntegrationStatuses();
    apiFetch('/api/integrations/status').then(r => r.ok ? r.json() : null).then(data => {
        if (!data) return;
        const count = Object.values(data).filter(s => s.connected).length;
        const badge = document.getElementById('int-nav-badge');
        if (!badge) return;
        badge.textContent = count + '/3';
        badge.className = count === 0 ? 'nav-badge nb-gray' : count < 3 ? 'nav-badge nb-amber' : 'nav-badge nb-green';
    }).catch(() => {});
}

function setConnected(service, connected) {
    const svc = service === 'email' ? 'gmail' : service;
    document.getElementById(`int-form-${svc}`)?.style  && (document.getElementById(`int-form-${svc}`).style.display      = connected ? 'none'  : '');
    document.getElementById(`int-connected-${svc}`)?.style && (document.getElementById(`int-connected-${svc}`).style.display = connected ? ''     : 'none');
    const statusEl = document.getElementById(`int-status-${svc}`);
    if (statusEl) {
        statusEl.textContent = connected ? '● Connected' : '○ Not connected';
        statusEl.style.color = connected ? 'var(--g-green)' : 'var(--md-dim)';
    }
}

// ── Load status on settings page open ────────────────────────────────────────

export async function loadIntegrationStatuses() {
    try {
        const res  = await apiFetch('/api/integrations/status');
        if (!res.ok) return;
        const data = await res.json();
        for (const [svc, info] of Object.entries(data)) {
            setConnected(svc, info.connected);
        }
    } catch (_) {}
}

// ── Fetch + render integration data in intel pane ────────────────────────────

export async function fetchIntegrationPane(service) {
    const paneId   = service === 'email' ? 'gmail' : service;
    const content  = document.getElementById(`${paneId}-pane-content`);
    const labelEl  = document.getElementById(`${paneId}-source-label`);
    if (!content) return;

    content.innerHTML = `<div style="padding:20px;text-align:center;color:var(--md-dim);font-size:12px">
        <span class="ms" style="font-size:24px;display:block;margin-bottom:8px;animation:spin 1s linear infinite">refresh</span>
        Fetching from ${service}…</div>`;

    try {
        const endpoint = service === 'gmail' ? '/api/integrations/gmail' : `/api/integrations/${service}`;
        const res = await apiFetch(endpoint);
        if (res.status === 404) {
            content.innerHTML = `<div class="int-connect-prompt">
                <span class="ms" style="font-size:32px;color:var(--md-dim)">link_off</span>
                <div style="font-size:13px;font-weight:600;margin:8px 0 4px">${service.charAt(0).toUpperCase()+service.slice(1)} not connected</div>
                <div style="font-size:12px;color:var(--md-dim);margin-bottom:12px">Go to Integrations to connect your account.</div>
                <button class="goal-run" style="font-size:12px" onclick="window.switchView('integrations-settings')"><span class="ms sm">settings</span> Connect</button>
            </div>`;
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (service === 'github')  renderGitHubPane(data, content, labelEl);
        if (service === 'slack')   renderSlackPane(data, content, labelEl);
        if (service === 'gmail')   renderGmailPane(data, content, labelEl);

    } catch (e) {
        content.innerHTML = `<div style="padding:20px;text-align:center;color:var(--g-red);font-size:12px">
            Failed to load ${service} data: ${e.message}</div>`;
    }
}

// ── GitHub renderer ───────────────────────────────────────────────────────────

function renderGitHubPane(data, el, label) {
    if (label) label.textContent = `GitHub · @${data.username} · 7-day digest`;
    const stateColor = { open:'var(--g-blue)', merged:'var(--g-green)', blocked:'var(--g-red)', draft:'var(--md-dim)' };
    const stateLabel = { open:'Open', merged:'Merged', blocked:'Blocked', draft:'Draft' };

    const prHtml = (data.pull_requests||[]).slice(0,6).map(pr => `
        <div class="task-intel-item" style="cursor:pointer" onclick="window.open('${pr.url}','_blank')">
            <div class="ti-check" style="background:${stateColor[pr.state]||'var(--g-blue)'};color:white;font-size:10px">#${pr.id}</div>
            <div style="flex:1;min-width:0">
                <div class="ti-title" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${pr.title}</div>
                <div style="display:flex;gap:6px;margin-top:4px;flex-wrap:wrap">
                    <span class="ti-priority" style="background:${stateColor[pr.state]}22;color:${stateColor[pr.state]}">${stateLabel[pr.state]||pr.state}</span>
                    <span class="ti-due">${pr.repo} · ${pr.updated}</span>
                </div>
            </div>
        </div>`).join('');

    const reviewHtml = (data.reviews_requested||[]).slice(0,3).map(pr => `
        <div class="task-intel-item" style="cursor:pointer" onclick="window.open('${pr.url}','_blank')">
            <div class="ti-check" style="background:var(--g-amber);color:white;font-size:9px">Rev</div>
            <div><div class="ti-title">${pr.title}</div><div style="font-size:10px;color:var(--md-dim)">${pr.repo}</div></div>
        </div>`).join('');

    const issueHtml = (data.open_issues||[]).slice(0,4).map(i => `
        <div class="task-intel-item" style="cursor:pointer" onclick="window.open('${i.url}','_blank')">
            <div class="ti-check" style="background:var(--g-violet);color:white;font-size:9px">!</div>
            <div><div class="ti-title">${i.title}</div><div style="font-size:10px;color:var(--md-dim)">${i.repo}</div></div>
        </div>`).join('');

    el.innerHTML = `
        ${prHtml ? `<div style="font-size:10px;font-weight:700;color:var(--md-dim);letter-spacing:.5px;margin:4px 0 8px">YOUR PULL REQUESTS</div><div class="task-intel-grid">${prHtml}</div>` : ''}
        ${reviewHtml ? `<div style="font-size:10px;font-weight:700;color:var(--md-dim);letter-spacing:.5px;margin:12px 0 8px">REVIEW REQUESTED</div><div class="task-intel-grid">${reviewHtml}</div>` : ''}
        ${issueHtml ? `<div style="font-size:10px;font-weight:700;color:var(--md-dim);letter-spacing:.5px;margin:12px 0 8px">ASSIGNED ISSUES</div><div class="task-intel-grid">${issueHtml}</div>` : ''}
        ${!prHtml && !reviewHtml && !issueHtml ? '<div style="padding:24px;text-align:center;color:var(--md-dim);font-size:12px">No activity in the last 7 days</div>' : ''}`;
}

// ── Slack renderer ────────────────────────────────────────────────────────────

function renderSlackPane(data, el, label) {
    if (label) label.textContent = `Slack · @${data.username} · 7-day digest`;

    const mentionHtml = (data.mentions||[]).slice(0,6).map(m => `
        <div class="task-intel-item" style="cursor:pointer" onclick="window.open('${m.url||'https://app.slack.com'}','_blank')">
            <div class="ti-check" style="background:var(--g-violet);color:white;font-size:10px">@</div>
            <div><div class="ti-title">${m.text.replace(/<[^>]+>/g,' ').trim()}</div>
            <div style="display:flex;gap:6px;margin-top:4px">
                <span class="ti-priority" style="background:var(--g-violet-light);color:var(--g-violet)">mention</span>
                <span class="ti-due">${m.channel} · ${m.ts}</span>
            </div></div>
        </div>`).join('');

    const actionHtml = (data.action_items||[]).slice(0,4).map(a => `
        <div class="task-intel-item">
            <div class="ti-check" style="background:var(--g-amber);color:white;font-size:9px">→</div>
            <div><div class="ti-title">${a.text.replace(/<[^>]+>/g,' ').trim()}</div>
            <div style="display:flex;gap:6px;margin-top:4px">
                <span class="ti-priority" style="background:var(--g-amber-light);color:var(--g-amber)">action</span>
                <span class="ti-due">${a.channel} · ${a.ts}</span>
            </div></div>
        </div>`).join('');

    el.innerHTML = `
        <div style="font-size:11px;color:var(--md-dim);margin-bottom:10px">${data.week_count||0} messages across ${(data.channels||[]).length} channels this week</div>
        ${mentionHtml ? `<div style="font-size:10px;font-weight:700;color:var(--md-dim);letter-spacing:.5px;margin-bottom:8px">MENTIONS</div><div class="task-intel-grid">${mentionHtml}</div>` : ''}
        ${actionHtml ? `<div style="font-size:10px;font-weight:700;color:var(--md-dim);letter-spacing:.5px;margin:12px 0 8px">ACTION ITEMS</div><div class="task-intel-grid">${actionHtml}</div>` : ''}
        ${!mentionHtml && !actionHtml ? '<div style="padding:24px;text-align:center;color:var(--md-dim);font-size:12px">No mentions or action items this week</div>' : ''}`;
}

// ── Gmail renderer ────────────────────────────────────────────────────────────

function renderGmailPane(data, el, label) {
    if (label) label.textContent = `Gmail · ${data.email} · ${data.unread_count} unread`;

    const emailHtml = (data.urgent||[]).slice(0,8).map(e => `
        <div class="task-intel-item" style="cursor:pointer" onclick="window.open('${e.url}','_blank')">
            <div class="ti-check" style="background:${e.priority==='high'?'var(--g-red)':'var(--g-blue)'};color:white;font-size:9px">M</div>
            <div style="flex:1;min-width:0">
                <div class="ti-title" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${e.subject}</div>
                <div style="font-size:10px;color:var(--md-dim);margin:2px 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${e.snippet}</div>
                <div style="display:flex;gap:6px">
                    <span class="ti-priority" style="background:${e.priority==='high'?'var(--g-red-light)':'var(--g-blue-light)'};color:${e.priority==='high'?'var(--g-red)':'var(--g-blue)'}">${e.priority}</span>
                    <span class="ti-due">${e.from.replace(/<.*?>/g,'').trim()}</span>
                </div>
            </div>
        </div>`).join('');

    el.innerHTML = emailHtml || '<div style="padding:24px;text-align:center;color:var(--md-dim);font-size:12px">No urgent emails this week</div>';
}

// ── Wire into window and demos ────────────────────────────────────────────────

window.connectIntegration    = connectIntegration;
window.disconnectIntegration = disconnectIntegration;
window.loadIntegrationStatuses = loadIntegrationStatuses;
window.fetchIntegrationPane  = fetchIntegrationPane;
