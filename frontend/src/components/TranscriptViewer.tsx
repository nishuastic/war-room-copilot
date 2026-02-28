import { useEffect, useRef } from 'react'

export interface TranscriptRow {
  id: number
  session_id: number
  speaker_id: string
  text: string
  timestamp: number
  is_passive: number
}

// Per-speaker accent — hue only, opacity applied via CSS vars
const ACCENTS = [
  { color: '#6366f1', bg: 'rgba(99,102,241,0.1)',  border: 'rgba(99,102,241,0.25)' },
  { color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)',  border: 'rgba(139,92,246,0.25)' },
  { color: '#10b981', bg: 'rgba(16,185,129,0.1)',  border: 'rgba(16,185,129,0.25)' },
  { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.25)' },
  { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.25)'  },
  { color: '#06b6d4', bg: 'rgba(6,182,212,0.1)',   border: 'rgba(6,182,212,0.25)'  },
]
const colorMap: Record<string, typeof ACCENTS[0]> = {}
let idx = 0
function accentFor(id: string) {
  if (!colorMap[id]) colorMap[id] = ACCENTS[idx++ % ACCENTS.length]
  return colorMap[id]
}

function initials(id: string) {
  return id.slice(0, 2).toUpperCase()
}

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

interface Props { rows: TranscriptRow[] }

export function TranscriptViewer({ rows }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [rows.length])

  if (rows.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: 'var(--text-4)', fontSize: 13 }}>Waiting for transcript…</span>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 1, paddingTop: 8 }}>
      {rows.map((row) => {
        const a = accentFor(row.speaker_id)
        const isAgent = row.speaker_id === 'sam'
        return (
          <div
            key={row.id}
            style={{
              display: 'flex',
              gap: 10,
              padding: '8px 6px',
              borderRadius: 8,
              opacity: row.is_passive ? 0.5 : 1,
              transition: 'background 0.1s',
              background: isAgent ? 'var(--accent-bg)' : 'transparent',
            }}
            onMouseEnter={(e) => { if (!isAgent) e.currentTarget.style.background = 'var(--surface-2)' }}
            onMouseLeave={(e) => { if (!isAgent) e.currentTarget.style.background = 'transparent' }}
          >
            {/* Avatar */}
            <div style={{
              width: 30, height: 30, borderRadius: 7, flexShrink: 0,
              background: a.bg, border: `1px solid ${a.border}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, fontWeight: 700, color: a.color,
              marginTop: 1,
            }}>
              {initials(row.speaker_id)}
            </div>

            {/* Content */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 3 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: a.color }}>
                  {row.speaker_id}
                </span>
                {isAgent && (
                  <span style={{
                    fontSize: 9, fontWeight: 700, color: 'var(--accent)',
                    background: 'var(--accent-bg)', border: '1px solid var(--accent-border)',
                    borderRadius: 3, padding: '0 4px', letterSpacing: '0.04em',
                  }}>AI</span>
                )}
                <span style={{ fontSize: 10, color: 'var(--text-4)', fontFamily: 'JetBrains Mono, monospace' }}>
                  {fmtTime(row.timestamp)}
                </span>
                {row.is_passive ? (
                  <span style={{
                    fontSize: 9, color: 'var(--text-4)',
                    background: 'var(--surface-2)', border: '1px solid var(--border)',
                    borderRadius: 3, padding: '0 4px',
                  }}>passive</span>
                ) : null}
              </div>
              <p style={{ margin: 0, fontSize: 13, color: 'var(--text-2)', lineHeight: 1.6, wordBreak: 'break-word' }}>
                {row.text}
              </p>
            </div>
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
