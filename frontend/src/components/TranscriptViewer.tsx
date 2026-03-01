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

// Speaker colors for human participants
const SPEAKER_COLORS = [
  { color: '#0066CC', bg: 'rgba(0,102,204,0.1)',   border: 'rgba(0,102,204,0.2)'  }, // blue
  { color: '#34C759', bg: 'rgba(52,199,89,0.1)',   border: 'rgba(52,199,89,0.2)'  }, // green
  { color: '#FF9500', bg: 'rgba(255,149,0,0.1)',   border: 'rgba(255,149,0,0.2)'  }, // amber
  { color: '#FF3B30', bg: 'rgba(255,59,48,0.1)',   border: 'rgba(255,59,48,0.2)'  }, // red
  { color: '#32ADE6', bg: 'rgba(50,173,230,0.1)',  border: 'rgba(50,173,230,0.2)' }, // cyan
  { color: '#FF6B00', bg: 'rgba(255,107,0,0.1)',   border: 'rgba(255,107,0,0.2)'  }, // orange
]
const colorMap: Record<string, typeof SPEAKER_COLORS[0]> = {}
let colorIdx = 0
function accentFor(id: string) {
  if (!colorMap[id]) colorMap[id] = SPEAKER_COLORS[colorIdx++ % SPEAKER_COLORS.length]
  return colorMap[id]
}

// Trace event config
const TRACE_CFG: Record<string, { label: string; icon: string; color: string }> = {
  wake_word:    { label: 'Wake Word',   icon: '◎', color: '#FF9500' },
  tool_call:    { label: 'Tool Call',   icon: '→', color: '#6366F1' },
  tool_result:  { label: 'Tool Result', icon: '✓', color: '#34C759' },
  llm_response: { label: 'Response',   icon: '◈', color: '#64748b' },
  latency:      { label: 'Latency',    icon: '⚡', color: '#32ADE6' },
}

// GitHub tools
const GITHUB_TOOLS = new Set([
  'search_code', 'get_recent_commits', 'get_commit_diff', 'list_pull_requests',
  'search_issues', 'read_file', 'get_blame', 'create_github_issue',
  'revert_commit', 'close_pull_request',
])

export function toolIcon(toolName: string): string {
  const t = toolName.toLowerCase()

  if (GITHUB_TOOLS.has(t)) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 16 16" fill="#24292e">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
    </svg>`
  }

  if (t.startsWith('query_datadog') || t.startsWith('get_datadog')) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
      <rect width="14" height="14" rx="3" fill="#FF5733"/>
      <text x="7" y="10.5" text-anchor="middle" font-size="9" font-weight="bold" font-family="sans-serif" fill="white">D</text>
    </svg>`
  }

  if (t.startsWith('query_cloudwatch') || t.startsWith('query_ecs') || t.startsWith('query_lambda')) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
      <rect width="14" height="14" rx="3" fill="#FF9900"/>
      <text x="7" y="10.5" text-anchor="middle" font-size="8" font-weight="bold" font-family="sans-serif" fill="white">AWS</text>
    </svg>`
  }

  if (t.startsWith('query_gcp') || t.startsWith('query_gke')) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
      <rect width="14" height="14" rx="3" fill="#4285F4"/>
      <text x="7" y="10.5" text-anchor="middle" font-size="7" font-weight="bold" font-family="sans-serif" fill="white">GCP</text>
    </svg>`
  }

  if (t.startsWith('query_azure') || t.startsWith('query_aks')) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
      <rect width="14" height="14" rx="3" fill="#0078D4"/>
      <text x="7" y="10.5" text-anchor="middle" font-size="7" font-weight="bold" font-family="sans-serif" fill="white">AZ</text>
    </svg>`
  }

  if (t === 'search_runbook') {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
      <rect x="2" y="1" width="10" height="12" rx="1.5" stroke="#6E6E73" stroke-width="1.2"/>
      <line x1="4" y1="4.5" x2="10" y2="4.5" stroke="#6E6E73" stroke-width="1"/>
      <line x1="4" y1="7" x2="10" y2="7" stroke="#6E6E73" stroke-width="1"/>
      <line x1="4" y1="9.5" x2="8" y2="9.5" stroke="#6E6E73" stroke-width="1"/>
    </svg>`
  }

  if (t.startsWith('get_service')) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="2" fill="#6366F1"/>
      <circle cx="2" cy="4" r="1.5" fill="#6366F1"/>
      <circle cx="12" cy="4" r="1.5" fill="#6366F1"/>
      <circle cx="2" cy="10" r="1.5" fill="#6366F1"/>
      <circle cx="12" cy="10" r="1.5" fill="#6366F1"/>
      <line x1="7" y1="7" x2="2" y2="4" stroke="#6366F1" stroke-width="1"/>
      <line x1="7" y1="7" x2="12" y2="4" stroke="#6366F1" stroke-width="1"/>
      <line x1="7" y1="7" x2="2" y2="10" stroke="#6366F1" stroke-width="1"/>
      <line x1="7" y1="7" x2="12" y2="10" stroke="#6366F1" stroke-width="1"/>
    </svg>`
  }

  if (t === 'recall_decision') {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 2C4.5 2 2.5 3.8 2.5 6c0 1 .4 1.9 1 2.6L3 11l2.5-1c.5.2 1 .3 1.5.3 2.5 0 4.5-1.8 4.5-4S9.5 2 7 2z" stroke="#a78bfa" stroke-width="1.2" fill="rgba(167,139,250,0.15)"/>
      <circle cx="5" cy="6" r="0.7" fill="#a78bfa"/>
      <circle cx="7" cy="6" r="0.7" fill="#a78bfa"/>
      <circle cx="9" cy="6" r="0.7" fill="#a78bfa"/>
    </svg>`
  }

  // default — no SVG icon, use text char
  return ''
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

function SamBubble({ text, ts }: { text: string; ts: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '6px 0', animation: 'messageIn 0.25s ease-out' }}>
      <div style={{
        width: 28, height: 28, borderRadius: '50%', flexShrink: 0, marginTop: 2,
        background: 'linear-gradient(135deg, var(--sam-from), var(--sam-to))',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 700, color: 'white',
      }}>SA</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--sam-from)' }}>Sam</span>
          <span style={{ fontSize: 11, color: 'var(--text-4)' }}>{fmtTime(ts)}</span>
        </div>
        <div style={{
          display: 'inline-block', maxWidth: '90%',
          background: 'linear-gradient(135deg, var(--sam-from), var(--sam-to))',
          color: '#fff',
          borderRadius: '4px 16px 16px 16px',
          padding: '9px 13px',
          boxShadow: '0 2px 12px rgba(99,102,241,0.2)',
          fontSize: 13.5, lineHeight: 1.65, wordBreak: 'break-word',
        }}>
          {text}
        </div>
      </div>
    </div>
  )
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

  // llm_response is always paired with a sam transcript row — skip it to avoid duplicates
  const filteredTrace = traceRows.filter((r) => r.event_type !== 'llm_response')

  const merged: MergedItem[] = [
    ...rows.map((r): MergedItem => ({ kind: 'turn', row: r })),
    ...filteredTrace.map((r): MergedItem => ({ kind: 'event', row: r })),
  ].sort((a, b) => a.row.timestamp - b.row.timestamp)

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
    <div style={{ height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', padding: '10px 12px 12px' }}>
      {merged.map((item) => {
        if (item.kind === 'event') {
          const row = item.row

          // Trace event pill
          const cfg = TRACE_CFG[row.event_type] ?? { label: row.event_type, icon: '·', color: 'var(--text-4)' }
          const label = traceLabel(row)
          const isOpen = expandedTrace.has(row.id)
          let parsed: unknown
          try { parsed = JSON.parse(row.data) } catch { parsed = row.data }

          let toolName = ''
          if (row.event_type === 'tool_call') {
            try { toolName = JSON.parse(row.data).tool ?? '' } catch { /* ignore */ }
          }
          const iconSvg = toolName ? toolIcon(toolName) : ''

          return (
            <div key={`t-${row.id}`} style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', padding: '4px 0 4px 36px' }}>
              <div
                onClick={() => toggleTrace(row.id)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '3px 10px', borderRadius: 20,
                  background: `${cfg.color}12`, border: `1px solid ${cfg.color}30`,
                  cursor: 'pointer', fontSize: 11, color: cfg.color,
                  transition: 'opacity 0.1s',
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.opacity = '0.8' }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.opacity = '1' }}
              >
                {iconSvg ? (
                  <span style={{ display: 'flex', alignItems: 'center', width: 14, height: 14 }}
                    dangerouslySetInnerHTML={{ __html: iconSvg }} />
                ) : (
                  <span style={{ fontWeight: 600 }}>{cfg.icon}</span>
                )}
                <span style={{ fontWeight: 600 }}>{cfg.label}</span>
                {label && (
                  <span style={{ color: 'var(--text-3)', fontSize: 11, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {label}{label.length >= 60 ? '…' : ''}
                  </span>
                )}
                <span style={{ color: 'var(--text-4)', fontSize: 10 }}>{fmtTime(row.timestamp)}</span>
              </div>
              {isOpen && (
                <pre style={{
                  marginTop: 6, fontSize: 11, color: 'var(--text-3)',
                  fontFamily: 'ui-monospace, monospace',
                  whiteSpace: 'pre-wrap', wordBreak: 'break-all', lineHeight: 1.6,
                  background: 'var(--surface-2)', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '7px 10px', maxWidth: 480,
                }}>
                  {JSON.stringify(parsed, null, 2)}
                </pre>
              )}
            </div>
          )
        }

        // Speech turn — all left-aligned
        const row = item.row
        const isSam = row.speaker_id === 'sam'

        if (isSam) {
          return <SamBubble key={`s-${row.id}`} text={row.text} ts={row.timestamp} />
        }

        const a = accentFor(row.speaker_id)
        return (
          <div key={`s-${row.id}`} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '6px 0', animation: 'messageIn 0.25s ease-out' }}>
            <div style={{
              width: 28, height: 28, borderRadius: '50%', flexShrink: 0, marginTop: 2,
              background: a.bg, border: `1px solid ${a.border}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, fontWeight: 700, color: a.color,
            }}>
              {row.speaker_id.slice(0, 2).toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: a.color }}>{row.speaker_id}</span>
                <span style={{ fontSize: 11, color: 'var(--text-4)' }}>{fmtTime(row.timestamp)}</span>
              </div>
              <div style={{
                display: 'inline-block', maxWidth: '90%',
                background: 'var(--surface-2)', border: `1px solid ${a.border}`,
                borderRadius: '4px 16px 16px 16px',
                padding: '9px 13px',
                fontSize: 13.5, lineHeight: 1.65, wordBreak: 'break-word', color: 'var(--text-1)',
              }}>
                {row.text}
              </div>
            </div>
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
