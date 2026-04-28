import { apiUrl, apiFetch } from './api.js';
import { activityFeed } from './feed.js';
import { renderNews, renderResearch, renderStatusOverview, renderAuditReport, renderDigest } from './renderers.js';

let _nlActiveStream = null;
let _activeWorkflowBoard = null;
let _workflowLiveState = {
    workflow_id: null,
    goal: '',
    status: 'idle',
    progress: 0,
    plan_revision: 0,
    total_steps: 0,
    steps: [],
    logs: [],
};

const WORKFLOW_STATUS_META = {
    idle:       { label: 'Idle',       color: 'var(--md-dim)', bg: 'var(--md-surface-2)', dot: 'var(--md-dim)' },
    planning:   { label: 'Planning',   color: 'var(--g-amber)', bg: 'var(--g-amber-light)', dot: 'var(--g-amber)' },
    replanning: { label: 'Replanning', color: 'var(--g-violet)', bg: 'var(--g-violet-light)', dot: 'var(--g-violet)' },
    replanned:  { label: 'Replanned',  color: 'var(--g-violet)', bg: 'var(--g-violet-light)', dot: 'var(--g-violet)' },
    executing:  { label: 'Executing',  color: 'var(--g-green)', bg: 'var(--g-green-light)', dot: 'var(--g-green-mid)' },
    completed:  { label: 'Done',       color: 'var(--g-green)', bg: 'var(--g-green-light)', dot: 'var(--g-green-mid)' },
    failed:     { label: 'Failed',     color: 'var(--g-red)', bg: 'var(--g-red-light)', dot: 'var(--g-red)' },
};

function workflowMeta(status) {
    return WORKFLOW_STATUS_META[(status || 'idle').toLowerCase()] || WORKFLOW_STATUS_META.idle;
}

function workflowStepMeta(status) {
    const map = {
        pending:   { label: 'Pending',   color: 'var(--md-dim)', bg: 'var(--md-surface-1)' },
        starting:  { label: 'Starting',  color: 'var(--g-blue)', bg: 'var(--g-blue-light)' },
        executing: { label: 'Executing', color: 'var(--g-green)', bg: 'var(--g-green-light)' },
        completed: { label: 'Completed', color: 'var(--g-green)', bg: 'var(--g-green-light)' },
        failed:    { label: 'Failed',    color: 'var(--g-red)', bg: 'var(--g-red-light)' },
        replanning:{ label: 'Replanning', color: 'var(--g-violet)', bg: 'var(--g-violet-light)' },
        replanned: { label: 'Replanned',  color: 'var(--g-violet)', bg: 'var(--g-violet-light)' },
    };
    return map[(status || 'pending').toLowerCase()] || map.pending;
}

function normalizeWorkflowSteps(steps = []) {
    return (steps || []).map((step, index) => ({
        step_id: Number.isFinite(step.step_id) ? step.step_id : index,
        sequence_index: Number.isFinite(step.sequence_index) ? step.sequence_index : index + 1,
        name: step.name || step.action || `Step ${index + 1}`,
        agent: (step.agent || 'orchestrator').toLowerCase(),
        detail: step.detail || step.description || step.message || '',
        params: step.params || {},
        status: (step.status || 'pending').toLowerCase(),
        result_summary: step.result_summary || '',
        duration_seconds: Number.isFinite(step.duration_seconds) ? step.duration_seconds : null,
    }));
}

function pushWorkflowLog(entry) {
    if (!entry) return;
    const logs = [entry, ...(_workflowLiveState.logs || [])].slice(0, 6);
    _workflowLiveState = { ..._workflowLiveState, logs };
}

function renderWorkflowStepCard(step, isActive = false) {
    const meta = workflowStepMeta(step.status);
    const detail = step.detail || step.result_summary || 'Working through the current step.';
    return `
        <div class="workflow-step-card ${step.status}" style="${isActive ? 'background:linear-gradient(135deg, rgba(124,77,255,0.08), rgba(26,115,232,0.05));' : ''}">
            <div class="workflow-step-top">
                <div style="min-width:0">
                    <div class="workflow-step-name">${step.sequence_index}. ${step.name}</div>
                    <div class="workflow-step-meta">
                        <span class="workflow-step-chip active">${step.agent}</span>
                        <span class="workflow-step-chip">Step ${step.sequence_index}</span>
                        <span class="workflow-step-chip" style="background:${meta.bg};color:${meta.color};border-color:transparent">${meta.label}</span>
                    </div>
                </div>
                <span class="workflow-step-chip" style="background:${meta.bg};color:${meta.color};border-color:transparent">${meta.label}</span>
            </div>
            <div class="workflow-step-desc">${detail}</div>
            ${step.duration_seconds != null ? `<div class="workflow-step-desc" style="margin-top:6px">Duration: <strong>${step.duration_seconds}s</strong>${step.result_summary ? ` · ${step.result_summary}` : ''}</div>` : ''}
        </div>`;
}

function renderWorkflowLogItem(entry = {}) {
    const meta = workflowMeta(entry.status || entry.stage || 'executing');
    return `
        <div class="workflow-log-item" style="border-left:3px solid ${meta.color}">
            <div class="workflow-log-title">${entry.title || entry.agent || 'Orchestrator'}${entry.time ? ` · ${entry.time}` : ''}</div>
            <div class="workflow-log-body">${entry.body || entry.message || 'Live workflow update.'}</div>
        </div>`;
}

function renderPlanningSkeleton(status = 'planning') {
    const label = status === 'replanning' ? 'Rebuilding plan with Critic feedback…' : 'Orchestrator is drafting the execution graph…';
    const stages = [
        { title: 'Goal intake', agent: 'Orchestrator', detail: 'Parsing user intent and constraints.' },
        { title: 'Plan synthesis', agent: 'Planner', detail: 'Creating the shortest safe path.' },
        { title: 'Critic review', agent: 'Critic', detail: 'Checking dependencies and bottlenecks.' },
        { title: 'Execution dispatch', agent: 'Executor', detail: 'Waiting to launch the first agent step.' },
    ];

    return `
        <div class="workflow-empty-state" style="padding:18px 16px">
            <div class="workflow-live-title" style="font-size:16px;margin-bottom:6px">${label}</div>
            <div class="workflow-live-sub" style="margin-bottom:14px">This is the actual planning phase, not a dead screen. The orchestrator is building the plan before the agent steps begin.</div>
            <div class="workflow-step-list">
                ${stages.map((stage, idx) => `
                    <div class="workflow-step-card ${idx === 0 ? 'starting' : 'pending'}" style="background:linear-gradient(135deg, rgba(124,77,255,0.06), rgba(26,115,232,0.04));">
                        <div class="workflow-step-top">
                            <div style="min-width:0">
                                <div class="workflow-step-name">${idx + 1}. ${stage.title}</div>
                                <div class="workflow-step-meta">
                                    <span class="workflow-step-chip active">${stage.agent}</span>
                                    <span class="workflow-step-chip">Planning</span>
                                </div>
                            </div>
                            <span class="workflow-step-chip" style="background:var(--g-violet-light);color:var(--g-violet);border-color:transparent">
                                ${idx === 0 ? 'Live' : 'Queued'}
                            </span>
                        </div>
                        <div class="workflow-step-desc">${stage.detail}</div>
                    </div>
                `).join('')}
            </div>
        </div>`;
}

function renderWorkflowBoard(state = {}) {
    const container = document.getElementById('workflow-live-board');
    if (!container) return null;

    const nextSteps = state.steps ? normalizeWorkflowSteps(state.steps) : _workflowLiveState.steps;
    const nextLogs = state.logs ? state.logs.slice(0, 6) : _workflowLiveState.logs;
    const merged = {
        ..._workflowLiveState,
        ...state,
        steps: nextSteps,
        logs: nextLogs,
        workflow_id: state.workflow_id || _workflowLiveState.workflow_id,
        goal: state.goal || _workflowLiveState.goal,
        status: (state.status || _workflowLiveState.status || 'idle').toLowerCase(),
        progress: Number.isFinite(state.progress) ? Math.max(0, Math.min(100, state.progress)) : _workflowLiveState.progress,
        plan_revision: Number.isFinite(state.plan_revision) ? state.plan_revision : _workflowLiveState.plan_revision,
        total_steps: Number.isFinite(state.total_steps) ? state.total_steps : (nextSteps.length || _workflowLiveState.total_steps),
    };

    _workflowLiveState = merged;

    const meta = workflowMeta(merged.status);
    const activeStep = merged.steps.find(step => ['starting', 'executing'].includes(step.status))
        || merged.steps.find(step => step.status === 'replanning')
        || merged.steps.find(step => step.status === 'pending')
        || merged.steps[0];
    const stageCards = [
        { key: 'planning',   label: 'Planner',   value: 'Drafting plan' },
        { key: 'replanning', label: 'Critic',    value: 'Reviewing path' },
        { key: 'executing',  label: 'Executor',  value: 'Running steps' },
        { key: 'completed',  label: 'Outcome',   value: 'Workflow finished' },
    ].map(stage => {
        const active = merged.status === stage.key || (stage.key === 'executing' && ['starting', 'executing', 'replanned'].includes(merged.status));
        return `
            <div class="workflow-stage${active ? ' active' : ''}">
                <div class="workflow-stage-label">${stage.label}</div>
                <div class="workflow-stage-value">${stage.value}</div>
            </div>`;
    }).join('');

    const summaryChips = [
        merged.workflow_id ? `ID ${merged.workflow_id}` : null,
        `${merged.total_steps || 0} step${(merged.total_steps || 0) === 1 ? '' : 's'}`,
        `Revision ${merged.plan_revision || 0}`,
        activeStep ? `Active: ${activeStep.agent}` : 'Awaiting plan',
    ].filter(Boolean).map(label => `<span class="chip">${label}</span>`).join('');

    const stepsHtml = merged.steps.length
        ? merged.steps.map(step => renderWorkflowStepCard(step, activeStep && step.step_id === activeStep.step_id)).join('')
        : renderPlanningSkeleton(merged.status);

    const logsHtml = nextLogs.length
        ? nextLogs.map(renderWorkflowLogItem).join('')
        : `<div class="workflow-empty-state">Planner, Critic, and Executor updates will appear here as soon as the plan starts moving.</div>`;

    container.innerHTML = `
        <div class="workflow-live-head">
            <div style="min-width:0">
                <div class="workflow-live-title">Live Workflow Journey</div>
                <div class="workflow-live-sub">${merged.goal || 'New workflow'} · ${meta.label} · ${merged.progress || 0}% complete</div>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;align-items:flex-start">
                <span class="run-tag tag-live" style="background:${meta.bg};color:${meta.color}">
                    <span class="tag-dot" style="background:${meta.dot}"></span>${meta.label}
                </span>
                ${summaryChips}
            </div>
        </div>
        <div class="run-bar-bg" style="height:8px;margin-top:4px"><div class="run-bar-fill" style="width:${merged.progress || 0}%;background:${meta.dot}"></div></div>
        <div class="workflow-stage-strip">${stageCards}</div>
        <div class="workflow-board-grid">
            <div class="workflow-panel">
                <div class="workflow-panel-head">
                    <div class="workflow-panel-title">Execution Plan</div>
                    <span class="chip">Planner ↔ Critic ↔ Executor</span>
                </div>
                <div class="workflow-step-list">${stepsHtml}</div>
            </div>
            <div class="workflow-panel">
                <div class="workflow-panel-head">
                    <div class="workflow-panel-title">Live Reasoning</div>
                    <span class="chip">${merged.logs.length || 0} updates</span>
                </div>
                <div class="workflow-log-list">${logsHtml}</div>
            </div>
        </div>`;

    container.style.display = 'block';
    _activeWorkflowBoard = container;
    return container;
}

function updateWorkflowBoardState(payload = {}) {
    const nextSteps = payload.steps ? normalizeWorkflowSteps(payload.steps) : _workflowLiveState.steps;
    const nextLogs = payload.logs ? payload.logs.slice(0, 6) : _workflowLiveState.logs;
    return renderWorkflowBoard({
        ...payload,
        steps: nextSteps,
        logs: nextLogs,
    });
}

function upsertWorkflowStep(payload = {}) {
    const stepId = Number.isFinite(payload.step_id) ? payload.step_id : null;
    const nextSteps = normalizeWorkflowSteps(_workflowLiveState.steps);
    const idx = nextSteps.findIndex(step => step.step_id === stepId);
    const status = (payload.status || 'executing').toLowerCase();
    const step = {
        step_id: stepId ?? nextSteps.length,
        sequence_index: Number.isFinite(payload.sequence_index) ? payload.sequence_index : (idx >= 0 ? nextSteps[idx].sequence_index : nextSteps.length + 1),
        name: payload.step_name || payload.name || (idx >= 0 ? nextSteps[idx].name : `Step ${nextSteps.length + 1}`),
        agent: (payload.agent || (idx >= 0 ? nextSteps[idx].agent : 'orchestrator')).toLowerCase(),
        detail: payload.message || payload.result_summary || (idx >= 0 ? nextSteps[idx].detail : ''),
        params: idx >= 0 ? nextSteps[idx].params : {},
        status,
        result_summary: payload.result_summary || (status === 'completed' ? 'Completed' : ''),
        duration_seconds: Number.isFinite(payload.duration_seconds) ? payload.duration_seconds : (idx >= 0 ? nextSteps[idx].duration_seconds : null),
    };

    if (idx >= 0) nextSteps[idx] = step;
    else nextSteps.push(step);

    const completed = nextSteps.filter(s => s.status === 'completed').length;
    const progress = status === 'completed'
        ? Math.max(_workflowLiveState.progress || 0, Math.round((completed / Math.max(nextSteps.length, 1)) * 100))
        : _workflowLiveState.progress;

    pushWorkflowLog({
        title: `${step.agent.toUpperCase()} · ${step.name}`,
        body: payload.message || payload.result_summary || `Step ${step.sequence_index} ${status}`,
        status,
    });

    return renderWorkflowBoard({
        workflow_id: payload.workflow_id || _workflowLiveState.workflow_id,
        goal: payload.goal || _workflowLiveState.goal,
        status: status === 'starting' ? 'executing' : _workflowLiveState.status,
        progress,
        plan_revision: Number.isFinite(payload.plan_revision) ? payload.plan_revision : _workflowLiveState.plan_revision,
        total_steps: nextSteps.length,
        steps: nextSteps,
    });
}

function renderWorkflowCard(state = {}) {
    return renderWorkflowBoard(state);
}

function updateWorkflowCardState(payload = {}) {
    if (payload.steps) return updateWorkflowBoardState(payload);
    if (payload.step_id != null || payload.step_name || payload.agent) return upsertWorkflowStep(payload);
    return renderWorkflowBoard(payload);
}

export async function submitGoal() {
    const textarea  = document.getElementById('nl-goal-input');
    const submitBtn = document.getElementById('nl-submit-btn');
    const priority  = document.getElementById('nl-priority')?.value || 'medium';
    const goal      = (textarea.value || '').trim();
    if (!goal) return;

    // ── Real streaming orchestration ─────────────────────────────────────────
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="ms sm fa-spin">progress_activity</span> Running…';
    textarea.disabled = true;

    if (_nlActiveStream) _nlActiveStream.abort();
    const controller  = new AbortController();
    _nlActiveStream   = controller;

    activityFeed.log(`🚀 Initiating workflow: <strong>${goal}</strong>`, 'user', 'USER');
    if (window.switchView) window.switchView('workflows');
    renderWorkflowBoard({
        workflow_id: `wf-${Date.now().toString(36)}`,
        goal,
        status: 'planning',
        progress: 10,
        plan_revision: 0,
        total_steps: 0,
        steps: [],
        logs: [{
            title: 'Orchestrator',
            body: 'Preparing execution plan…',
            status: 'planning',
        }],
    });

    try {
        const res = await apiFetch('/orchestrate/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal, priority }),
            signal: controller.signal,
        });
        if (res.status === 401) {
            activityFeed.log('🔒 Session expired — please <a href="/login" style="color:var(--g-blue)">log in again</a>.', 'error', 'SYSTEM');
            localStorage.removeItem('orch-session-token');
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer    = '';

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
                    } else if (event === 'workflow-state') {
                        updateWorkflowCardState(payload);
                    } else if (event === 'workflow-plan') {
                        updateWorkflowBoardState({
                            ...payload,
                            logs: [{
                                title: 'Planner',
                                body: payload.message || `Plan published with ${payload.total_steps || 0} steps.`,
                                status: payload.status || 'planning',
                            }],
                        });
                    } else if (event === 'workflow-step') {
                        updateWorkflowCardState(payload);
                    } else if (event === 'render-digest') {
                        try { renderDigest(payload); } catch(e) { activityFeed.log(`⚠️ Digest render error: ${e.message}`, 'error', 'SYSTEM'); }
                    } else if (event === 'render-audit') {
                        try { renderAuditReport(payload); } catch(e) { activityFeed.log(`⚠️ Audit render error: ${e.message}`, 'error', 'SYSTEM'); }
                    } else if (event === 'render-status') {
                        try { renderStatusOverview(payload); } catch(e) { activityFeed.log(`⚠️ Status render error: ${e.message}`, 'error', 'SYSTEM'); }
                    } else if (event === 'render-news') {
                        renderNews(payload.articles || []);
                        const newsTab = document.querySelector('.intel-tab');
                        if (window.switchIntel) window.switchIntel('news', newsTab);
                    } else if (event === 'render-research') {
                        renderResearch(payload.papers || []);
                        if (window.switchIntel) window.switchIntel('research');
                    } else if (event === 'celebrate') {
                        activityFeed.log(`✨ <strong>Celebration:</strong> ${payload.message}`, 'success', 'SYSTEM');
                        if (typeof confetti === 'function') {
                            confetti({ 
                                particleCount: 150, 
                                spread: 70, 
                                origin: { y: 0.6 }, 
                                colors: ['#1a73e8','#34a853','#fbbc04','#ea4335'] 
                            });
                        }
                    } else if (event === 'done') {
                        // Refresh intel panel so newly created tasks/events appear immediately
                        if ((payload.tasks_created || 0) > 0)    window.runDemo?.('tasks');
                        if ((payload.events_scheduled || 0) > 0) window.runDemo?.('schedule');

                        const steps    = payload.steps            || 0;
                        const tasks    = payload.tasks_created    || 0;
                        const events   = payload.events_scheduled || 0;
                        const parts    = [];
                        if (steps)  parts.push(`${steps} step${steps  !== 1 ? 's' : ''}`);
                        if (tasks)  parts.push(`${tasks} task${tasks  !== 1 ? 's' : ''} created`);
                        if (events) parts.push(`${events} event${events !== 1 ? 's' : ''} scheduled`);
                        const summary  = parts.length ? parts.join(' · ') : 'No output generated';
                        activityFeed.log(
                            `<strong>Workflow complete</strong> — ${summary}`,
                            'success', 'SYSTEM'
                        );
                        renderWorkflowBoard({
                            goal,
                            status: 'completed',
                            progress: 100,
                            plan_revision: 0,
                            total_steps: _workflowLiveState.total_steps || 0,
                            logs: [{
                                title: 'Orchestrator',
                                body: summary,
                                status: 'completed',
                            }, ...(_workflowLiveState.logs || [])],
                        });
                    }
                } catch (e) { console.warn('SSE Parse Error:', e); }
            }
        }
    } catch (err) {
        if (err.name !== 'AbortError') activityFeed.log(`❌ Workflow Error: ${err.message}`, 'error', 'SYSTEM');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span class="ms sm">play_arrow</span> Run';
        textarea.disabled  = false;
        textarea.value     = '';
        window.autoExpandGoal(textarea);
    }
}

window.submitGoal = submitGoal;
window.renderWorkflowCard = renderWorkflowCard;
