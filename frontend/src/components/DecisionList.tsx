export interface DecisionRow {
  id: string
  text: string
  speaker_id: string
  timestamp: number
  confidence: number
  context: string
}

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function confColor(c: number) {
  if (c >= 0.85) return 'var(--green)'
  if (c >= 0.65) return 'var(--yellow)'
  return 'var(--red)'
}

function confBg(c: number) {
  if (c >= 0.85) return 'rgba(16,185,129,0.1)'
  if (c >= 0.65) return 'rgba(245,158,11,0.1)'
  return 'rgba(239,68,68,0.1)'
}

interface Props { decisions: DecisionRow[] }

export function DecisionList({ decisions }: Props) {
  if (decisions.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: 'var(--text-4)', fontSize: 13 }}>No decisions captured yet…</span>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 8 }}>
      {decisions.map((d) => {
        const pct = Math.round(d.confidence * 100)
        const color = confColor(d.confidence)
        return (
          <div
            key={d.id}
            style={{
              borderRadius: 'var(--radius)',
              border: '1px solid var(--border)',
              borderLeft: `3px solid ${color}`,
              background: 'var(--surface)',
              padding: '12px 14px',
              boxShadow: 'var(--shadow-sm)',
              animation: 'messageIn 0.3s ease-out',
            }}
          >
            <p style={{ margin: '0 0 10px', fontSize: 13, color: 'var(--text-1)', lineHeight: 1.55, fontWeight: 500 }}>
              {d.text}
            </p>

            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{
                fontSize: 11, fontWeight: 700, color,
                background: confBg(d.confidence),
                borderRadius: 20, padding: '2px 8px',
                fontFamily: 'JetBrains Mono, monospace',
              }}>{pct}%</span>
              <span style={{
                fontSize: 10, fontWeight: 600, color: 'var(--text-3)',
                background: 'var(--surface-2)', border: '1px solid var(--border)',
                borderRadius: 4, padding: '1px 6px',
              }}>{d.speaker_id}</span>
              <span style={{ fontSize: 10, color: 'var(--text-4)', fontFamily: 'JetBrains Mono, monospace' }}>
                {fmtTime(d.timestamp)}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
