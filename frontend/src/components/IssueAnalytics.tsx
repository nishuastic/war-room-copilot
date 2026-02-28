import { useEffect, useState } from 'react'

interface Analytics {
  categories: Array<{ name: string; count: number; pct: number }>
  resolution_time_s: number | null
  total_turns: number
  speaker_turns: Record<string, number>
  total_decisions: number
}

const API = '/api'

const CATEGORY_COLORS: Record<string, string> = {
  database: '#3b82f6',
  networking: '#8b5cf6',
  deployment: '#f59e0b',
  auth: '#ef4444',
  infrastructure: '#10b981',
}

function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

export function IssueAnalytics({ sessionId }: { sessionId: number }) {
  const [data, setData] = useState<Analytics | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const poll = () =>
      fetch(`${API}/sessions/${sessionId}/analytics`)
        .then((r) => r.json())
        .then(setData)
        .catch(() => setError(true))
    poll()
    const id = setInterval(poll, 15000)
    return () => clearInterval(id)
  }, [sessionId])

  if (error) return <EmptyState msg="Could not load analytics" />
  if (!data) return <EmptyState msg="Loading analytics…" />
  if (data.categories.length === 0) return <EmptyState msg="Not enough transcript data yet" />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '8px 0' }}>
      {/* Summary badges */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Badge label="Total Turns" value={data.total_turns} color="var(--accent)" />
        <Badge label="Decisions" value={data.total_decisions} color="var(--green)" />
        {data.resolution_time_s !== null && (
          <Badge label="Duration" value={fmtDuration(data.resolution_time_s)} color="#8b5cf6" isString />
        )}
      </div>

      {/* Issue category bars */}
      <div style={{
        background: 'var(--surface-2)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-sm)',
        padding: '10px 12px',
      }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>
          Issue Categories
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {data.categories.map((cat) => {
            const color = CATEGORY_COLORS[cat.name] || 'var(--accent)'
            return (
              <div key={cat.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                  <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-2)', textTransform: 'capitalize' }}>
                    {cat.name}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--text-4)', fontFamily: 'JetBrains Mono, monospace' }}>
                    {cat.count} mention{cat.count !== 1 ? 's' : ''} · {cat.pct}%
                  </span>
                </div>
                <div style={{
                  height: 6, borderRadius: 3,
                  background: 'var(--border)',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${cat.pct}%`,
                    background: color,
                    borderRadius: 3,
                    transition: 'width 0.5s ease',
                  }} />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Speaker turn breakdown */}
      {Object.keys(data.speaker_turns).length > 0 && (
        <div style={{
          background: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          padding: '10px 12px',
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Speaker Activity
          </div>
          {Object.entries(data.speaker_turns)
            .sort(([, a], [, b]) => b - a)
            .map(([spk, turns]) => {
              const pct = data.total_turns > 0 ? Math.round(turns / data.total_turns * 100) : 0
              return (
                <div key={spk} style={{ marginBottom: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-2)', fontFamily: 'JetBrains Mono, monospace' }}>{spk}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-4)' }}>{turns} turns · {pct}%</span>
                  </div>
                  <div style={{ height: 4, borderRadius: 2, background: 'var(--border)', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pct}%`, background: 'var(--accent)', borderRadius: 2 }} />
                  </div>
                </div>
              )
            })}
        </div>
      )}
    </div>
  )
}

function Badge({ label, value, color, isString }: { label: string; value: number | string; color: string; isString?: boolean }) {
  return (
    <div style={{
      background: 'var(--surface-2)',
      border: '1px solid var(--border)',
      borderRadius: 20,
      padding: '3px 10px',
      display: 'flex',
      alignItems: 'center',
      gap: 5,
    }}>
      <span style={{ fontSize: 12, fontWeight: 700, color, fontFamily: isString ? 'inherit' : 'JetBrains Mono, monospace' }}>{value}</span>
      <span style={{ fontSize: 11, color: 'var(--text-4)', fontWeight: 500 }}>{label}</span>
    </div>
  )
}

function EmptyState({ msg }: { msg: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 120, color: 'var(--text-4)', fontSize: 13 }}>
      {msg}
    </div>
  )
}
