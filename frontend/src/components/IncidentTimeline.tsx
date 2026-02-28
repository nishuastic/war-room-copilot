import type { TranscriptRow } from './TranscriptViewer'
import type { TraceRow } from './AgentTrace'
import type { DecisionRow } from './DecisionList'

type TimelineEvent =
  | { kind: 'transcript'; row: TranscriptRow }
  | { kind: 'trace'; row: TraceRow }
  | { kind: 'decision'; row: DecisionRow }

function getTimestamp(e: TimelineEvent): number {
  return e.kind === 'decision' ? e.row.timestamp : e.row.timestamp
}

function fmtTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const TRACE_ICONS: Record<string, string> = {
  wake_word: '🔔', tool_call: '🔧', tool_result: '✅', llm_response: '🤖',
}

interface Props {
  transcript: TranscriptRow[]
  trace: TraceRow[]
  decisions: DecisionRow[]
}

export function IncidentTimeline({ transcript, trace, decisions }: Props) {
  const events: TimelineEvent[] = [
    ...transcript.map((row) => ({ kind: 'transcript' as const, row })),
    ...trace.map((row) => ({ kind: 'trace' as const, row })),
    ...decisions.map((row) => ({ kind: 'decision' as const, row })),
  ].sort((a, b) => getTimestamp(a) - getTimestamp(b))

  return (
    <div className="flex flex-col gap-1 overflow-y-auto h-full pr-1">
      {events.length === 0 && (
        <p className="text-slate-500 text-sm italic">Timeline will appear here…</p>
      )}
      {events.map((e, i) => (
        <div key={i} className="flex gap-3 items-start text-xs">
          <span className="text-slate-500 w-20 shrink-0">{fmtTime(getTimestamp(e))}</span>
          {e.kind === 'transcript' && (
            <span className="text-slate-300">
              <span className="text-sky-400 font-semibold mr-1">{e.row.speaker_id}</span>
              {e.row.text.slice(0, 80)}{e.row.text.length > 80 ? '…' : ''}
            </span>
          )}
          {e.kind === 'trace' && (
            <span className="text-slate-400">
              {TRACE_ICONS[e.row.event_type] ?? '•'} {e.row.event_type.replace('_', ' ')}
              {e.row.event_type === 'tool_call' && (() => {
                try { const d = JSON.parse(e.row.data); return ` → ${d.tool}` } catch { return '' }
              })()}
            </span>
          )}
          {e.kind === 'decision' && (
            <span className="text-emerald-400">
              ⚖️ {e.row.text.slice(0, 80)}{e.row.text.length > 80 ? '…' : ''}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
