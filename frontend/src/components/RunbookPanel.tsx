import { useEffect, useState } from 'react'

interface Runbook {
  id: string
  title: string
  keywords: string[]
  steps: string[]
  score: number
  relevance_pct: number
}

const API = '/api'

export function RunbookPanel({ sessionId }: { sessionId: number }) {
  const [runbooks, setRunbooks] = useState<Runbook[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetch(`${API}/sessions/${sessionId}/runbooks`)
      .then((r) => r.json())
      .then((data) => {
        setRunbooks(data)
        setLoading(false)
      })
      .catch(() => {
        setError(true)
        setLoading(false)
      })
  }, [sessionId])

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (loading) return <EmptyState msg="Matching runbooks…" />
  if (error) return <EmptyState msg="Could not load runbooks" />
  if (runbooks.length === 0) return <EmptyState msg="No runbooks matched transcript keywords yet" />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '8px 0' }}>
      <div style={{ fontSize: 11, color: 'var(--text-4)', marginBottom: 2 }}>
        Top {runbooks.length} runbook{runbooks.length !== 1 ? 's' : ''} matched from transcript keywords
      </div>
      {runbooks.map((rb) => {
        const isOpen = expanded.has(rb.id)
        return (
          <div key={rb.id} style={{
            background: 'var(--surface-2)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
          }}>
            <button
              onClick={() => toggle(rb.id)}
              style={{
                width: '100%',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: '10px 12px',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                textAlign: 'left',
              }}
            >
              <span style={{ fontSize: 14 }}>📋</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-1)', marginBottom: 2 }}>
                  {rb.title}
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {rb.keywords.slice(0, 4).map((kw) => (
                    <span key={kw} style={{
                      fontSize: 10, color: 'var(--text-4)',
                      background: 'var(--surface)', border: '1px solid var(--border)',
                      borderRadius: 3, padding: '1px 5px',
                    }}>{kw}</span>
                  ))}
                </div>
              </div>
              <RelevanceBadge pct={rb.relevance_pct} />
              <span style={{ fontSize: 11, color: 'var(--text-4)', flexShrink: 0 }}>
                {isOpen ? '▲' : '▼'}
              </span>
            </button>

            {isOpen && (
              <div style={{
                borderTop: '1px solid var(--border)',
                padding: '10px 12px',
              }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                  Steps
                </div>
                <ol style={{ margin: 0, padding: '0 0 0 18px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {rb.steps.map((step, i) => (
                    <li key={i} style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.5 }}>
                      <code style={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: 11,
                        background: 'var(--surface)',
                        border: '1px solid var(--border)',
                        borderRadius: 3,
                        padding: '1px 4px',
                        color: 'var(--accent)',
                      }}>
                        {step.match(/`[^`]+`|[A-Z_]+=[^\s]+|kubectl [^\n]+|SELECT [^\n]+|redis-cli [^\n]+/)?.[0]}
                      </code>
                      {' '}{step.replace(/`[^`]+`/, '').replace(/[A-Z_]+=[^\s]+/, '').replace(/kubectl [^\n]+/, '').replace(/SELECT [^\n]+/, '').replace(/redis-cli [^\n]+/, '').trim() || step}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function RelevanceBadge({ pct }: { pct: number }) {
  const color = pct >= 60 ? 'var(--green)' : pct >= 30 ? '#f59e0b' : 'var(--text-4)'
  const bg = pct >= 60 ? 'var(--green-bg)' : pct >= 30 ? 'rgba(245,158,11,0.1)' : 'var(--surface)'
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, color,
      background: bg, border: `1px solid ${color}33`,
      borderRadius: 4, padding: '2px 6px',
      flexShrink: 0,
    }}>
      {pct}% match
    </span>
  )
}

function EmptyState({ msg }: { msg: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 120, color: 'var(--text-4)', fontSize: 13 }}>
      {msg}
    </div>
  )
}
