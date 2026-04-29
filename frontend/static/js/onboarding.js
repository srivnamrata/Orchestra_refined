/* ============================================================
   ORCHESTRA ONBOARDING — drop in at end of <body>
   Shows on first visit, never again. Replay via ⌘K.
   ============================================================ */
(function() {

const CSS = `
.orch-onboard-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(8,9,12,0.75);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
  opacity: 0; pointer-events: none; transition: opacity 0.3s;
}
.orch-onboard-overlay.open { opacity: 1; pointer-events: all; }
.orch-onboard-card {
  width: min(560px, 92vw);
  background: var(--orch-surface, #fff);
  border-radius: 24px; border: 1px solid var(--orch-surface-3, #dadce0);
  box-shadow: 0 32px 80px rgba(0,0,0,0.3);
  overflow: hidden;
  transform: translateY(16px) scale(0.97);
  transition: transform 0.3s cubic-bezier(.34,1.2,.64,1);
}
.orch-onboard-overlay.open .orch-onboard-card { transform: translateY(0) scale(1); }
.orch-ob-progress { height: 3px; background: #e8eaed; position: relative; overflow: hidden; }
.orch-ob-fill {
  position: absolute; left: 0; top: 0; bottom: 0;
  background: linear-gradient(90deg, #1a73e8, #34a8eb);
  border-radius: 0 2px 2px 0; transition: width 0.5s cubic-bezier(.4,0,.2,1);
}
.orch-ob-dots { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 18px 0 0; }
.orch-ob-dot { width: 8px; height: 8px; border-radius: 50%; background: #dadce0; transition: all 0.25s; }
.orch-ob-dot.active { background: #1a73e8; width: 24px; border-radius: 4px; }
.orch-ob-dot.done { background: #1e8e3e; }
.orch-ob-body { padding: 24px 32px 20px; font-family: 'Google Sans', system-ui, sans-serif; }
.orch-ob-step-label { font-size: 10px; font-weight: 700; color: #1a73e8; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 8px; }
.orch-ob-title { font-size: 24px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 10px; }
.orch-ob-sub { font-size: 14px; color: #5f6368; line-height: 1.65; margin-bottom: 24px; }
.orch-ob-agents { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; margin-bottom: 20px; }
.orch-ob-agent { border: 1.5px solid #e8eaed; border-radius: 12px; padding: 12px; text-align: center; transition: all 0.15s; cursor: default; }
.orch-ob-agent:hover { border-color: #1a73e8; background: #e8f0fe; }
.orch-ob-agent-icon { font-size: 24px; margin-bottom: 6px; }
.orch-ob-agent-name { font-size: 12px; font-weight: 700; margin-bottom: 2px; }
.orch-ob-agent-role { font-size: 9px; color: #5f6368; }
.orch-ob-integrations { display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px; }
.orch-ob-integration { display: flex; align-items: center; gap: 12px; border: 1.5px solid #e8eaed; border-radius: 12px; padding: 12px 14px; }
.orch-ob-int-icon { font-size: 20px; flex-shrink: 0; }
.orch-ob-int-name { font-size: 13px; font-weight: 600; }
.orch-ob-int-desc { font-size: 10px; color: #5f6368; margin-top: 1px; }
.orch-ob-int-btn { padding: 6px 14px; border-radius: 100px; font-size: 12px; font-weight: 700; border: none; cursor: pointer; margin-left: auto; flex-shrink: 0; transition: all 0.15s; }
.orch-ob-int-btn.connect { background: #1a73e8; color: white; }
.orch-ob-int-btn.connected { background: #e6f4ea; color: #137333; border: 1px solid rgba(19,115,51,0.2); cursor: default; }
.orch-ob-goal-box { border: 2px solid #1a73e8; border-radius: 14px; padding: 14px 16px; margin-bottom: 16px; background: #e8f0fe; }
.orch-ob-goal-input { width: 100%; background: none; border: none; outline: none; font-size: 14px; color: #202124; resize: none; height: 48px; line-height: 1.6; font-family: inherit; }
.orch-ob-goal-input::placeholder { color: #9aa0a6; }
.orch-ob-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.orch-ob-chip { font-size: 11px; padding: 4px 11px; border-radius: 100px; border: 1px solid rgba(26,115,232,0.3); background: white; color: #1a73e8; cursor: pointer; font-weight: 500; transition: all 0.12s; }
.orch-ob-chip:hover { background: #1a73e8; color: white; }
.orch-ob-footer { display: flex; align-items: center; justify-content: space-between; padding: 16px 32px 24px; border-top: 1px solid #e8eaed; }
.orch-ob-skip { font-size: 11px; color: #9aa0a6; background: none; border: none; cursor: pointer; }
.orch-ob-skip:hover { color: #5f6368; }
.orch-ob-cta { display: flex; gap: 10px; }
.orch-ob-back { padding: 10px 20px; border-radius: 100px; border: 1px solid #dadce0; background: none; font-size: 13px; font-weight: 600; color: #5f6368; cursor: pointer; font-family: inherit; }
.orch-ob-next { padding: 10px 24px; border-radius: 100px; background: #1a73e8; color: white; border: none; font-size: 13px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 7px; box-shadow: 0 2px 8px rgba(26,115,232,0.3); font-family: inherit; transition: all 0.2s; }
.orch-ob-next:hover { background: #1557b0; transform: translateY(-1px); }
.orch-ob-next.finish { background: #1e8e3e; box-shadow: 0 2px 8px rgba(30,142,62,0.3); }
`;

// Inject CSS
const style = document.createElement('style');
style.textContent = CSS;
document.head.appendChild(style);

// Build HTML
const overlay = document.createElement('div');
overlay.className = 'orch-onboard-overlay';
overlay.id = 'orchOnboardOverlay';
overlay.innerHTML = `
  <div class="orch-onboard-card">
    <div class="orch-ob-progress"><div class="orch-ob-fill" id="orchObFill" style="width:33%"></div></div>
    <div class="orch-ob-dots" id="orchObDots"></div>
    <div class="orch-ob-body" id="orchObBody"></div>
    <div class="orch-ob-footer">
      <button class="orch-ob-skip" onclick="window.orchOnboard.finish()">Skip for now</button>
      <div class="orch-ob-cta">
        <button class="orch-ob-back" id="orchObBack" style="display:none" onclick="window.orchOnboard.prev()">← Back</button>
        <button class="orch-ob-next" id="orchObNext" onclick="window.orchOnboard.next()">Continue →</button>
      </div>
    </div>
  </div>`;
document.body.appendChild(overlay);

const STEPS = [
  {
    label:'Step 1 of 3', title:'Welcome to Orchestra 🎯',
    sub:'A fleet of specialized AI agents work in parallel to complete complex goals in minutes, not hours.',
    render:()=>`
      <div class="orch-ob-agents">
        ${[['🎯','Orchestrator','Coordinates all'],['🔍','Researcher','Web & doc search'],['⚖️','Critic','Quality review'],['🛡️','Auditor','Safety & PII'],['✍️','Writer','Content drafting'],['🗂️','Planner','Task decomposer']].map(([i,n,r])=>`
          <div class="orch-ob-agent"><div class="orch-ob-agent-icon">${i}</div><div class="orch-ob-agent-name">${n}</div><div class="orch-ob-agent-role">${r}</div></div>`).join('')}
      </div>
      <div style="background:#e8f0fe;border:1px solid rgba(26,115,232,0.2);border-radius:12px;padding:12px 16px;font-size:12px;color:#1a73e8;line-height:1.7">
        💡 Just type a goal — agents plan, research, write and review automatically.
      </div>`
  },
  {
    label:'Step 2 of 3', title:'Connect your tools',
    sub:'Orchestra surfaces bottlenecks from GitHub, Slack, and Email automatically.',
    render:()=> {
      return `
      <div class="orch-ob-integrations">
        ${[['🐙','GitHub','PRs, issues, CI alerts',false],['💬','Slack','Mentions, channel messages',false],['📧','Email','Inbox flags, approvals',false],['📅','Google Calendar','Events, conflicts',true]].map(([i,n,d,c],idx)=>`
          <div class="orch-ob-integration">
            <div class="orch-ob-int-icon">${i}</div>
            <div><div class="orch-ob-int-name">${n}</div><div class="orch-ob-int-desc">${d}</div></div>
            <button class="orch-ob-int-btn ${c?'connected':'connect'}" onclick="this.textContent='✓ Connected';this.className='orch-ob-int-btn connected'">${c?'✓ Connected':'Connect'}</button>
          </div>`).join('')}
      </div>
      <div style="margin-top:15px; padding:12px; border:1.5px dashed #dadce0; border-radius:12px; display:flex; align-items:center; gap:10px;">
        <span style="font-size:20px">🚀</span>
        <div style="flex:1">
           <div style="font-size:12px; font-weight:700">Want to see it in action?</div>
           <div style="font-size:10px; color:#5f6368">Load sample tasks and events to populate your dashboard.</div>
        </div>
        <button class="orch-ob-int-btn connect" id="seedDemoBtn" onclick="window.orchOnboard.seedData(this)">Load Demo</button>
      </div>`;}
  },
  {
    label:'Step 3 of 3', title:'Set your first goal',
    sub:'Tell the Orchestrator what you want to accomplish. Be specific — agents work better with detail.',
    render:()=>`
      <div class="orch-ob-goal-box">
        <textarea class="orch-ob-goal-input" id="orchObGoalInput" placeholder="e.g. Research competitors and draft a Q3 strategy brief…"></textarea>
      </div>
      <div class="orch-ob-chips">
        <span style="font-size:10px;color:#9aa0a6">Try:</span>
        ${['Research AI trends','Plan my week','Summarise today\'s news','Review PR #42'].map(t=>`<div class="orch-ob-chip" onclick="document.getElementById('orchObGoalInput').value='${t}'">${t}</div>`).join('')}
      </div>`
  }
];

window.onboardStep = 0;

function render() {
  const s = STEPS[window.onboardStep];
  document.getElementById('orchObFill').style.width = ((window.onboardStep+1)/STEPS.length*100)+'%';
  document.getElementById('orchObDots').innerHTML = STEPS.map((_,i)=>`<div class="orch-ob-dot ${i<window.onboardStep?'done':''} ${i===window.onboardStep?'active':''}"></div>`).join('');
  document.getElementById('orchObBody').innerHTML = `<div class="orch-ob-step-label">${s.label}</div><div class="orch-ob-title">${s.title}</div><div class="orch-ob-sub">${s.sub}</div>${s.render()}`;
  const back = document.getElementById('orchObBack');
  const next = document.getElementById('orchObNext');
  back.style.display = window.onboardStep > 0 ? '' : 'none';
  const isLast = window.onboardStep === STEPS.length - 1;
  next.textContent = isLast ? '✓ Get started' : 'Continue →';
  next.className = 'orch-ob-next' + (isLast ? ' finish' : '');
}

window.orchOnboard = {
  open() {
    window.onboardStep = 0;
    render();
    document.getElementById('orchOnboardOverlay').classList.add('open');
  },
  next() {
    if(window.onboardStep === STEPS.length-1) { this.finish(); return; }
    window.onboardStep++;
    render();
  },
  prev() {
    if(window.onboardStep > 0) { window.onboardStep--; render(); }
  },
  async seedData(btn) {
    btn.disabled = true;
    btn.textContent = 'Loading...';
    try {
      const res = await (window.apiFetch || fetch)('/seed-demo', { method: 'POST' });
      if (res.ok) {
        btn.textContent = '✓ Loaded';
        btn.className = 'orch-ob-int-btn connected';
      } else {
        throw new Error(`HTTP Error: ${res.status}`);
      }
    } catch (e) {
      btn.textContent = 'Error';
      btn.disabled = false;
    }
  },
  finish() {
    const goalEl = document.getElementById('orchObGoalInput');
    if(goalEl && goalEl.value.trim()) {
      // Pre-fill the main goal input — adjust selector to match yours
      const mainInput = document.querySelector('#nl-goal-input, #goal-input, .goal-input, textarea[name="goal"]');
      if(mainInput) mainInput.value = goalEl.value.trim();
    }
    // Trigger a proactive scan immediately so the "Thought Trace" is active
    if (window.runScan) {
      console.log("Onboarding complete: Triggering initial scan...");
      window.runScan();
    }
    document.getElementById('orchOnboardOverlay').classList.remove('open');
    try { sessionStorage.setItem('orch-onboarded','true'); } catch(e){}
  }
};

// Show on first visit
let done; try { done = sessionStorage.getItem('orch-onboarded'); } catch(e){}
if(!done) setTimeout(() => window.orchOnboard.open(), 800);

// Restart tour — callable from Ctrl+K palette or anywhere
window.restartTour = function() {
  try { sessionStorage.removeItem('orch-onboarded'); } catch(e){}
  window.orchOnboard.open();
};

})();
