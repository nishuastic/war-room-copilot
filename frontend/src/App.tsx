import { useEffect, useState } from 'react'
import { TranscriptViewer, toolIcon } from './components/TranscriptViewer'
import { DecisionList } from './components/DecisionList'
import { useSSE } from './hooks/useSSE'
import { useSessions, useLatestSessionId } from './hooks/useSessions'
import type { TranscriptRow } from './components/TranscriptViewer'
import type { TraceRow } from './components/AgentTrace'
import type { DecisionRow } from './components/DecisionList'

import './index.css'

function fmtDateLong(ts: number) {
  return new Date(ts * 1000).toLocaleString([], {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function generateMinutesHTML(
  session: { id: number; room_name: string; started_at: number; ended_at: number | null } | undefined,
  transcriptRows: TranscriptRow[],
  traceRows: TraceRow[],
  decisions: DecisionRow[],
): string {
  if (!session) return ''

  const duration = session.ended_at
    ? Math.round((session.ended_at - session.started_at) / 60) + ' min'
    : 'Ongoing'

  const speakers = [...new Set(transcriptRows.filter(r => r.speaker_id !== 'sam').map(r => r.speaker_id))]
  const toolCalls = traceRows.filter(r => r.event_type === 'tool_call').map(r => {
    try { return JSON.parse(r.data).tool ?? '' } catch { return '' }
  }).filter(Boolean)
  const uniqueTools = [...new Set(toolCalls)]

  const transcriptHtml = transcriptRows.map(r => {
    const isSam = r.speaker_id === 'sam'
    const time = new Date(r.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return `<div class="turn ${isSam ? 'sam' : 'human'}">
      <span class="speaker">${isSam ? 'Sam (AI)' : r.speaker_id}</span>
      <span class="time">${time}</span>
      <p>${r.text}</p>
    </div>`
  }).join('')

  const decisionsHtml = decisions.length > 0
    ? decisions.map(d => {
        const pct = Math.round(d.confidence * 100)
        const time = new Date(d.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        return `<div class="decision">
          <p>${d.text}</p>
          <div class="decision-meta">
            <span class="badge">${pct}% confidence</span>
            <span class="speaker-tag">${d.speaker_id}</span>
            <span class="time">${time}</span>
          </div>
        </div>`
      }).join('')
    : '<p class="empty">No decisions recorded.</p>'

  const toolsHtml = uniqueTools.length > 0
    ? uniqueTools.map(t => `<span class="tool-tag">${t.replace(/_/g, ' ')}</span>`).join('')
    : '<span class="empty">No tools used.</span>'

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Minutes — ${session.room_name}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f7; color: #1d1d1f; padding: 40px 24px; }
    .page { max-width: 760px; margin: 0 auto; }

    /* Cover */
    .cover { background: linear-gradient(135deg, #6366F1, #8B5CF6); border-radius: 16px; padding: 36px 40px; color: white; margin-bottom: 32px; }
    .cover h1 { font-size: 26px; font-weight: 700; margin-bottom: 6px; }
    .cover .subtitle { font-size: 14px; opacity: 0.8; margin-bottom: 20px; }
    .cover .meta-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; }
    .cover .meta-item label { font-size: 11px; font-weight: 600; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 3px; }
    .cover .meta-item span { font-size: 14px; font-weight: 600; }

    /* Sections */
    section { background: white; border-radius: 12px; padding: 24px 28px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
    section h2 { font-size: 13px; font-weight: 700; color: #6366F1; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 16px; }

    /* Participants */
    .participant-list { display: flex; flex-wrap: wrap; gap: 8px; }
    .participant { background: #f0f0f5; border-radius: 20px; padding: 4px 14px; font-size: 13px; font-weight: 500; }

    /* Tools */
    .tools-wrap { display: flex; flex-wrap: wrap; gap: 8px; }
    .tool-tag { background: #eef2ff; color: #4f46e5; border-radius: 20px; padding: 4px 12px; font-size: 12px; font-weight: 500; }

    /* Decisions */
    .decision { border-left: 3px solid #10b981; padding: 10px 14px; margin-bottom: 12px; background: #f9fafb; border-radius: 0 8px 8px 0; }
    .decision p { font-size: 14px; line-height: 1.55; font-weight: 500; margin-bottom: 8px; }
    .decision-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .badge { background: rgba(16,185,129,0.12); color: #059669; border-radius: 20px; padding: 2px 8px; font-size: 11px; font-weight: 700; }
    .speaker-tag { background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 4px; padding: 1px 6px; font-size: 11px; font-weight: 600; color: #374151; }
    .time { font-size: 11px; color: #9ca3af; font-variant-numeric: tabular-nums; }

    /* Transcript */
    .turn { padding: 8px 0; border-bottom: 1px solid #f3f4f6; }
    .turn:last-child { border-bottom: none; }
    .turn .speaker { font-size: 12px; font-weight: 700; margin-right: 8px; }
    .turn.sam .speaker { color: #6366F1; }
    .turn.human .speaker { color: #0066CC; }
    .turn p { font-size: 13.5px; line-height: 1.6; color: #1d1d1f; margin-top: 3px; }

    .empty { color: #9ca3af; font-size: 13px; font-style: italic; }

    /* Footer */
    .footer { text-align: center; font-size: 12px; color: #9ca3af; margin-top: 32px; }
  </style>
</head>
<body>
  <div class="page">
    <div class="cover">
      <h1>War Room Minutes</h1>
      <div class="subtitle">${session.room_name}</div>
      <div class="meta-grid">
        <div class="meta-item"><label>Started</label><span>${fmtDateLong(session.started_at)}</span></div>
        <div class="meta-item"><label>Duration</label><span>${duration}</span></div>
        <div class="meta-item"><label>Session ID</label><span>#${session.id}</span></div>
        <div class="meta-item"><label>Participants</label><span>${speakers.length + 1} (incl. Sam)</span></div>
      </div>
    </div>

    <section>
      <h2>Participants</h2>
      <div class="participant-list">
        <span class="participant" style="background:#eef2ff;color:#4f46e5">Sam (AI Copilot)</span>
        ${speakers.map(s => `<span class="participant">${s}</span>`).join('')}
      </div>
    </section>

    <section>
      <h2>Decisions Captured · ${decisions.length}</h2>
      ${decisionsHtml}
    </section>

    <section>
      <h2>Tools Used · ${uniqueTools.length}</h2>
      <div class="tools-wrap">${toolsHtml}</div>
    </section>

    <section>
      <h2>Full Transcript · ${transcriptRows.length} turns</h2>
      ${transcriptHtml || '<p class="empty">No transcript recorded.</p>'}
    </section>

    <div class="footer">Generated by War Room Copilot · ${new Date().toLocaleString()}</div>
  </div>
</body>
</html>`
}

const API = '/api'

function useDecisions(sessionId: number | null) {
  const [decisions, setDecisions] = useState<DecisionRow[]>([])
  useEffect(() => {
    if (!sessionId) return
    const poll = () =>
      fetch(`${API}/sessions/${sessionId}/decisions`)
        .then((r) => r.json())
        .then(setDecisions)
        .catch(console.error)
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [sessionId])
  return decisions
}

function fmtDate(ts: number) {
  return new Date(ts * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}



export default function App() {
  const { sessions, loading } = useSessions()
  const latestId = useLatestSessionId()
  const [selectedId, setSelectedId] = useState<number | null>(null)

  useEffect(() => {
    if (selectedId === null && latestId !== null) setSelectedId(latestId)
  }, [latestId, selectedId])

  const { items: transcriptRows, partials } = useSSE<TranscriptRow>(
    selectedId !== null ? `/api/sessions/${selectedId}/stream` : null
  )
  const { items: traceRows } = useSSE<TraceRow>(
    selectedId !== null ? `/api/sessions/${selectedId}/trace` : null
  )
  const decisions = useDecisions(selectedId)
  const session = sessions.find((s) => s.id === selectedId)
  const isLive = session?.ended_at === null

  function openMinutes() {
    const html = generateMinutesHTML(session, transcriptRows, traceRows, decisions)
    if (!html) return
    const win = window.open('', '_blank')
    if (win) { win.document.write(html); win.document.close() }
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)', padding: 12, gap: 12 }}>

      {/* ── Topbar ── */}
      <header style={{
        height: 40,
        background: 'rgba(255,255,255,0.85)',
        backdropFilter: 'blur(20px) saturate(1.8)',
        WebkitBackdropFilter: 'blur(20px) saturate(1.8)',
        border: '1px solid rgba(0,0,0,0.08)',
        borderRadius: 12,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: 10,
        flexShrink: 0,
      }}>
        {loading ? (
          <span style={{ fontSize: 12, color: 'var(--text-4)' }}>Loading…</span>
        ) : (
          <select
            value={selectedId ?? ''}
            onChange={(e) => setSelectedId(Number(e.target.value))}
            style={{
              background: 'var(--surface-2)',
              border: '1px solid var(--border)',
              borderRadius: 20,
              padding: '4px 28px 4px 12px',
              fontSize: 12,
              fontWeight: 500,
              color: 'var(--text-2)',
              fontFamily: 'Inter, sans-serif',
              cursor: 'pointer',
              outline: 'none',
              appearance: 'none',
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%236b7280' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'right 10px center',
            }}
          >
            <option value="">Select session…</option>
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                #{s.id} · {s.room_name} · {fmtDate(s.started_at)}
                {s.ended_at === null ? '  · live' : ''}
              </option>
            ))}
          </select>
        )}

        {session && (
          <span style={{
            display: 'flex', alignItems: 'center', gap: 5,
            fontSize: 11, fontWeight: 600,
            color: isLive ? 'var(--green)' : 'var(--text-4)',
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: isLive ? 'var(--green)' : 'var(--text-4)',
              display: 'inline-block',
              animation: isLive ? 'livePulse 2s ease-in-out infinite' : 'none',
            }} />
            {isLive ? 'Live' : 'Ended'}
          </span>
        )}

        {/* spacer */}
        <div style={{ flex: 1 }} />

        {session && (
          <button
            onClick={openMinutes}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              background: 'linear-gradient(135deg, #6366F1, #8B5CF6)',
              color: 'white',
              border: 'none',
              borderRadius: 20,
              padding: '5px 14px',
              fontSize: 12, fontWeight: 600,
              cursor: 'pointer',
              fontFamily: 'Inter, sans-serif',
              boxShadow: '0 2px 8px rgba(99,102,241,0.3)',
            }}
          >
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 2h7l3 3v9a1 1 0 01-1 1H3a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="white" strokeWidth="1.4" strokeLinejoin="round"/>
              <path d="M10 2v4h4M5 8h6M5 11h4" stroke="white" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
            Save Minutes
          </button>
        )}
      </header>

      {/* ── Content ── */}
      {selectedId === null ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 10, background: 'var(--surface)', borderRadius: 12, border: '1px solid var(--border)' }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: 'var(--accent-bg)', border: '1px solid var(--accent-border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="22" height="22" viewBox="0 0 26 26" fill="none">
              <rect width="26" height="26" rx="7" fill="url(#emptyGrad)" />
              <path d="M13 5L19.5 8.5V14c0 3.5-3 6.5-6.5 7.5C9.5 20.5 6.5 17.5 6.5 14V8.5L13 5z" fill="white" fillOpacity="0.92" />
              <defs>
                <linearGradient id="emptyGrad" x1="0" y1="0" x2="26" y2="26" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#6366F1" />
                  <stop offset="1" stopColor="#8B5CF6" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <p style={{ color: 'var(--text-3)', fontSize: 14, fontWeight: 500 }}>Select a session to start monitoring</p>
          <p style={{ color: 'var(--text-4)', fontSize: 12 }}>Sessions appear automatically when the agent joins a room</p>
        </div>
      ) : (
        <div style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '62fr 0fr',
          gap: 0,
          overflow: 'hidden',
          minHeight: 0,
          background: 'var(--surface)',
          borderRadius: 12,
          border: '1px solid var(--border)',
        }}>
          {/* Transcript column */}
          <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRight: '1px solid var(--border)' }}>
            <TranscriptViewer rows={transcriptRows} traceRows={traceRows} partials={partials} />
          </div>

          {/* Right column: tool calls + decisions */}
          <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <ToolCallList traceRows={traceRows} />
            <div style={{ height: 1, background: 'var(--border)', flexShrink: 0 }} />
            <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>
              <DecisionList decisions={decisions} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function toolLabel(name: string): string {
  return name.replace(/_/g, ' ')
}

function ToolCallList({ traceRows }: { traceRows: TraceRow[] }) {
  const calls = traceRows.filter((r) => r.event_type === 'tool_call')
  if (calls.length === 0) return null

  return (
    <div style={{ flexShrink: 0, maxHeight: '40%', overflow: 'auto', padding: '12px 16px 8px' }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
        Sam's Tools · {calls.length}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {calls.map((row) => {
          let name = ''
          try { name = JSON.parse(row.data).tool ?? '' } catch { /* ignore */ }
          const svg = toolIcon(name)
          return (
            <div key={row.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {svg ? (
                <span style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}
                  dangerouslySetInnerHTML={{ __html: svg }} />
              ) : (
                <span style={{ width: 14, height: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, color: '#6366F1', flexShrink: 0 }}>→</span>
              )}
              <span style={{ fontSize: 12, color: 'var(--text-2)', fontWeight: 500, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {toolLabel(name)}
              </span>
              <span style={{ fontSize: 10, color: 'var(--text-4)', flexShrink: 0 }}>{fmtTime(row.timestamp)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
