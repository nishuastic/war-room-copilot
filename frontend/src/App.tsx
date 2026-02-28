import { useEffect, useState } from 'react'
import { TranscriptViewer } from './components/TranscriptViewer'
import { AgentTrace } from './components/AgentTrace'
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

function useDarkMode() {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('theme')
    if (saved) return saved === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])
  return [dark, setDark] as const
}

function fmtDate(ts: number) {
  return new Date(ts * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function App() {
  const [dark, setDark] = useDarkMode()
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
        height: 52,
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: 16,
        flexShrink: 0,
        boxShadow: 'var(--shadow-sm)',
      }}>

        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginRight: 4 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 7,
            background: 'linear-gradient(135deg, var(--accent) 0%, #8b5cf6 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, boxShadow: '0 2px 8px var(--accent-border)',
          }}>⚔️</div>
          <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-1)', letterSpacing: '-0.02em' }}>
            War Room Copilot
          </span>
        </div>

        <div style={{ width: 1, height: 18, background: 'var(--border)' }} />

        {/* Session picker */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Session
          </span>
          {loading ? (
            <span style={{ fontSize: 12, color: 'var(--text-4)' }}>Loading…</span>
          ) : (
            <select
              value={selectedId ?? ''}
              onChange={(e) => setSelectedId(Number(e.target.value))}
              style={{
                background: 'var(--surface-2)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '4px 24px 4px 8px',
                fontSize: 12,
                fontWeight: 500,
                color: 'var(--text-2)',
                fontFamily: 'Inter, sans-serif',
                cursor: 'pointer',
                outline: 'none',
                appearance: 'none',
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%236b7280' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
                backgroundRepeat: 'no-repeat',
                backgroundPosition: 'right 7px center',
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
        </div>

        {/* Stats pills */}
        {session && (
          <div style={{ display: 'flex', gap: 6 }}>
            <StatPill label="Turns" value={transcriptRows.length} color="var(--accent)" />
            <StatPill label="Events" value={traceRows.length} color="#8b5cf6" />
            <StatPill label="Decisions" value={decisions.length} color="var(--green)" />
          </div>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Live badge */}
        {session && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
            background: isLive ? 'var(--green-bg)' : 'var(--surface-2)',
            border: `1px solid ${isLive ? 'rgba(16,185,129,0.3)' : 'var(--border)'}`,
            color: isLive ? 'var(--green)' : 'var(--text-4)',
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: isLive ? 'var(--green)' : 'var(--text-4)',
              animation: isLive ? 'livePulse 2s ease-in-out infinite' : 'none',
            }} />
            {isLive ? 'Live' : 'Ended'}
          </div>
        )}

        {/* Theme toggle */}
        <button
          onClick={() => setDark(!dark)}
          title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          style={{
            width: 32, height: 32, borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border)',
            background: 'var(--surface-2)',
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15, color: 'var(--text-3)',
            transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--border-2)'
            e.currentTarget.style.color = 'var(--text-1)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.color = 'var(--text-3)'
          }}
        >
          {dark ? '☀️' : '🌙'}
        </button>
      </header>

      {/* ── Content ── */}
      {selectedId === null ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 10 }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: 'var(--accent-bg)', border: '1px solid var(--accent-border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22,
          }}>⚔️</div>
          <p style={{ color: 'var(--text-3)', fontSize: 14, fontWeight: 500 }}>Select a session to start monitoring</p>
          <p style={{ color: 'var(--text-4)', fontSize: 12 }}>Sessions appear automatically when the agent joins a room</p>
        </div>
      ) : (
        <div style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '1fr 320px',
          gridTemplateRows: '1fr 1fr',
          gap: 12,
          padding: 12,
          overflow: 'hidden',
        }}>
          {/* Transcript — full height left */}
          <Panel
            title="Transcript"
            count={transcriptRows.length}
            accentColor="var(--accent)"
            style={{ gridRow: '1 / 3' }}
          >
            <TranscriptViewer rows={transcriptRows} />
          </Panel>

          {/* Agent Trace — top right */}
          <Panel title="Agent Trace" count={traceRows.length} accentColor="#8b5cf6">
            <AgentTrace rows={traceRows} />
          </Panel>

          {/* Decisions — bottom right */}
          <Panel title="Decisions" count={decisions.length} accentColor="var(--green)">
            <DecisionList decisions={decisions} />
          </Panel>
        </div>
      )}

      <style>{`
        @keyframes livePulse {
          0%, 100% { opacity: 1; box-shadow: 0 0 0 0 var(--green); }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  )
}

function StatPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 5,
      background: 'var(--surface-2)',
      border: '1px solid var(--border)',
      borderRadius: 20, padding: '3px 9px',
    }}>
      <span style={{ fontSize: 12, fontWeight: 700, color }}>{value}</span>
      <span style={{ fontSize: 11, color: 'var(--text-4)', fontWeight: 500 }}>{label}</span>
    </div>
  )
}

function Panel({
  title, count, accentColor, children, style,
}: {
  title: string
  count: number
  accentColor: string
  children: React.ReactNode
  style?: React.CSSProperties
}) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      boxShadow: 'var(--shadow-sm)',
      ...style,
    }}>
      {/* Panel header */}
      <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flexShrink: 0,
        background: 'var(--surface-2)',
      }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: accentColor, flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', letterSpacing: '-0.01em' }}>
          {title}
        </span>
        <div style={{
          marginLeft: 'auto',
          fontSize: 11, fontWeight: 600, color: 'var(--text-4)',
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 4, padding: '1px 6px',
          fontFamily: 'JetBrains Mono, monospace',
        }}>
          {count}
        </div>
      </div>

      {/* Panel content */}
      <div style={{ flex: 1, overflow: 'hidden', padding: '4px 14px 14px' }}>
        {children}
      </div>
    </div>
  )
}
