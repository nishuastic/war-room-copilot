"""Self-contained HTML dashboard served inline by FastAPI.

No build step, no external JS/CSS — a single HTML page with inline styles and
scripts that connects to the SSE endpoint at /events.  Designed for a dark SRE
aesthetic with monospace fonts, speaker-colored transcript, and 4-panel layout.
"""

from __future__ import annotations

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>War Room Copilot</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d28;
    --border: #2a2d3a;
    --text: #e4e4e7;
    --muted: #71717a;
    --accent: #3b82f6;
    --green: #22c55e;
    --red: #ef4444;
    --amber: #f59e0b;
    --purple: #a855f7;
    --cyan: #06b6d4;
    --pink: #ec4899;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
    background: var(--bg);
    color: var(--text);
    font-size: 13px;
    line-height: 1.5;
    overflow: hidden;
    height: 100vh;
  }

  /* Header */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 20px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    height: 48px;
    flex-shrink: 0;
  }
  .header-left { display: flex; align-items: center; gap: 12px; }
  .logo {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: var(--text);
  }
  .logo span { color: var(--accent); }
  .status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--red);
    transition: background 0.3s;
  }
  .status-dot.connected {
    background: var(--green);
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  .status-label { color: var(--muted); font-size: 11px; }
  .header-right { display: flex; align-items: center; gap: 16px; }
  .timer {
    font-size: 14px;
    font-weight: 600;
    color: var(--amber);
    font-variant-numeric: tabular-nums;
  }
  .counter {
    font-size: 11px;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }

  /* Grid */
  .grid {
    display: grid;
    grid-template-columns: 1.2fr 0.8fr;
    grid-template-rows: 1fr 1fr;
    gap: 1px;
    background: var(--border);
    height: calc(100vh - 48px);
  }

  /* Panel */
  .panel {
    background: var(--surface);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 14px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .panel-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
  }
  .panel-badge {
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 9999px;
    background: var(--border);
    color: var(--muted);
  }
  .panel-body {
    flex: 1;
    overflow-y: auto;
    padding: 8px 14px;
  }
  .panel-body::-webkit-scrollbar { width: 4px; }
  .panel-body::-webkit-scrollbar-track { background: transparent; }
  .panel-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  /* Transcript */
  .transcript-line {
    display: flex;
    gap: 8px;
    padding: 3px 0;
    align-items: baseline;
  }
  .transcript-time {
    color: var(--muted);
    font-size: 11px;
    flex-shrink: 0;
    min-width: 52px;
  }
  .speaker-badge {
    font-size: 10px;
    font-weight: 600;
    padding: 0 6px;
    border-radius: 3px;
    flex-shrink: 0;
    line-height: 18px;
  }
  .transcript-text { color: var(--text); word-break: break-word; }

  /* Trace */
  .trace-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    font-size: 12px;
  }
  .trace-icon { flex-shrink: 0; font-size: 14px; }
  .trace-node {
    font-weight: 600;
    color: var(--cyan);
    min-width: 80px;
  }
  .trace-query {
    color: var(--muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .trace-time {
    color: var(--muted);
    font-size: 10px;
    margin-left: auto;
    flex-shrink: 0;
  }

  /* Timeline */
  .timeline-item {
    display: flex;
    gap: 8px;
    padding: 5px 0;
    border-left: 2px solid var(--border);
    padding-left: 12px;
    margin-left: 4px;
  }
  .timeline-item.transcript-type { border-left-color: var(--accent); }
  .timeline-item.finding-type { border-left-color: var(--purple); }
  .timeline-item.decision-type { border-left-color: var(--green); }
  .timeline-icon { flex-shrink: 0; font-size: 13px; }
  .timeline-text { color: var(--text); word-break: break-word; font-size: 12px; }

  /* Decisions */
  .decision-item {
    display: flex;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
    align-items: flex-start;
  }
  .decision-num {
    background: var(--green);
    color: var(--bg);
    font-weight: 700;
    font-size: 11px;
    min-width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    flex-shrink: 0;
  }
  .decision-text { color: var(--text); font-size: 13px; line-height: 1.5; }

  /* Empty state */
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--muted);
    font-size: 12px;
    text-align: center;
    padding: 20px;
    line-height: 1.8;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .grid {
      grid-template-columns: 1fr;
      grid-template-rows: repeat(4, 1fr);
    }
  }
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <div class="logo">War Room <span>Copilot</span></div>
    <div class="status-dot" id="statusDot"></div>
    <div class="status-label" id="statusLabel">Connecting...</div>
  </div>
  <div class="header-right">
    <div class="counter" id="eventCounter">0 events</div>
    <div class="timer" id="timer">00:00:00</div>
  </div>
</div>

<div class="grid">
  <!-- Transcript -->
  <div class="panel">
    <div class="panel-header">
      <div class="panel-title">Live Transcript</div>
      <div class="panel-badge" id="transcriptCount">0</div>
    </div>
    <div class="panel-body" id="transcriptBody">
      <div class="empty-state">Waiting for incident data...<br>
        Connect to a LiveKit room to begin.</div>
    </div>
  </div>

  <!-- Agent Trace -->
  <div class="panel">
    <div class="panel-header">
      <div class="panel-title">Agent Reasoning</div>
      <div class="panel-badge" id="traceCount">0</div>
    </div>
    <div class="panel-body" id="traceBody">
      <div class="empty-state">No graph traces yet.<br>Ask the agent to investigate something.</div>
    </div>
  </div>

  <!-- Timeline -->
  <div class="panel">
    <div class="panel-header">
      <div class="panel-title">Incident Timeline</div>
      <div class="panel-badge" id="timelineCount">0</div>
    </div>
    <div class="panel-body" id="timelineBody">
      <div class="empty-state">Timeline populates as the incident progresses.</div>
    </div>
  </div>

  <!-- Decisions -->
  <div class="panel">
    <div class="panel-header">
      <div class="panel-title">Decisions</div>
      <div class="panel-badge" id="decisionCount">0</div>
    </div>
    <div class="panel-body" id="decisionBody">
      <div class="empty-state">No decisions captured yet.<br>
        Decisions are detected automatically.</div>
    </div>
  </div>
</div>

<script>
(function() {
  const SPEAKER_COLORS = [
    '#3b82f6', '#22c55e', '#f59e0b', '#a855f7',
    '#ef4444', '#ec4899', '#06b6d4', '#f97316',
  ];
  const speakerMap = {};
  let speakerIdx = 0;
  let eventCount = 0;
  let transcriptCount = 0;
  let traceCount = 0;
  let timelineCount = 0;
  let decisionCount = 0;
  let timerStart = null;
  let timerInterval = null;

  function getSpeakerColor(name) {
    if (!speakerMap[name]) {
      speakerMap[name] = SPEAKER_COLORS[speakerIdx % SPEAKER_COLORS.length];
      speakerIdx++;
    }
    return speakerMap[name];
  }

  function clearEmpty(el) {
    const empty = el.querySelector('.empty-state');
    if (empty) empty.remove();
  }

  function autoScroll(el) {
    // Only auto-scroll if user is near the bottom
    const threshold = 80;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < threshold) {
      el.scrollTop = el.scrollHeight;
    }
  }

  function parseTranscriptLine(line) {
    // "[14:32:05] Alice: We're seeing 5xx errors" or "Alice: text"
    const m = line.match(/^\[(\d{2}:\d{2}:\d{2})\]\s+(.+?):\s*(.*)$/);
    if (m) return { time: m[1], speaker: m[2], text: m[3] };
    const m2 = line.match(/^(.+?):\s*(.*)$/);
    if (m2) return { time: '', speaker: m2[1], text: m2[2] };
    return { time: '', speaker: '', text: line };
  }

  function addTranscript(line) {
    const body = document.getElementById('transcriptBody');
    clearEmpty(body);
    const parsed = parseTranscriptLine(line);
    const div = document.createElement('div');
    div.className = 'transcript-line';

    if (parsed.time) {
      div.innerHTML += `<span class="transcript-time">${esc(parsed.time)}</span>`;
    }
    if (parsed.speaker) {
      const color = getSpeakerColor(parsed.speaker);
      var badge = '<span class="speaker-badge" style="background:'
        + color + '20;color:' + color + '">'
        + esc(parsed.speaker) + '</span>';
      div.innerHTML += badge;
    }
    div.innerHTML += `<span class="transcript-text">${esc(parsed.text || line)}</span>`;
    body.appendChild(div);
    autoScroll(body);
    transcriptCount++;
    document.getElementById('transcriptCount').textContent = transcriptCount;
  }

  function addTrace(data) {
    const body = document.getElementById('traceBody');
    clearEmpty(body);
    const div = document.createElement('div');
    div.className = 'trace-item';

    const node = data.node || '?';
    const query = data.query || '';
    const ts = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : '';

    div.innerHTML = `
      <span class="trace-icon">&#x2713;</span>
      <span class="trace-node">${esc(node)}</span>
      <span class="trace-query">${esc(query.substring(0, 60))}</span>
      <span class="trace-time">${esc(ts)}</span>
    `;
    body.appendChild(div);
    autoScroll(body);
    traceCount++;
    document.getElementById('traceCount').textContent = traceCount;
  }

  function addTimeline(type, data) {
    const body = document.getElementById('timelineBody');
    clearEmpty(body);
    const div = document.createElement('div');
    const icons = { transcript: '\uD83D\uDCAC', finding: '\uD83D\uDD0D', decision: '\u2696\uFE0F' };
    div.className = `timeline-item ${type}-type`;
    const text = typeof data === 'string' ? data : JSON.stringify(data);
    div.innerHTML = `
      <span class="timeline-icon">${icons[type] || '\u25CB'}</span>
      <span class="timeline-text">${esc(text.substring(0, 200))}</span>
    `;
    body.appendChild(div);
    autoScroll(body);
    timelineCount++;
    document.getElementById('timelineCount').textContent = timelineCount;
  }

  function addDecision(data) {
    const body = document.getElementById('decisionBody');
    clearEmpty(body);
    decisionCount++;
    const div = document.createElement('div');
    div.className = 'decision-item';
    div.innerHTML = `
      <span class="decision-num">${decisionCount}</span>
      <span class="decision-text">${esc(data)}</span>
    `;
    body.appendChild(div);
    autoScroll(body);
    document.getElementById('decisionCount').textContent = decisionCount;
  }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function startTimer() {
    if (timerInterval) return;
    timerStart = Date.now();
    timerInterval = setInterval(function() {
      const elapsed = Math.floor((Date.now() - timerStart) / 1000);
      const h = String(Math.floor(elapsed / 3600)).padStart(2, '0');
      const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
      const s = String(elapsed % 60).padStart(2, '0');
      document.getElementById('timer').textContent = h + ':' + m + ':' + s;
    }, 1000);
  }

  function connect() {
    const dot = document.getElementById('statusDot');
    const label = document.getElementById('statusLabel');
    const url = (window.DASHBOARD_API_URL || '') + '/events';

    const es = new EventSource(url);

    es.onopen = function() {
      dot.classList.add('connected');
      label.textContent = 'Connected';
    };

    es.onmessage = function(e) {
      try {
        const msg = JSON.parse(e.data);
        eventCount++;
        document.getElementById('eventCounter').textContent = eventCount + ' events';

        if (!timerStart) startTimer();

        switch (msg.type) {
          case 'transcript':
            addTranscript(msg.data);
            addTimeline('transcript', msg.data);
            break;
          case 'finding':
            addTimeline('finding', msg.data);
            break;
          case 'decision':
            addDecision(msg.data);
            addTimeline('decision', msg.data);
            break;
          case 'graph_trace':
            addTrace(msg.data);
            break;
          case 'error':
            console.error('SSE error:', msg.data);
            break;
        }
      } catch(err) {
        console.error('Parse error:', err);
      }
    };

    es.onerror = function() {
      dot.classList.remove('connected');
      label.textContent = 'Reconnecting...';
    };
  }

  connect();
})();
</script>
</body>
</html>
"""
