import { useEffect, useState } from 'react'
import { TranscriptViewer, toolIcon } from './components/TranscriptViewer'
import { DecisionList } from './components/DecisionList'
import { useSSE } from './hooks/useSSE'
import { useSessions, useLatestSessionId } from './hooks/useSessions'
import type { TranscriptRow } from './components/TranscriptViewer'
import type { TraceRow } from './components/AgentTrace'
import type { DecisionRow } from './components/DecisionList'

import './index.css'

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

  const transcriptRows = useSSE<TranscriptRow>(
    selectedId !== null ? `/api/sessions/${selectedId}/stream` : null
  )
  const traceRows = useSSE<TraceRow>(
    selectedId !== null ? `/api/sessions/${selectedId}/trace` : null
  )
  const decisions = useDecisions(selectedId)
  const session = sessions.find((s) => s.id === selectedId)
  const isLive = session?.ended_at === null

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>

      {/* ── Topbar ── */}
      <header style={{
        height: 40,
        background: 'rgba(255,255,255,0.85)',
        backdropFilter: 'blur(20px) saturate(1.8)',
        WebkitBackdropFilter: 'blur(20px) saturate(1.8)',
        borderBottom: '1px solid rgba(0,0,0,0.08)',
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
      </header>

      {/* ── Content ── */}
      {selectedId === null ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 10 }}>
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
          gridTemplateColumns: '62fr 38fr',
          gap: 0,
          overflow: 'hidden',
          minHeight: 0,
        }}>
          {/* Transcript column */}
          <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRight: '1px solid var(--border)' }}>
            <TranscriptViewer rows={transcriptRows} traceRows={traceRows} />
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
