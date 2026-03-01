import { useEffect, useRef, useState } from 'react'
import type { TraceRow } from './AgentTrace'

export interface TranscriptRow {
  id: number
  session_id: number
  speaker_id: string
  text: string
  timestamp: number
  is_passive: number
}

// Speaker colors — no purple/indigo
const SPEAKER_COLORS = [
  { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)',  border: 'rgba(59,130,246,0.2)'  }, // blue
  { color: '#10b981', bg: 'rgba(16,185,129,0.1)',  border: 'rgba(16,185,129,0.2)'  }, // green
  { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.2)'  }, // amber
  { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.2)'   }, // red
  { color: '#06b6d4', bg: 'rgba(6,182,212,0.1)',   border: 'rgba(6,182,212,0.2)'   }, // cyan
  { color: '#f97316', bg: 'rgba(249,115,22,0.1)',  border: 'rgba(249,115,22,0.2)'  }, // orange
]
const colorMap: Record<string, typeof SPEAKER_COLORS[0]> = {}
let colorIdx = 0
function accentFor(id: string) {
  if (!colorMap[id]) colorMap[id] = SPEAKER_COLORS[colorIdx++ % SPEAKER_COLORS.length]
  return colorMap[id]
}

// Trace event config — no purple
const TRACE_CFG: Record<string, { label: string; icon: string; color: string }> = {
  wake_word:    { label: 'Wake Word',   icon: '◎', color: '#f59e0b' },
  tool_call:    { label: 'Tool Call',   icon: '→', color: '#3b82f6' },
  tool_result:  { label: 'Tool Result', icon: '✓', color: '#10b981' },
  llm_response: { label: 'Response',   icon: '◈', color: '#64748b' },
  latency:      { label: 'Latency',    icon: '⚡', color: '#14b8a6' },
}

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function traceLabel(row: TraceRow): string {
  try {
    const d = JSON.parse(row.data)
    if (row.event_type === 'tool_call')    return d.tool ?? ''
    if (row.event_type === 'tool_result')  return d.tool ?? ''
    if (row.event_type === 'wake_word')    return String(d.text ?? '').slice(0, 60)
    if (row.event_type === 'latency')      return `${d.ms} ms`
    if (row.event_type === 'llm_response') return String(d.text ?? '').slice(0, 60)
  } catch { /* ignore */ }
  return ''
}

interface Props {
  rows: TranscriptRow[]
  traceRows?: TraceRow[]
}

type MergedItem =
  | { kind: 'turn'; row: TranscriptRow }
  | { kind: 'event'; row: TraceRow }

export function TranscriptViewer({ rows, traceRows = [] }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [expandedTrace, setExpandedTrace] = useState<Set<number>>(new Set())

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [rows.length, traceRows.length])

  // Merge and sort by timestamp
  // Filter out llm_response — those are already in transcript as sam's rows
  const filteredTrace = traceRows.filter((r) => r.event_type !== 'llm_response')
  const merged: MergedItem[] = [
    ...rows.map((r): MergedItem => ({ kind: 'turn', row: r })),
    ...filteredTrace.map((r): MergedItem => ({ kind: 'event', row: r })),
  ].sort((a, b) => {
    const ta = a.kind === 'turn' ? a.row.timestamp : a.row.timestamp
    const tb = b.kind === 'turn' ? b.row.timestamp : b.row.timestamp
    return ta - tb
  })

  if (merged.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: 'var(--text-4)', fontSize: 13 }}>Waiting for transcript…</span>
      </div>
    )
  }

  const toggleTrace = (id: number) =>
    setExpandedTrace((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })

  return (
    <div style={{ height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 2, paddingTop: 10 }}>
      {merged.map((item) => {
        if (item.kind === 'event') {
          const row = item.row
          const cfg = TRACE_CFG[row.event_type] ?? { label: row.event_type, icon: '·', color: 'var(--text-4)' }
          const label = traceLabel(row)
          const isOpen = expandedTrace.has(row.id)
          let parsed: unknown
          try { parsed = JSON.parse(row.data) } catch { parsed = row.data }

          return (
            <div
              key={`t-${row.id}`}
              onClick={() => toggleTrace(row.id)}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '5px 6px',
                borderRadius: 6,
                cursor: 'pointer',
                opacity: 0.75,
                transition: 'opacity 0.1s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.background = 'var(--surface-2)' }}
              onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.75'; e.currentTarget.style.background = 'transparent' }}
            >
              {/* Timeline line + dot */}
              <div style={{ width: 30, flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 4 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: cfg.color, flexShrink: 0 }} />
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 600, color: cfg.color,
                    background: `${cfg.color}15`,
                    border: `1px solid ${cfg.color}30`,
                    borderRadius: 4, padding: '1px 6px', whiteSpace: 'nowrap',
                  }}>{cfg.icon} {cfg.label}</span>
                  {label && (
                    <span style={{ fontSize: 12, color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {label}{label.length >= 60 ? '…' : ''}
                    </span>
                  )}
                  <span style={{ fontSize: 10, color: 'var(--text-4)', marginLeft: 'auto', flexShrink: 0 }}>
                    {fmtTime(row.timestamp)}
                  </span>
                </div>
                {isOpen && (
                  <pre style={{
                    marginTop: 6, fontSize: 11, color: 'var(--text-3)',
                    fontFamily: 'ui-monospace, monospace',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-all', lineHeight: 1.6,
                    background: 'var(--surface-2)', border: '1px solid var(--border)',
                    borderRadius: 6, padding: '7px 10px',
                  }}>
                    {JSON.stringify(parsed, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )
        }

        // Speech turn
        const row = item.row
        const a = accentFor(row.speaker_id)
        const isAgent = row.speaker_id === 'sam'

        return (
          <div
            key={`s-${row.id}`}
            style={{
              display: 'flex',
              gap: 10,
              padding: '8px 6px',
              borderRadius: 8,
              opacity: row.is_passive ? 0.45 : 1,
              background: isAgent ? 'var(--accent-bg)' : 'transparent',
              transition: 'background 0.1s',
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
              {row.speaker_id.slice(0, 2).toUpperCase()}
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
                <span style={{ fontSize: 10, color: 'var(--text-4)' }}>
                  {fmtTime(row.timestamp)}
                </span>
                {Boolean(row.is_passive) && (
                  <span style={{
                    fontSize: 9, color: 'var(--text-4)',
                    background: 'var(--surface-2)', border: '1px solid var(--border)',
                    borderRadius: 3, padding: '0 4px',
                  }}>passive</span>
                )}
              </div>
              <p style={{ margin: 0, fontSize: 13.5, color: 'var(--text-2)', lineHeight: 1.65, wordBreak: 'break-word' }}>
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
