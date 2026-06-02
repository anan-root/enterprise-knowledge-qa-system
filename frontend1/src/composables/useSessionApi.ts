import type { Message } from '../types'

const API_BASE = ''

interface SessionMeta {
  session_id: string
  title: string
  created_at: string
  updated_at: string
  is_starred: boolean
  message_count: number
}

interface SessionDetail {
  session_id: string
  title: string
  messages: Message[]
  created_at: string
  updated_at: string
  is_starred: boolean
}

export function useSessionApi() {
  async function createSession(): Promise<{ session_id: string; title: string; created_at: string }> {
    const res = await fetch(`${API_BASE}/api/sessions`, { method: 'POST' })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }

  async function listSessions(): Promise<SessionMeta[]> {
    const res = await fetch(`${API_BASE}/api/sessions`)
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    return data.sessions
  }

  async function getSession(sessionId: string): Promise<SessionDetail> {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`)
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }

  async function updateSession(sessionId: string, updates: { title?: string; is_starred?: boolean }): Promise<void> {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
    if (!res.ok) throw new Error(await res.text())
  }

  async function deleteSession(sessionId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(await res.text())
  }

  async function generateTitle(sessionId: string, questions: string[]): Promise<string> {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/title`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ questions }),
    })
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    return data.title
  }

  async function saveMessages(sessionId: string, messages: Message[]): Promise<void> {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/messages`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
    })
    if (!res.ok) throw new Error(await res.text())
  }

  return { createSession, listSessions, getSession, updateSession, deleteSession, generateTitle, saveMessages }
}
