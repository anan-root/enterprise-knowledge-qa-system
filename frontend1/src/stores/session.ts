import { defineStore } from 'pinia'
import type { Session, Message } from '../types'
import { useSessionApi } from '../composables/useSessionApi'

interface SessionState {
  sessions: Session[]
  currentSessionId: string | null
  _synced: boolean
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    sessions: [],
    currentSessionId: null,
    _synced: false,
  }),

  getters: {
    currentSession: (state) =>
      state.sessions.find(s => s.id === state.currentSessionId) || null,

    starredSessions: (state) =>
      state.sessions.filter(s => s.isStarred),

    recentSessions: (state) =>
      [...state.sessions]
        .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
        .slice(0, 5),
  },

  actions: {
    async loadFromStorage() {
      const api = useSessionApi()

      try {
        const metas = await api.listSessions()
        this.sessions = metas.map(m => ({
          id: m.session_id,
          title: m.title,
          messages: [],
          createdAt: m.created_at,
          updatedAt: m.updated_at,
          isStarred: m.is_starred,
        }))
        this._synced = true
      } catch {
        // Fallback: load from localStorage
        const saved = localStorage.getItem('bid_sessions')
        if (saved) {
          try { this.sessions = JSON.parse(saved) } catch { this.sessions = [] }
        }
      }

      if (this.sessions.length === 0) {
        await this.createSession()
      } else {
        const savedCurrent = localStorage.getItem('bid_current_session')
        if (savedCurrent && this.sessions.find(s => s.id === savedCurrent)) {
          this.currentSessionId = savedCurrent
        } else {
          this.currentSessionId = this.sessions[0].id
        }
      }
    },

    _saveToStorage() {
      localStorage.setItem('bid_sessions', JSON.stringify(this.sessions))
      if (this.currentSessionId) {
        localStorage.setItem('bid_current_session', this.currentSessionId)
      }
    },

    async loadSessionMessages(sessionId: string) {
      if (!this._synced) return
      const api = useSessionApi()
      try {
        const detail = await api.getSession(sessionId)
        const session = this.sessions.find(s => s.id === sessionId)
        if (session) {
          session.messages = detail.messages
          session.title = detail.title
          session.isStarred = detail.is_starred
          this._saveToStorage()
        }
      } catch {
        // keep local messages if API fails
      }
    },

    async createSession(title?: string): Promise<string> {
      const api = useSessionApi()
      let sid = ''
      let createdTitle = title || '新会话'
      let createdTime = new Date().toISOString()

      try {
        const result = await api.createSession()
        sid = result.session_id
        createdTitle = result.title
        createdTime = result.created_at
      } catch {
        sid = Date.now().toString()
      }

      const session: Session = {
        id: sid,
        title: createdTitle,
        messages: [],
        createdAt: createdTime,
        updatedAt: createdTime,
        isStarred: false,
      }
      this.sessions.unshift(session)
      this.currentSessionId = sid
      this._saveToStorage()
      return sid
    },

    async syncMessagesToBackend(sessionId: string) {
      if (!this._synced) return
      const session = this.sessions.find(s => s.id === sessionId)
      if (!session || session.messages.length === 0) return

      const api = useSessionApi()
      try {
        await api.saveMessages(sessionId, session.messages)

        // Generate title from first 1-3 user questions via LLM
        const userQuestions = session.messages
          .filter(m => m.role === 'user')
          .map(m => m.content)
          .slice(0, 3)

        if (userQuestions.length >= 1 && (session.title === '新会话' || session.messages.filter(m => m.role === 'user').length <= 3)) {
          const newTitle = await api.generateTitle(sessionId, userQuestions)
          if (newTitle && newTitle !== '新会话') {
            session.title = newTitle
            this._saveToStorage()
          }
        }
      } catch {
        // silent fail
      }
    },

    updateSession(id: string, updates: Partial<Session>) {
      const session = this.sessions.find(s => s.id === id)
      if (session) {
        Object.assign(session, updates)
        session.updatedAt = new Date().toISOString()
        this._saveToStorage()

        if (this._synced) {
          const api = useSessionApi()
          const backendUpdates: { title?: string; is_starred?: boolean } = {}
          if (updates.title !== undefined) backendUpdates.title = updates.title
          if (updates.isStarred !== undefined) backendUpdates.is_starred = updates.isStarred
          if (Object.keys(backendUpdates).length > 0) {
            api.updateSession(id, backendUpdates).catch(() => {})
          }
        }
      }
    },

    async deleteSession(id: string) {
      const index = this.sessions.findIndex(s => s.id === id)
      if (index === -1) return

      this.sessions.splice(index, 1)

      if (this.currentSessionId === id) {
        this.currentSessionId = this.sessions[0]?.id || null
        if (!this.currentSessionId) {
          await this.createSession()
        }
      }
      this._saveToStorage()

      if (this._synced) {
        const api = useSessionApi()
        api.deleteSession(id).catch(() => {})
      }
    },

    addMessage(sessionId: string, message: Message) {
      const session = this.sessions.find(s => s.id === sessionId)
      if (session) {
        session.messages.push(message)
        session.updatedAt = new Date().toISOString()

        if (session.messages.length === 1 && message.role === 'user') {
          session.title = message.content.slice(0, 30) + (message.content.length > 30 ? '...' : '')
        }
        this._saveToStorage()

        // Sync to backend after each assistant reply
        if (message.role === 'assistant' && message.content) {
          this.syncMessagesToBackend(sessionId)
        }
      }
    },

    updateMessage(sessionId: string, messageId: string, updates: Partial<Message>) {
      const session = this.sessions.find(s => s.id === sessionId)
      if (session) {
        const message = session.messages.find(m => m.id === messageId)
        if (message) {
          Object.assign(message, updates)
          this._saveToStorage()
        }
      }
    },

    clearSession(sessionId: string) {
      const session = this.sessions.find(s => s.id === sessionId)
      if (session) {
        session.messages = []
        session.title = '新会话'
        session.updatedAt = new Date().toISOString()
        this._saveToStorage()
      }
    },

    toggleStar(sessionId: string) {
      const session = this.sessions.find(s => s.id === sessionId)
      if (session) {
        session.isStarred = !session.isStarred
        this._saveToStorage()

        if (this._synced) {
          const api = useSessionApi()
          api.updateSession(sessionId, { is_starred: session.isStarred }).catch(() => {})
        }
      }
    },

    setCurrentSession(id: string) {
      this.currentSessionId = id
      this._saveToStorage()
    },
  },
})
