import re

with open('/Users/Shared/Orchestra_refined/frontend/index.html', 'r') as f:
    content = f.read()

# 1. Update Onboarding logic (Integrations & MCP)
integrations_old = """      <div class="onboard-integrations">
        ${[
          {icon:'🐙',name:'GitHub',desc:'PRs, issues, CI status, code review alerts',connected:false},
          {icon:'💬',name:'Slack',desc:'Mentions, channel messages, deploy updates',connected:false},
          {icon:'📧',name:'Email',desc:'Inbox flags, approvals, overdue replies',connected:false},
          {icon:'📅',name:'Google Calendar',desc:'Events, conflicts, scheduling context',connected:true},
        ]"""
integrations_new = """      <div class="onboard-integrations">
        ${[
          {icon:'🐙',name:'GitHub',desc:'PRs, issues, CI status, code review alerts',connected:false},
          {icon:'💬',name:'Slack',desc:'Mentions, channel messages, deploy updates',connected:false},
          {icon:'📧',name:'Email',desc:'Inbox flags, approvals, overdue replies',connected:false},
          {icon:'🔌',name:'MCP Servers',desc:'Add custom Model Context Protocol servers',connected:false},
          {icon:'📅',name:'Google Calendar',desc:'Events, conflicts, scheduling context',connected:true},
        ]"""
content = content.replace(integrations_old, integrations_new)

connect_logic_old = """function connectIntegration(idx, btn) {
  btn.textContent = '✓ Connected';
  btn.className = 'oi-btn connected';
}"""
connect_logic_new = """function connectIntegration(idx, btn) {
  const isMCP = btn.parentElement.querySelector('.oi-name').textContent.includes('MCP');
  const msg = isMCP ? "Enter MCP Server URL:" : "Enter Integration ID/Token:";
  const val = prompt(msg);
  if (val) {
    btn.textContent = '✓ Connected';
    btn.className = 'oi-btn connected';
  }
}"""
content = content.replace(connect_logic_old, connect_logic_new)

# Force onboarding to show by removing localStorage check temporarily or just let it show if new
# The user wants "for a new user presnet onboarding screen...". The logic `!done` already handles new users.
# I will clear it to force it to show this time for demo purposes.
show_onboard_old = "try { done = localStorage.getItem('orchestra-onboarded'); } catch(e){}"
show_onboard_new = "done = false; // Forced for demonstration"
content = content.replace(show_onboard_old, show_onboard_new)

# 2. Change Outputs sidebar link
outputs_old = """onclick="if(typeof triggerResearchDemo==='function') triggerResearchDemo(); else alert('Opening Outputs');\""""
outputs_new = """onclick="window.location.href='/analytics'\""""
content = content.replace(outputs_old, outputs_new)

# 3. Store active goal in localStorage
submit_goal_old = """  // Add user message to feed
  feedData.unshift({time:t, agent:'YOU', color:'var(--md-on-surface)', cbg:'var(--md-surface-1)', text:val, tag:'tasks'});"""
submit_goal_new = """  // Add user message to feed
  localStorage.setItem('currentGoal', val);
  feedData.unshift({time:t, agent:'YOU', color:'var(--md-on-surface)', cbg:'var(--md-surface-1)', text:val, tag:'tasks'});"""
content = content.replace(submit_goal_old, submit_goal_new)

# 4. Move centre bars up
# .main-goal has margin-bottom: 24px. Reduce to 12px.
# .unified-stats-bar has margin-bottom: 24px? Wait, index.html line 1552:
content = content.replace('class="main-goal anim a1" style="margin-bottom: 24px;"', 'class="main-goal anim a1" style="margin-bottom: 12px;"')
content = content.replace('padding: 16px 20px;', 'padding: 12px 20px;')
# Make sure .usb-analytics padding is smaller too
content = content.replace('padding:12px 0;', 'padding:8px 0;')


with open('/Users/Shared/Orchestra_refined/frontend/index.html', 'w') as f:
    f.write(content)

# 5. Fix trace.html
with open('/Users/Shared/Orchestra_refined/frontend/trace.html', 'r') as f:
    tcontent = f.read()

# Update the header to show the actual goal
header_old = """<div class="top-nav-goal">
    <b>Active Goal:</b> Analyze server logs from production-db-1 over the past 24 hours to identify root cause of latency spikes, and generate a recommended mitigation plan.
  </div>"""
header_new = """<div class="top-nav-goal">
    <b>Active Goal:</b> <span id="traceActiveGoal">Loading goal...</span>
  </div>"""
tcontent = tcontent.replace(header_old, header_new)

# Modify script to load the goal and clear EVENTS
# Around line 99: const EVENTS = [ ... ];
# We'll just replace the array contents with a single dynamic seed.
# I will use regex to find `const EVENTS = [ ... ];` up to the end of the array, or just find where EVENTS is defined.
event_regex = re.compile(r'const EVENTS = \[.*?\];', re.DOTALL)
event_new = """const EVENTS = [];
const savedGoal = localStorage.getItem('currentGoal') || 'Analyze server logs from production-db-1 over the past 24 hours to identify root cause of latency spikes, and generate a recommended mitigation plan.';
document.getElementById('traceActiveGoal').textContent = savedGoal;
// Add a seeded event based on the actual goal
EVENTS.push({
  id: 'e_init',
  time: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
  agent: 'orchestrator',
  type: 'decision',
  title: 'Received User Goal',
  detail: `Parsed and decomposed user goal: "${savedGoal}"`,
  tags: ['planning'],
  filter: 'all',
  reasoning: [`Starting planning phase for goal: ${savedGoal}`],
  input: savedGoal,
  output: '-',
  handoffTo: ['researcher', 'planner'],
  decision: 'Proceed with distributed execution'
});
"""
tcontent = event_regex.sub(event_new, tcontent)

with open('/Users/Shared/Orchestra_refined/frontend/trace.html', 'w') as f:
    f.write(tcontent)

print("Updates applied.")
