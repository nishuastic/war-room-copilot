import { useEffect, useRef, useState } from 'react'

export function useSSE<T>(url: string | null): T[] {
  const [items, setItems] = useState<T[]>([])
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!url) return
    setItems([])

    const es = new EventSource(url)
    esRef.current = es

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

  return items
}
