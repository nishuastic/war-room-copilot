import { useEffect, useRef, useState } from 'react'

export interface PartialEntry {
  session_id: number
  speaker_id: string
  text: string
  timestamp: number
}

export interface SSEResult<T> {
  items: T[]
  partials: PartialEntry[]
}

/**
 * Subscribe to an SSE endpoint that emits named events:
 * - `event: final` — completed rows (appended to items)
 * - `event: partial` — in-progress text (replaces partials array)
 * - unnamed `data:` — backward compat (appended to items, e.g. trace endpoint)
 */
export function useSSE<T>(url: string | null): SSEResult<T> {
  const [items, setItems] = useState<T[]>([])
  const [partials, setPartials] = useState<PartialEntry[]>([])
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!url) return
    setItems([])
    setPartials([])

    const es = new EventSource(url)
    esRef.current = es

    // Named event: final transcript row
    es.addEventListener('final', (e: MessageEvent) => {
      try {
        const row = JSON.parse(e.data) as T
        setItems((prev) => [...prev, row])
        // Auto-clear partial for this speaker when final arrives
        const speakerId = (row as Record<string, unknown>).speaker_id as string | undefined
        if (speakerId) {
          setPartials((prev) => prev.filter((p) => p.speaker_id !== speakerId))
        }
      } catch {
        // ignore malformed frames
      }
    })

    // Named event: partial (in-progress) entries
    es.addEventListener('partial', (e: MessageEvent) => {
      try {
        const entries = JSON.parse(e.data) as PartialEntry[]
        setPartials(entries)
      } catch {
        // ignore malformed frames
      }
    })

    // Backward compat: unnamed messages (used by trace endpoint)
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as T
        setItems((prev) => [...prev, data])
      } catch {
        // ignore malformed frames
      }
    }

    return () => {
      es.close()
      esRef.current = null
    }
  }, [url])

  return { items, partials }
}
