export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  category?: string
  feedback?: 'like' | 'dislike' | null
}

export interface Session {
  id: string
  title: string
  messages: Message[]
  createdAt: string
  updatedAt: string
  isStarred?: boolean
}

export interface ToolConfig {
  webSearch: boolean
  vectorSearch: boolean
}

export interface QuickAction {
  title: string
  description: string
  icon: string
  query: string
}

export interface UserSettings {
  theme: 'light' | 'dark' | 'auto'
  fontSize: 'small' | 'medium' | 'large'
  autoSend: boolean
  enterToSend: boolean
  showTimestamp: boolean
}

export interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ApiResponse {
  content: string
  category?: string
  sources?: Source[]
}

export interface Source {
  title: string
  url: string
  type: 'web' | 'database' | 'regulation'
}