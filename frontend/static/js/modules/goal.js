import { apiUrl, apiFetch } from './api.js';
import { activityFeed } from './feed.js';
import { showCompletionToast } from './navigation.js';
import { renderNews, renderResearch } from './renderers.js';

let _nlActiveStream = null;

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

    const wfList = document.getElementById('workflows-list');
    if (wfList) wfList.innerHTML = `
        <div class="run-card live" style="margin-bottom:12px">
            <div><div class="run-title">${goal}</div>
            <div class="run-meta"><span class="run-tag tag-live"><span class="tag-dot"></span>Live</span><span class="chip">Orchestrator</span><span style="font-family:var(--font-mono);font-size:10px;color:var(--md-dim)">Just started</span></div>
            <div class="run-bar-bg"><div class="run-bar-fill" style="width:10%;background:var(--g-green-mid)"></div></div></div>
            <div class="run-right"><div class="run-pct" style="color:var(--g-green)">10%</div></div>
        </div>`;

    try {
        const res = await apiFetch('/orchestrate/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal, priority }),
            signal: controller.signal,
        });
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
                        activityFeed.log('✅ Workflow execution completed.', 'success', 'SYSTEM');
                        showCompletionToast(goal);
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
