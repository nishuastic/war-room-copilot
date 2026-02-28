import { useEffect, useState } from 'react'

export interface Session {
  id: number
  room_name: string
  started_at: number
  ended_at: number | null
}

const API = '/api'

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API}/sessions`)
      .then((r) => r.json())
      .then((data: Session[]) => setSessions(data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  return { sessions, loading }
}

export function useLatestSessionId() {
  const [sessionId, setSessionId] = useState<number | null>(null)

  useEffect(() => {
    fetch(`${API}/sessions/latest/id`)
      .then((r) => r.json())
      .then((data: { session_id: number | null }) => setSessionId(data.session_id))
      .catch(console.error)
  }, [])

  return sessionId
}
