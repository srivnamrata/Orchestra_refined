import { activityFeed } from './feed.js';
import { apiFetch, apiUrl } from './api.js';

let _scanRunning = false;

export async function runScan(btn) {
    if (_scanRunning) return;
    _scanRunning = true;
    const scanBtn  = btn || document.getElementById('runScanBtn');
    if (scanBtn) { scanBtn.disabled = true; scanBtn.innerHTML = '<span class="ms sm fa-spin">radar</span> Scanning…'; }
    const traceBody = document.getElementById('live-trace-body');
    const traceIdle = document.getElementById('traceIdle');
    const scanDot   = document.getElementById('scanDot');
    const scanLabel = document.getElementById('scanLabel');
    if (traceIdle) traceIdle.style.display = 'none';
    if (scanDot)   scanDot.className = 'scan-dot running';
    if (scanLabel) scanLabel.textContent = 'Scanning…';

    const append = (agent, msg, color = '#1a73e8') => {
        if (!traceBody) return;
        const line = document.createElement('div');
        line.className = 'trace-line';
        line.innerHTML = `<span class="tl-agent" style="color:${color}">${agent}</span><span class="tl-text">${msg}</span>`;
        traceBody.appendChild(line);
        traceBody.scrollTop = traceBody.scrollHeight;
    };

    activityFeed.log('📡 Intelligence Scan initiated…', 'status', 'SYSTEM');

    try {
        await apiFetch('/agent/monitor/scan', { method: 'POST' });
        
        const es = new EventSource(apiUrl('/agent/reasoning/stream'));
        
        es.addEventListener('reasoning', (e) => {
            try {
                const data = JSON.parse(e.data);
                const colorMap = { 'orchestrator': '#1a73e8', 'critic': '#e37400', 'auditor': '#007b83', 'guru': '#b06000' };
                append((data.agent || 'SYSTEM').toUpperCase(), data.message, colorMap[data.agent] || '#1a73e8');
                activityFeed.log(data.message, 'info', (data.agent || 'SYSTEM').toUpperCase());
            } catch (err) {}
        });
        
        es.addEventListener('done', (e) => {
            es.close();
            if (scanDot)   scanDot.className = 'scan-dot idle';
            if (scanLabel) scanLabel.textContent = 'Idle';
            if (scanBtn)   { scanBtn.disabled = false; scanBtn.innerHTML = '<span class="ms sm">radar</span> Run Scan'; }
            _scanRunning = false;
        });
        
        es.addEventListener('error', (e) => {
            es.close();
            if (scanDot)   scanDot.className = 'scan-dot idle';
            if (scanLabel) scanLabel.textContent = 'Idle';
            if (scanBtn)   { scanBtn.disabled = false; scanBtn.innerHTML = '<span class="ms sm">radar</span> Run Scan'; }
            _scanRunning = false;
        });
    } catch (e) {
        if (scanDot)   scanDot.className = 'scan-dot idle';
        if (scanLabel) scanLabel.textContent = 'Idle';
        if (scanBtn)   { scanBtn.disabled = false; scanBtn.innerHTML = '<span class="ms sm">radar</span> Run Scan'; }
        _scanRunning = false;
    }
}

export function clearScan() {
    const body  = document.getElementById('live-trace-body');
    const idle  = document.getElementById('traceIdle');
    const dot   = document.getElementById('scanDot');
    const label = document.getElementById('scanLabel');
    if (body)  body.innerHTML = '';
    if (idle)  idle.style.display = '';
    if (dot)   dot.className = 'scan-dot idle';
    if (label) label.textContent = 'Idle';
}

export function switchTraceAgent(agent, btn) {
    document.querySelectorAll('.trace-tab').forEach(t => t.classList.remove('active'));
    if (btn) btn.classList.add('active');
    activityFeed.log(`Switched trace view to ${agent}`, 'info', 'SYSTEM');
}

export function dismissBn(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
}

export function reviewBn(btn, type) {
    activityFeed.log(`Reviewing ${type} bottleneck…`, 'status', type.toUpperCase());
    btn.closest('.bn-item').style.opacity = '0.5';
}

window.runScan          = runScan;
window.clearScan        = clearScan;
window.switchTraceAgent = switchTraceAgent;
window.dismissBn        = dismissBn;
window.reviewBn         = reviewBn;
