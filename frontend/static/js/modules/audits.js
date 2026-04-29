import { apiFetch } from './api.js';

export async function fetchVibeChecks() {
    const container = document.getElementById('vibe-check-results');
    if (!container) return;
    try {
        const res = await apiFetch('/audit-history');
        if (!res.ok) throw new Error('Failed to fetch vibe checks');
        const data = await res.json();
        
        if (!data.recent_audits || data.recent_audits.length === 0) {
            container.innerHTML = `<div class="empty-state" style="padding:40px; text-align:center; background:var(--md-surface-1); border-radius:16px">
                <span class="ms" style="font-size:32px;display:block;margin-bottom:12px;color:var(--md-dim)">security</span>
                <div style="font-weight:600;margin-bottom:8px">All Systems Safe</div>
                <p style="color:var(--md-dim)">No audits conducted yet. The AuditorAgent runs automatically on high-stakes actions.</p>
            </div>`;
            return;
        }

        container.innerHTML = data.recent_audits.map(audit => `
            <div class="run-card" style="margin-bottom:16px; border-left:4px solid ${audit.approval_status === 'approved' ? 'var(--g-green)' : (audit.approval_status === 'escalated' ? 'var(--g-red)' : 'var(--g-amber)')}">
                <div style="display:flex; justify-content:space-between; align-items:flex-start">
                    <div>
                        <div style="font-size:11px; color:var(--md-dim); margin-bottom:4px">Audit ID: ${audit.action_id}</div>
                        <div style="font-weight:600; font-size:14px; margin-bottom:4px">Action: ${audit.executor_agent} execution</div>
                        <div style="font-size:12px; color:var(--md-on-surface)">${audit.final_recommendation}</div>
                    </div>
                    <div class="nav-badge ${audit.approval_status === 'approved' ? 'nb-green' : 'nb-red'}">${audit.approval_status.toUpperCase()}</div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error(e);
        container.innerHTML = `<div style="color:var(--g-red)">Failed to load vibe checks.</div>`;
    }
}

export async function fetchDebates() {
    const container = document.getElementById('debate-list');
    if (!container) return;
    try {
        const res = await apiFetch('/debate-history');
        if (!res.ok) throw new Error('Failed to fetch debates');
        const data = await res.json();
        
        if (!data.recent_debates || data.recent_debates.length === 0) {
            container.innerHTML = `<div class="empty-state" style="padding:40px; text-align:center; background:var(--md-surface-1); border-radius:16px">
                <span class="ms" style="font-size:32px;display:block;margin-bottom:12px;color:var(--md-dim)">forum</span>
                <div style="font-weight:600;margin-bottom:8px">No Active Debates</div>
                <p style="color:var(--md-dim)">Debates trigger automatically when high-stakes decisions require team consensus.</p>
            </div>`;
            return;
        }

        container.innerHTML = data.recent_debates.map(debate => `
            <div class="run-card" style="margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
                    <div style="font-weight:600; font-size:14px">${debate.action}</div>
                    <div class="nav-badge ${debate.consensus ? 'nb-green' : 'nb-amber'}">${debate.recommendation}</div>
                </div>
                <div style="font-size:12px; color:var(--md-dim); margin-bottom:12px">${debate.issue}</div>
                
                <div style="display:flex; gap:8px; margin-bottom:12px; font-size:11px">
                    <span style="color:var(--g-green)">👍 Support: ${debate.votes.support}</span>
                    <span style="color:var(--g-blue)">🤔 Conditional: ${debate.votes.conditional_support}</span>
                    <span style="color:var(--g-amber)">⚠️ Concern: ${debate.votes.concern}</span>
                    <span style="color:var(--g-red)">🚫 Oppose: ${debate.votes.oppose}</span>
                </div>
                
                <div style="font-size:11px; background:var(--md-surface-1); padding:8px; border-radius:6px">
                    <div style="font-weight:600; margin-bottom:4px">Team Confidence: ${debate.overall_confidence}</div>
                    ${debate.dissenting_agents.length > 0 ? `<div style="color:var(--g-red)">Dissenting: ${debate.dissenting_agents.join(', ')}</div>` : '<div style="color:var(--g-green)">Unanimous Agreement</div>'}
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error(e);
        container.innerHTML = `<div style="color:var(--g-red)">Failed to load debates.</div>`;
    }
}

window.fetchVibeChecks = fetchVibeChecks;
window.fetchDebates = fetchDebates;
