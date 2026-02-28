import { useEffect, useState } from 'react'

interface MetricsData {
  cost_usd: number
  cost_breakdown: {
    llm_input_usd: number
    llm_output_usd: number
    tts_usd: number
  }
  carbon_g: number
  avg_latency_ms: number
  llm_calls: number
  total_input_tokens: number
  total_output_tokens: number
  elevenlabs_chars: number
  speaker_stats: Array<{
    speaker_id: string
    turns: number
    words: number
    decisions: number
  }>
}

const API = '/api'

export function BusinessMetrics({ sessionId }: { sessionId: number }) {
  const [data, setData] = useState<MetricsData | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const poll = () =>
      fetch(`${API}/sessions/${sessionId}/metrics`)
        .then((r) => r.json())
        .then(setData)
        .catch(() => setError(true))
    poll()
    const id = setInterval(poll, 10000)
    return () => clearInterval(id)
  }, [sessionId])

  if (error) return <EmptyState msg="Could not load metrics" />
  if (!data) return <EmptyState msg="Loading metrics…" />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '8px 0' }}>
      {/* Top stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <MetricCard
          label="Session Cost"
          value={`$${data.cost_usd.toFixed(4)}`}
          sub={`LLM $${(data.cost_breakdown.llm_input_usd + data.cost_breakdown.llm_output_usd).toFixed(4)} · TTS $${data.cost_breakdown.tts_usd.toFixed(4)}`}
          color="var(--accent)"
          icon="💰"
        />
        <MetricCard
          label="Carbon Footprint"
          value={`${data.carbon_g.toFixed(1)} gCO₂`}
          sub={`${data.llm_calls} LLM call${data.llm_calls !== 1 ? 's' : ''}`}
          color="#10b981"
          icon="🌱"
        />
        <MetricCard
          label="Avg Response Latency"
          value={data.avg_latency_ms > 0 ? `${Math.round(data.avg_latency_ms)} ms` : '—'}
          sub="wake-word → agent reply"
          color="#8b5cf6"
          icon="⚡"
        />
        <MetricCard
          label="Tokens Used"
          value={(data.total_input_tokens + data.total_output_tokens).toLocaleString()}
          sub={`${data.total_input_tokens.toLocaleString()} in · ${data.total_output_tokens.toLocaleString()} out`}
          color="#f59e0b"
          icon="🔢"
        />
      </div>

      {/* Speaker leaderboard */}
      {data.speaker_stats.length > 0 && (
        <div style={{
          background: 'var(--surface-2)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          overflow: 'hidden',
        }}>
          <div style={{
            padding: '7px 10px',
            borderBottom: '1px solid var(--border)',
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--text-3)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}>
            Speaker Contributions
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: 'var(--surface)' }}>
                {['Speaker', 'Turns', 'Words', 'Decisions'].map((h) => (
                  <th key={h} style={{
                    padding: '5px 10px', textAlign: h === 'Speaker' ? 'left' : 'right',
                    fontSize: 11, fontWeight: 600, color: 'var(--text-4)',
                    borderBottom: '1px solid var(--border)',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.speaker_stats
                .sort((a, b) => b.turns - a.turns)
                .map((spk, i) => (
                  <tr key={spk.speaker_id} style={{
                    background: i % 2 === 0 ? 'transparent' : 'var(--surface)',
                  }}>
                    <td style={{ padding: '5px 10px', fontWeight: 600, color: 'var(--text-2)', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>
                      {spk.speaker_id === 'sam' ? '🤖 sam' : `👤 ${spk.speaker_id}`}
                    </td>
                    <td style={{ padding: '5px 10px', textAlign: 'right', color: 'var(--text-3)' }}>{spk.turns}</td>
                    <td style={{ padding: '5px 10px', textAlign: 'right', color: 'var(--text-3)' }}>{spk.words.toLocaleString()}</td>
                    <td style={{ padding: '5px 10px', textAlign: 'right' }}>
                      {spk.decisions > 0 ? (
                        <span style={{
                          background: 'var(--green-bg)', color: 'var(--green)',
                          borderRadius: 4, padding: '1px 5px', fontSize: 11, fontWeight: 600,
                        }}>{spk.decisions}</span>
                      ) : (
                        <span style={{ color: 'var(--text-4)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function MetricCard({
  label, value, sub, color, icon,
}: {
  label: string; value: string; sub: string; color: string; icon: string
}) {
  return (
    <div style={{
      background: 'var(--surface-2)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-sm)',
      padding: '10px 12px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <span style={{ fontSize: 14 }}>{icon}</span>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, color, fontFamily: 'JetBrains Mono, monospace', lineHeight: 1.2 }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 4 }}>{sub}</div>
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
