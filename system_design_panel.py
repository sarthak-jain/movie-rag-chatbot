"""Renders the System Design Panel: an EventSource client that connects
directly to the local sse_server.py process (not proxied through Streamlit).

Local dev only — see sse_server.py for why this can't reach a real backend
once deployed to a single-port host like Hugging Face Spaces.
"""

_HTML_TEMPLATE = """
<div id="panel" style="font-family: -apple-system, Segoe UI, sans-serif; font-size: 13px;
     background: #0e1117; color: #e6e6e6; border-radius: 8px; padding: 12px;">
  <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
    <span id="badge" style="padding:2px 8px; border-radius:12px; font-size:11px;
          background:#3a3a3a; color:#ccc;">Connecting…</span>
    <span style="color:#8892b0;">traces newer than the panel open aren't backfilled</span>
    <button id="clear" style="margin-left:auto; background:#262730; color:#ccc; border:1px solid #444;
            border-radius:4px; padding:2px 10px; cursor:pointer;">Clear</button>
  </div>
  <div id="log" style="max-height:420px; overflow-y:auto; display:flex; flex-direction:column; gap:8px;"></div>
</div>
<script>
const PORT = {port};
const TYPE_COLOR = {{
  INDEX_LOAD: '#26a69a', RETRIEVAL: '#40c4ff', CONTEXT_BUILD: '#ffab00',
  LLM_CALL: '#a855f7', STREAMING: '#7e57c2', RESPONSE: '#00c853', ERROR: '#ff5252',
}};
const TYPE_ICON = {{
  INDEX_LOAD: '📚', RETRIEVAL: '🔍', CONTEXT_BUILD: '📦',
  LLM_CALL: '🤖', STREAMING: '📡', RESPONSE: '✅', ERROR: '❌',
}};
const TRACE_COLOR = {{ USER_ACTION: '#4caf50', SYSTEM_EVENT: '#ff9800' }};

const badge = document.getElementById('badge');
const log = document.getElementById('log');
const traces = {{}};

document.getElementById('clear').onclick = () => {{
  log.innerHTML = '';
  for (const k in traces) delete traces[k];
}};

function traceEl(traceId, traceType, label) {{
  const color = TRACE_COLOR[traceType] || '#4caf50';
  const el = document.createElement('div');
  el.style.cssText = `border-left:3px solid ${{color}}; padding:6px 10px; background:#161a23; border-radius:4px;`;
  el.innerHTML = `<div style="color:${{color}}; font-weight:600; margin-bottom:4px;">${{label}}
    <span style="color:#666; font-weight:400; font-size:11px;"> #${{traceId}}</span></div>
    <div class="steps" style="display:flex; flex-direction:column; gap:3px;"></div>`;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}}

function stepRow(step) {{
  const color = TYPE_COLOR[step.type] || '#8892b0';
  const icon = TYPE_ICON[step.type] || '\\u25CF';
  const row = document.createElement('div');
  row.style.cssText = 'display:flex; gap:6px; align-items:baseline;';
  row.innerHTML = `<span>${{icon}}</span>
    <span style="color:${{color}}; min-width:110px;">[${{step.stepNumber}}] ${{step.name}}</span>
    <span style="color:#aaa; flex:1;">${{step.detail}}</span>
    <span style="color:#666;">${{step.durationMs}}ms</span>`;
  return row;
}}

function connect() {{
  const es = new EventSource(`http://localhost:${{PORT}}/events`);

  es.onopen = () => {{ badge.textContent = 'Connected'; badge.style.background = '#00c85333'; badge.style.color = '#00c853'; }};
  es.onerror = () => {{ badge.textContent = 'Reconnecting…'; badge.style.background = '#3a3a3a'; badge.style.color = '#ccc'; }};

  es.addEventListener('trace-start', (e) => {{
    const data = JSON.parse(e.data);
    traces[data.traceId] = traceEl(data.traceId, data.traceType, data.label);
  }});

  es.addEventListener('workflow-step', (e) => {{
    const step = JSON.parse(e.data);
    let el = traces[step.traceId];
    if (!el) {{ el = traceEl(step.traceId, step.traceType || 'USER_ACTION', step.name); traces[step.traceId] = el; }}
    el.querySelector('.steps').appendChild(stepRow(step));
    log.scrollTop = log.scrollHeight;
  }});
}}
connect();
</script>
"""


def render_html(port: int) -> str:
    return _HTML_TEMPLATE.format(port=port)
