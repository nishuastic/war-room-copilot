import { useEffect, useRef, useState } from 'react'

export interface TraceRow {
  id: number
  session_id: number
  event_type: string
  data: string
  timestamp: number
}

const EVENT_CFG: Record<string, { label: string; icon: string; color: string; bg: string; border: string }> = {
  wake_word:    { label: 'Wake Word',    icon: '◎', color: '#f59e0b', bg: 'rgba(245,158,11,0.08)',  border: 'rgba(245,158,11,0.2)'  },
  tool_call:    { label: 'Tool Call',    icon: '⟐', color: '#6366f1', bg: 'rgba(99,102,241,0.08)',  border: 'rgba(99,102,241,0.2)'  },
  tool_result:  { label: 'Tool Result',  icon: '✓', color: '#10b981', bg: 'rgba(16,185,129,0.08)',  border: 'rgba(16,185,129,0.2)'  },
  llm_response: { label: 'LLM Response', icon: '◈', color: '#8b5cf6', bg: 'rgba(139,92,246,0.08)', border: 'rgba(139,92,246,0.2)'  },
}

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function summarise(row: TraceRow): string {
  try {
    const d = JSON.parse(row.data)
    if (row.event_type === 'tool_call')    return d.tool ?? ''
    if (row.event_type === 'tool_result')  return d.tool ?? ''
    if (row.event_type === 'wake_word')    return String(d.text ?? '').slice(0, 48)
    if (row.event_type === 'llm_response') return String(d.text ?? '').slice(0, 48)
  } catch { /* ignore */ }
  return ''
}

interface Props { rows: TraceRow[] }

export function AgentTrace({ rows }: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [rows.length])

  if (rows.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: 'var(--text-4)', fontSize: 13 }}>No agent events yet…</span>
      </div>
    )
  }

  const toggle = (id: number) =>
    setExpanded((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n })

  return (
    <div style={{ height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 3, paddingTop: 8 }}>
      {rows.map((row) => {
        const cfg = EVENT_CFG[row.event_type] ?? { label: row.event_type, icon: '·', color: 'var(--text-4)', bg: 'var(--surface-2)', border: 'var(--border)' }
        const isOpen = expanded.has(row.id)
        const summary = summarise(row)
        let parsed: unknown
        try { parsed = JSON.parse(row.data) } catch { parsed = row.data }

        return (
          <div
            key={row.id}
            onClick={() => toggle(row.id)}
            style={{
              borderRadius: 8,
              border: `1px solid ${isOpen ? cfg.border : 'var(--border)'}`,
              background: isOpen ? cfg.bg : 'transparent',
              padding: '7px 10px',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { if (!isOpen) { e.currentTarget.style.background = 'var(--surface-2)'; e.currentTarget.style.borderColor = 'var(--border-2)' } }}
            onMouseLeave={(e) => { if (!isOpen) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'var(--border)' } }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              {/* Type badge */}
              <span style={{
                fontSize: 10, fontWeight: 700, color: cfg.color,
                background: cfg.bg, border: `1px solid ${cfg.border}`,
                borderRadius: 4, padding: '1px 6px', whiteSpace: 'nowrap',
                fontFamily: 'JetBrains Mono, monospace',
              }}>{cfg.icon} {cfg.label}</span>

              {/* Summary */}
              {summary && (
                <span style={{
                  fontSize: 12, color: 'var(--text-3)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
                }}>
                  {summary}{summary.length >= 48 ? '…' : ''}
                </span>
              )}

              <span style={{ fontSize: 10, color: 'var(--text-4)', fontFamily: 'JetBrains Mono, monospace', flexShrink: 0, marginLeft: 'auto' }}>
                {fmtTime(row.timestamp)}
              </span>
            </div>

            {isOpen && (
              <pre style={{
                margin: '8px 0 2px',
                fontSize: 11, color: 'var(--text-3)',
                fontFamily: 'JetBrains Mono, monospace',
                whiteSpace: 'pre-wrap', wordBreak: 'break-all', lineHeight: 1.7,
                background: 'var(--surface-2)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '8px 10px',
              }}>
                {JSON.stringify(parsed, null, 2)}
              </pre>
            )}
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
