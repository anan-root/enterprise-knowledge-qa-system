<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import { useChat } from '../composables/useChat'
import Sidebar from '../components/Sidebar.vue'
import ChatHeader from '../components/ChatHeader.vue'
import ChatArea from '../components/ChatArea.vue'
import type { Message, ToolConfig, HistoryMessage } from '../types'

const route = useRoute()
const router = useRouter()
const sessionStore = useSessionStore()
const { isLoading, sendMessage, stopGenerate } = useChat()
const sidebarOpen = ref(false)

onMounted(async () => {
  await sessionStore.loadFromStorage()
  const sessionId = route.params.id as string
  if (sessionId && sessionStore.sessions.find(s => s.id === sessionId)) {
    sessionStore.setCurrentSession(sessionId)
    await sessionStore.loadSessionMessages(sessionId)
  }
})

watch(() => sessionStore.currentSessionId, (newId) => {
  if (newId && route.path !== `/session/${newId}`) {
    router.replace(`/session/${newId}`)
  }
})

async function handleSelectSession(id: string) {
  sessionStore.setCurrentSession(id)
  await sessionStore.loadSessionMessages(id)
  sidebarOpen.value = false
}

function handleNewSession() {
  const newId = sessionStore.createSession()
  router.push(`/session/${newId}`)
  sidebarOpen.value = false
}

function handleRenameSession(id: string, title: string) {
  sessionStore.updateSession(id, { title })
}

function handleClearSession() {
  if (!sessionStore.currentSession) return
  if (confirm('确定要清空当前会话的所有消息吗？')) {
    sessionStore.clearSession(sessionStore.currentSession.id)
  }
}

function handleStarSession() {
  if (sessionStore.currentSession) {
    sessionStore.toggleStar(sessionStore.currentSession.id)
  }
}

async function handleSendMessage(content: string) {
  if (!sessionStore.currentSession) return

  const userMsg: Message = {
    id: Date.now().toString(),
    role: 'user',
    content,
    timestamp: new Date().toISOString()
  }
  sessionStore.addMessage(sessionStore.currentSession.id, userMsg)

  const assistantMsgId = (Date.now() + 1).toString()
  const assistantMsg: Message = {
    id: assistantMsgId,
    role: 'assistant',
    content: '',
    category: undefined,
    timestamp: new Date().toISOString(),
    feedback: null
  }
  sessionStore.addMessage(sessionStore.currentSession.id, assistantMsg)

  // 构建对话历史（发送给后端用于问题改写）
  const allMessages = sessionStore.currentSession.messages
  const history: HistoryMessage[] = []
  for (let i = 0; i < allMessages.length - 2; i++) {
    const msg = allMessages[i]
    if (msg.role === 'user' || msg.role === 'assistant') {
      history.push({ role: msg.role, content: msg.content })
    }
  }

  try {
    await sendMessage(content, sessionStore.currentSession.id, history, (chunkContent) => {
      sessionStore.updateMessage(sessionStore.currentSession!.id, assistantMsgId, {
        content: chunkContent
      })
    })
  } catch (error) {
    sessionStore.updateMessage(sessionStore.currentSession.id, assistantMsgId, {
      content: `抱歉，处理您的请求时出现错误：${error instanceof Error ? error.message : '未知错误'}`
    })
  }
}

function handleQuickAction(text: string) {
  handleSendMessage(text, { webSearch: false, vectorSearch: false })
}

function handleCopyMessage(content: string) {
  navigator.clipboard.writeText(content)
}

async function handleRegenerateMessage(msgId: string) {
  if (!sessionStore.currentSession) return

  const messages = sessionStore.currentSession.messages
  const idx = messages.findIndex(m => m.id === msgId)
  if (idx <= 0) return

  const userMsg = messages[idx - 1]
  if (userMsg.role !== 'user') return

  sessionStore.updateSession(sessionStore.currentSession.id, {
    messages: messages.slice(0, idx)
  })

  await handleSendMessage(userMsg.content, { webSearch: false, vectorSearch: false })
}

function handleFeedback(msgId: string, type: 'like' | 'dislike') {
  if (!sessionStore.currentSession) return
  sessionStore.updateMessage(sessionStore.currentSession.id, msgId, { feedback: type })
}

function handleStopGeneration() {
  stopGenerate()
}
</script>

<template>
  <div class="chat-layout">
    <Sidebar
      :sessions="sessionStore.sessions"
      :current-session-id="sessionStore.currentSessionId"
      @select-session="handleSelectSession"
      @new-session="handleNewSession"
      @delete-session="sessionStore.deleteSession"
      @rename-session="handleRenameSession"
      @star-session="sessionStore.toggleStar"
    />

    <div class="overlay" :class="{ active: sidebarOpen }" @click="sidebarOpen = false" />

    <main class="chat-main">
      <ChatHeader
        :title="sessionStore.currentSession?.title || '新会话'"
        :has-messages="(sessionStore.currentSession?.messages.length || 0) > 0"
        @toggle-sidebar="sidebarOpen = !sidebarOpen"
        @clear-session="handleClearSession"
        @star-session="handleStarSession"
        :is-starred="sessionStore.currentSession?.isStarred || false"
      />

      <ChatArea
        :messages="sessionStore.currentSession?.messages || []"
        :is-loading="isLoading"
        @send-message="handleSendMessage"
        @quick-action="handleQuickAction"
        @copy-message="handleCopyMessage"
        @regenerate-message="handleRegenerateMessage"
        @feedback="handleFeedback"
        @stop-generation="handleStopGeneration"
      />
    </main>
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 100;
}

.overlay.active {
  display: block;
}

@media (max-width: 768px) {
  .overlay.active {
    display: block;
  }
}
</style>