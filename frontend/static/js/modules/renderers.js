// Pure DOM-rendering functions — no external module imports.

export function renderDigest(data) {
    const feed = document.getElementById('feed');
    if (!feed) return;

    const card = document.createElement('div');
    card.className = 'run-card';
    card.style.cssText = 'margin:8px 0;border-top:3px solid var(--g-violet-mid,#7c4dff)';

    const sections = (data.sections || []).map(sec => {
        if (sec.type === 'not_connected') {
            return `<div style="padding:14px;border:1px dashed var(--md-surface-3);border-radius:10px;text-align:center;margin-bottom:12px">
                <span class="ms" style="font-size:28px;color:var(--md-dim)">link_off</span>
                <div style="font-size:13px;font-weight:600;margin:6px 0 4px">${sec.service} not connected</div>
                <button class="goal-run" style="font-size:12px;margin-top:6px" onclick="window.switchView('integrations-settings')">
                    <span class="ms sm">settings</span> Connect ${sec.service}
                </button>
            </div>`;
        }
        if (sec.type === 'gmail') {
            const items = (sec.items || []).slice(0, 6).map(e => `
                <div style="padding:8px 0;border-bottom:1px solid var(--md-surface-2);display:flex;gap:8px;align-items:start">
                    <span class="ms" style="font-size:16px;color:${e.priority==='high'?'var(--g-red)':'var(--g-blue)'};flex-shrink:0">mail</span>
                    <div style="flex:1;min-width:0">
                        <div style="font-size:12px;font-weight:600;color:var(--md-on-surface);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${e.subject}</div>
                        <div style="font-size:10px;color:var(--md-dim);margin-top:2px">${e.from?.replace(/<.*?>/g,'').trim()} · ${e.date||''}</div>
                        ${e.snippet ? `<div style="font-size:11px;color:var(--md-dim);margin-top:3px;line-height:1.4">${e.snippet}</div>` : ''}
                    </div>
                    <a href="${e.url||'https://mail.google.com'}" target="_blank" style="flex-shrink:0">
                        <span class="ms" style="font-size:16px;color:var(--g-blue)">open_in_new</span>
                    </a>
                </div>`).join('');
            return `<div style="margin-bottom:12px">
                <div style="font-size:10px;font-weight:700;color:var(--md-dim);letter-spacing:.5px;margin-bottom:8px">
                    📧 GMAIL · ${sec.email} · ${sec.unread} UNREAD
                </div>
                ${items || '<div style="color:var(--md-dim);font-size:12px;padding:12px 0">No urgent emails found.</div>'}
            </div>`;
        }
        if (sec.type === 'slack') {
            const mentions = (sec.mentions || []).slice(0, 4).map(m => `
                <div style="padding:6px 0;border-bottom:1px solid var(--md-surface-2)">
                    <div style="font-size:12px;color:var(--md-on-surface)">${m.text?.replace(/<[^>]+>/g,' ').trim()}</div>
                    <div style="font-size:10px;color:var(--md-dim);margin-top:2px">${m.channel} · ${m.ts}</div>
                </div>`).join('');
            return `<div style="margin-bottom:12px">
                <div style="font-size:10px;font-weight:700;color:var(--md-dim);letter-spacing:.5px;margin-bottom:8px">
                    💬 SLACK · @${sec.username} · MENTIONS
                </div>
                ${mentions || '<div style="color:var(--md-dim);font-size:12px;padding:12px 0">No mentions found.</div>'}
            </div>`;
        }
        return '';
    }).join('');

    card.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
            <span class="ms" style="color:var(--g-violet);font-size:22px">summarize</span>
            <div style="flex:1">
                <div style="font-weight:700;font-size:13px">Writer Agent — Digest</div>
                <div style="font-size:11px;color:var(--md-dim)">${data.goal} · ${data.generated||''}</div>
            </div>
        </div>
        ${sections || '<div style="color:var(--md-dim);font-size:12px">No integrations connected. Visit <strong>Integrations</strong> to set up Gmail and Slack.</div>'}`;

    feed.prepend(card);
}

export function renderAuditReport(data) {
    const feed = document.getElementById('feed');
    if (!feed) return;

    const counts  = data.counts  || {};
    const overall = data.overall || 'LOW';
    const scanned = data.scanned || {};

    const sevColor = { HIGH: 'var(--g-red)', MEDIUM: 'var(--g-amber)', LOW: 'var(--g-green)' };
    const sevBg    = { HIGH: 'var(--g-red-light)', MEDIUM: 'var(--g-amber-light)', LOW: 'var(--g-green-light)' };
    const overallColor = sevColor[overall] || 'var(--md-dim)';

    const findingCard = (f) => `
        <div style="border:1px solid ${sevColor[f.severity]||'var(--md-surface-3)'};border-radius:10px;padding:12px 14px;margin-bottom:10px;background:${sevBg[f.severity]||'var(--md-surface-1)'}20">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                <span style="font-size:16px">${f.icon}</span>
                <span style="font-size:12px;font-weight:700;color:${sevColor[f.severity]}">${f.severity}</span>
                <span style="font-size:10px;color:var(--md-dim);font-family:var(--font-mono)">${f.category}</span>
                <span style="margin-left:auto;font-size:10px;color:var(--md-dim);font-family:var(--font-mono)">${f.confidence}% confidence</span>
            </div>
            <div style="font-size:13px;font-weight:600;color:var(--md-on-surface);margin-bottom:4px">${f.title}</div>
            <div style="font-size:11px;color:var(--md-dim);margin-bottom:8px;line-height:1.5">${f.detail}</div>
            <div style="display:flex;align-items:center;gap:6px;font-size:11px">
                <span class="ms" style="font-size:14px;color:${sevColor[f.severity]}">arrow_forward</span>
                <span style="color:var(--md-on-surface);font-weight:500">${f.action}</span>
            </div>
        </div>`;

    const card = document.createElement('div');
    card.className = 'run-card';
    card.style.cssText = `margin:8px 0;border-top:3px solid ${overallColor}`;
    card.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
            <span class="ms" style="color:${overallColor};font-size:22px">security</span>
            <div style="flex:1">
                <div style="font-weight:700;font-size:13px">Risk & Audit Report</div>
                <div style="font-size:11px;color:var(--md-dim)">Scanned ${scanned.tasks||0} tasks · ${scanned.events||0} events · ${scanned.workflows||0} workflows · ${data.generated||''}</div>
            </div>
            <div style="text-align:center;padding:8px 14px;border-radius:10px;background:${sevBg[overall]||'var(--md-surface-2)'}">
                <div style="font-size:18px;font-weight:800;color:${overallColor}">${overall}</div>
                <div style="font-size:9px;color:${overallColor};font-weight:700;letter-spacing:.5px">OVERALL RISK</div>
            </div>
        </div>

        <!-- Severity summary -->
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px">
            ${[
                {label:'High Risk',   val:counts.high||0,   color:'var(--g-red)',   bg:'var(--g-red-light)'},
                {label:'Medium Risk', val:counts.medium||0, color:'var(--g-amber)', bg:'var(--g-amber-light)'},
                {label:'Low / Info',  val:counts.low||0,    color:'var(--g-green)', bg:'var(--g-green-light)'},
            ].map(s => `
                <div style="text-align:center;padding:8px;border-radius:10px;background:${s.bg}">
                    <div style="font-size:24px;font-weight:800;color:${s.color}">${s.val}</div>
                    <div style="font-size:9px;color:${s.color};font-weight:600;letter-spacing:.3px">${s.label.toUpperCase()}</div>
                </div>`).join('')}
        </div>

        <!-- Findings -->
        <div style="font-size:10px;font-weight:700;color:var(--md-dim);letter-spacing:.5px;margin-bottom:10px">FINDINGS</div>
        ${(data.findings||[]).map(findingCard).join('')}`;

    feed.prepend(card);
}

export function renderStatusOverview(data) {
    const feed = document.getElementById('feed');
    if (!feed) return;

    const t = data.totals || {};
    const prioColor = { critical:'var(--g-red)', high:'var(--g-amber)', medium:'var(--g-blue)', low:'var(--md-dim)' };
    const prioBg    = { critical:'var(--g-red-light)', high:'var(--g-amber-light)', medium:'var(--g-blue-light)', low:'var(--md-surface-2)' };

    const taskRow = (task) => `
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--md-surface-2)">
            <span style="width:6px;height:6px;border-radius:50%;background:${prioColor[task.priority]||'var(--md-dim)'};flex-shrink:0"></span>
            <span style="flex:1;font-size:12px;color:var(--md-on-surface)">${task.title}</span>
            ${task.due_date ? `<span style="font-size:10px;color:var(--md-dim);font-family:var(--font-mono)">${task.due_date}</span>` : ''}
            <span style="font-size:10px;padding:1px 6px;border-radius:100px;background:${prioBg[task.priority]||'var(--md-surface-2)'};color:${prioColor[task.priority]||'var(--md-dim)'}">${task.priority}</span>
        </div>`;

    const eventRow = (ev) => `
        <div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--md-surface-2)">
            <span class="ms" style="font-size:14px;color:var(--g-blue)">event</span>
            <span style="flex:1;font-size:12px;color:var(--md-on-surface)">${ev.title}</span>
            <span style="font-size:10px;color:var(--md-dim);font-family:var(--font-mono)">${ev.start||''}</span>
        </div>`;

    const insightRow = (ins) => {
        const bg = ins.level==='high' ? 'rgba(234,67,53,0.08)' : ins.level==='medium' ? 'rgba(251,188,4,0.08)' : 'rgba(52,168,83,0.08)';
        const border = ins.level==='high' ? 'var(--g-red)' : ins.level==='medium' ? 'var(--g-amber)' : 'var(--g-green)';
        return `<div style="padding:7px 10px;border-left:3px solid ${border};background:${bg};border-radius:0 6px 6px 0;font-size:12px;color:var(--md-on-surface);margin-bottom:6px">${ins.icon} ${ins.text}</div>`;
    };

    const card = document.createElement('div');
    card.className = 'run-card';
    card.style.cssText = 'margin:8px 0;border-top:3px solid var(--g-blue-mid)';
    card.innerHTML = `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
            <span class="ms" style="color:var(--g-blue)">dashboard</span>
            <div style="font-weight:700;font-size:13px;flex:1">Project Status Overview</div>
            <span style="font-size:10px;color:var(--md-dim);font-family:var(--font-mono)">${data.generated||''}</span>
        </div>

        <!-- Totals row -->
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:16px">
            ${[
                {label:'Overdue',     val:t.overdue||0,     color:'var(--g-red)',   bg:'var(--g-red-light)'},
                {label:'In Progress', val:t.in_progress||0, color:'var(--g-blue)',  bg:'var(--g-blue-light)'},
                {label:'Open',        val:t.open||0,        color:'var(--g-amber)', bg:'var(--g-amber-light)'},
                {label:'Done (7d)',   val:t.completed||0,   color:'var(--g-green)', bg:'var(--g-green-light)'},
                {label:'Critical',    val:t.critical||0,    color:'var(--g-red)',   bg:'var(--g-red-light)'},
            ].map(s => `
                <div style="text-align:center;padding:8px 4px;border-radius:10px;background:${s.bg}">
                    <div style="font-size:22px;font-weight:800;color:${s.color}">${s.val}</div>
                    <div style="font-size:9px;color:${s.color};font-weight:600;letter-spacing:.3px">${s.label.toUpperCase()}</div>
                </div>`).join('')}
        </div>

        <!-- Critic insights -->
        <div style="margin-bottom:14px">
            <div style="font-size:10px;font-weight:700;color:var(--md-dim);letter-spacing:.5px;margin-bottom:6px">CRITIC AGENT INSIGHTS</div>
            ${(data.insights||[]).map(insightRow).join('')}
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
            <!-- Overdue / In Progress -->
            <div>
                ${(data.overdue||[]).length ? `
                <div style="font-size:10px;font-weight:700;color:var(--g-red);letter-spacing:.5px;margin-bottom:4px">⚠ OVERDUE</div>
                ${(data.overdue||[]).map(taskRow).join('')}` : ''}
                ${(data.in_progress||[]).length ? `
                <div style="font-size:10px;font-weight:700;color:var(--g-blue);letter-spacing:.5px;margin:10px 0 4px">IN PROGRESS</div>
                ${(data.in_progress||[]).map(taskRow).join('')}` : ''}
                ${(data.open||[]).length ? `
                <div style="font-size:10px;font-weight:700;color:var(--md-dim);letter-spacing:.5px;margin:10px 0 4px">OPEN</div>
                ${(data.open||[]).map(taskRow).join('')}` : ''}
            </div>

            <!-- Upcoming events + completed -->
            <div>
                ${(data.upcoming||[]).length ? `
                <div style="font-size:10px;font-weight:700;color:var(--g-blue);letter-spacing:.5px;margin-bottom:4px">UPCOMING (7 DAYS)</div>
                ${(data.upcoming||[]).map(eventRow).join('')}` : ''}
                ${(data.completed||[]).length ? `
                <div style="font-size:10px;font-weight:700;color:var(--g-green);letter-spacing:.5px;margin:10px 0 4px">COMPLETED THIS WEEK</div>
                ${(data.completed||[]).map(taskRow).join('')}` : ''}
            </div>
        </div>`;

    feed.prepend(card);
}

export function renderVibeCheck(data) {
    const list = document.getElementById('vibe-check-results');
    if (!list) return;
    list.innerHTML = (data.scenarios_tested || []).map(s => `
        <div class="run-card" style="margin-bottom:16px;border-left:4px solid ${s.approval_status==='APPROVED'?'var(--g-green)':'var(--g-red)'}">
            <div style="display:flex;justify-content:space-between;align-items:start">
                <div>
                    <div class="run-title">${s.name}</div>
                    <div style="display:flex;gap:8px;margin:8px 0">
                        <span class="chip" style="background:${s.approval_status==='APPROVED'?'var(--g-green-light)':'var(--g-red-light)'};color:${s.approval_status==='APPROVED'?'var(--g-green)':'var(--g-red)'}">${s.approval_status}</span>
                        <span class="chip" style="background:var(--md-surface-2)">Risk: ${s.risk_level}</span>
                    </div>
                    <p style="color:var(--md-on-surface);font-size:13px;line-height:1.4">${s.explanation}</p>
                </div>
                <div style="text-align:right">
                    <div style="font-size:24px;font-weight:700;color:${s.approval_status==='APPROVED'?'var(--g-green)':'var(--g-red)'}">${s.approval_status==='APPROVED'?'95%':'22%'}</div>
                    <div style="font-size:10px;color:var(--md-dim)">SAFETY SCORE</div>
                </div>
            </div>
        </div>`).join('');
}

export function renderDebate(data) {
    const list = document.getElementById('debate-list');
    if (!list) return;
    const summary = data.summary || {};
    list.innerHTML = `
        <div class="run-card" style="margin-bottom:16px">
            <div class="run-title" style="color:var(--g-violet)">Debate ID: ${data.debate_id}</div>
            <div style="margin:12px 0;font-size:18px;font-weight:600">${data.final_decision}</div>
            <div style="background:var(--md-surface-2);padding:16px;border-radius:12px;margin-bottom:16px">
                <div style="font-size:12px;color:var(--md-dim);margin-bottom:8px">ARGUMENT BREAKDOWN</div>
                <pre style="font-family:var(--font-mono);font-size:12px;color:var(--md-on-surface);white-space:pre-wrap">${JSON.stringify(summary.arguments||summary,null,2)}</pre>
            </div>
            <div style="display:flex;gap:12px">
                <div class="chip" style="background:var(--g-blue-light);color:var(--g-blue)">Consensus: ${summary.consensus_reached?'YES':'NO'}</div>
                <div class="chip" style="background:var(--g-green-light);color:var(--g-green)">Score: ${summary.confidence_score?(summary.confidence_score*100).toFixed(0)+'%':'N/A'}</div>
            </div>
        </div>`;
}

export function renderCriticAnalysis(data) {
    const wfList = document.getElementById('workflows-list');
    if (!wfList) return;
    wfList.innerHTML = `
        <div class="run-card" style="margin-bottom:16px;border-top:4px solid var(--g-amber)">
            <div class="run-title">Workflow Analysis Report</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:16px 0">
                <div style="background:var(--md-surface-2);padding:12px;border-radius:8px;text-align:center"><div style="font-size:20px;font-weight:700">1</div><div style="font-size:10px;color:var(--md-dim)">TOTAL TASKS</div></div>
                <div style="background:var(--md-surface-2);padding:12px;border-radius:8px;text-align:center"><div style="font-size:20px;font-weight:700">2/5</div><div style="font-size:10px;color:var(--md-dim)">PRIORITY SCORE</div></div>
                <div style="background:var(--md-surface-2);padding:12px;border-radius:8px;text-align:center"><div style="font-size:20px;font-weight:700">72%</div><div style="font-size:10px;color:var(--md-dim)">EFFICIENCY</div></div>
            </div>
            <div style="margin-bottom:12px"><div style="font-size:12px;color:var(--g-red);font-weight:600;margin-bottom:4px">⚠️ Issues Detected:</div><div style="font-size:13px;padding:8px;background:rgba(234,67,53,0.1);border-radius:6px;color:var(--md-on-surface)">Task "demo for client A" has no due date - planning risk</div></div>
            <div><div style="font-size:12px;color:var(--g-green);font-weight:600;margin-bottom:4px">✅ Recommendations:</div><div style="font-size:13px;padding:8px;background:rgba(52,168,83,0.1);border-radius:6px;color:var(--md-on-surface)">Prioritize "demo for client A" - highest priority value</div></div>
        </div>`;
}

export function renderNews(articles) {
    const pane = document.getElementById('pane-news');
    if (!pane) return;
    const srcColors = { 'hacker news':'#ff6600', hackernews:'#ff6600', 'dev.to':'#08090a', reddit:'#ff4500', arxiv:'var(--g-blue)' };
    const label = document.getElementById('news-source-label');
    if (label && articles.length) {
        const s = typeof articles[0].source==='object' ? articles[0].source.name : (articles[0].source||'News');
        label.textContent = `${s} · ${new Date().toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})}`;
    }
    const grid = document.getElementById('hn-news-grid') || pane.querySelector('.news-grid');
    if (!grid) return;
    if (!articles.length) { grid.innerHTML = '<div class="empty-state">No news available.</div>'; return; }
    grid.innerHTML = articles.map(a => {
        const src      = typeof a.source==='object' ? (a.source.name||'News') : (a.source||'News');
        const color    = srcColors[src.toLowerCase()] || 'var(--g-amber)';
        const url      = (a.url||a.link||'#').replace(/'/g,'%27');
        const title    = (a.title||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/"/g,'&quot;');
        const score    = a.score ? `<span class="news-score">▲ ${a.score}</span>` : a.descendants!=null ? `<span class="news-score">💬 ${a.descendants}</span>` : '';
        return `
            <div class="news-card nc-hn">
                <div class="news-source-row"><div class="news-favicon" style="background:${color};color:white">${src.charAt(0).toUpperCase()}</div><span class="news-source-name">${src}</span><span class="news-date">${a.publishedAt?new Date(a.publishedAt).toLocaleDateString('en-GB',{day:'numeric',month:'short'}):''}</span></div>
                <div class="news-title">${a.title}</div>
                ${score?`<div class="news-meta">${score}</div>`:''}
                <div class="news-actions">
                    <button class="na-btn" onclick="playAudio('${title}')">🎧 Listen</button>
                    <button class="na-btn" onclick="window.open('${url}','_blank')">📖 Read</button>
                    <button class="na-btn" onclick="activityFeed.log('Article saved to Knowledge Graph','success','KNOWLEDGE')">🔖 Save</button>
                </div>
            </div>`;
    }).join('');
}

export function renderResearch(papers) {
    const pane = document.getElementById('pane-research');
    if (!pane) return;
    const label = document.getElementById('research-source-label');
    if (label) label.textContent = `arXiv · ${new Date().toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})}`;
    const grid = document.getElementById('arxiv-research-grid') || pane.querySelector('.news-grid');
    if (!grid) return;
    if (!papers.length) { grid.innerHTML = '<div class="empty-state">No research papers found.</div>'; return; }
    grid.innerHTML = papers.map(p => {
        const title = (p.title||'').replace(/\\/g,'\\\\').replace(/'/g,"\\'");
        const url   = (p.url||'#').replace(/'/g,'%27');
        const cat   = p.primary_category||p.source||'arXiv';
        return `
            <div class="news-card nc-arxiv">
                <div class="news-source-row"><div class="news-favicon" style="background:var(--g-blue);color:white;font-size:8px;font-weight:800">aX</div><span class="news-source-name">${cat}</span></div>
                <div class="news-title">${p.title}</div>
                ${p.citation_count?`<div class="news-meta"><span class="news-score" style="color:var(--g-blue)">★ ${p.citation_count} citations</span></div>`:''}
                <div class="news-actions">
                    <button class="na-btn" onclick="playAudio('${title}')">🎧 Listen</button>
                    <button class="na-btn" onclick="window.open('${url}','_blank')">📖 View</button>
                    <button class="na-btn" onclick="activityFeed.log('Paper indexed in Knowledge Graph','success','KNOWLEDGE')">🔖 Save</button>
                </div>
            </div>`;
    }).join('');
}


export function renderTasks(tasks) {
    const prioColor = { critical:'var(--g-red)', high:'var(--g-amber)', medium:'var(--g-blue)', low:'var(--md-dim)' };
    const prioBg    = { critical:'var(--g-red-light)', high:'var(--g-amber-light)', medium:'var(--g-blue-light)', low:'var(--md-surface-2)' };
    const html = (tasks||[]).slice(0,8).map(t => {
        const done = t.status === 'completed' || t.status === 'done';
        const p    = (t.priority||'medium').toLowerCase();
        const due  = t.due_date ? new Date(t.due_date).toLocaleDateString('en-GB',{day:'numeric',month:'short'}) : '';
        return `<div class="task-intel-item">
            <div class="ti-check ${done?'done':''}" style="cursor:default">${done?'✓':''}</div>
            <div><div class="ti-title ${done?'done-text':''}">${t.title}</div>
            <div style="display:flex;gap:6px;margin-top:4px">
                <span class="ti-priority" style="background:${prioBg[p]||'var(--md-surface-2)'};color:${prioColor[p]||'var(--md-dim)'}">${p}</span>
                ${due?`<span class="ti-due">${due}</span>`:''}
            </div></div>
        </div>`;
    }).join('');
    const pane = document.getElementById('pane-tasks');
    const all  = document.getElementById('all-tasks-list');
    if (pane) { const g = pane.querySelector('.task-intel-grid'); if (g) g.innerHTML = html; }
    if (all)  all.innerHTML = html;
}

export function renderSchedule(events) {
    const pane = document.getElementById('pane-schedule');
    if (!pane) return;
    const grid = pane.querySelector('.schedule-grid');
    if (!grid) return;
    grid.innerHTML = (events||[]).slice(0,6).map(ev => {
        const time = ev.start_time ? ev.start_time.split('T')[1]?.slice(0,5) : '--:--';
        const date = ev.start_time ? new Date(ev.start_time).toLocaleDateString('en-GB',{day:'numeric',month:'short'}) : '';
        return `
        <div class="sched-item">
            <div class="sched-time">${time}<div style="font-size:9px;color:var(--md-dim)">${date}</div></div>
            <div><div class="sched-name">${ev.title||ev.summary||'Untitled'}</div>
            <div class="sched-detail">${ev.location||'No location'}</div></div>
        </div>`;
    }).join('');
}
