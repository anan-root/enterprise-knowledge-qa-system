<template>
  <div class="history-list">
    <div v-if="sessions.length === 0" class="empty-state">
      <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="1">
        <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p>暂无历史记录</p>
      <button class="new-chat-link" @click="$emit('new-session')">开始新对话</button>
    </div>

    <div v-else>
      <div v-for="group in groupedSessions" :key="group.label" class="history-group">
        <h3 class="history-group-title">{{ group.label }}</h3>
        <div class="history-cards">
          <div
            v-for="session in group.sessions"
            :key="session.id"
            class="history-card"
            @click="$emit('select-session', session.id)"
          >
            <div class="card-header">
              <div class="card-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 4v-4z" />
                </svg>
                <span>{{ session.title }}</span>
              </div>
              <div class="card-actions">
                <button class="card-star" @click.stop="$emit('star-session', session.id)">
                  <svg width="14" height="14" viewBox="0 0 24 24" :fill="session.isStarred ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                  </svg>
                </button>
                <button class="card-menu" @click.stop="showMenu($event, session.id)">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 5v.01M12 12v.01M12 19v.01" />
                  </svg>
                </button>
              </div>
            </div>
            <div class="card-preview">
              <span class="message-count">{{ session.messages.length }} 条消息</span>
              <span class="card-date">{{ formatDate(session.updatedAt) }}</span>
            </div>
            <div v-if="session.messages.length > 0" class="card-last-message">
              {{ session.messages[session.messages.length - 1]?.content.slice(0, 80) }}...
            </div>
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="fade">
        <div v-if="menuVisible" class="dropdown-menu" :style="menuStyle">
          <div class="dropdown-item" @click="handleRename">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            重命名
          </div>
          <div class="dropdown-item danger" @click="handleDelete">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            删除
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import type { Session } from '../types'

const props = defineProps<{
  sessions: Session[]
}>()

const emit = defineEmits<{
  'select-session': [id: string]
  'delete-session': [id: string]
  'rename-session': [id: string, title: string]
  'star-session': [id: string]
  'new-session': []
}>()

const groupedSessions = computed(() => {
  const today = new Date()
  const groups: { label: string; sessions: Session[] }[] = [
    { label: '今天', sessions: [] },
    { label: '昨天', sessions: [] },
    { label: '本周', sessions: [] },
    { label: '更早', sessions: [] }
  ]

  props.sessions.forEach(session => {
    const date = new Date(session.updatedAt)
    const diffDays = Math.floor((today.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

    if (diffDays === 0) groups[0].sessions.push(session)
    else if (diffDays === 1) groups[1].sessions.push(session)
    else if (diffDays <= 7) groups[2].sessions.push(session)
    else groups[3].sessions.push(session)
  })

  return groups.filter(g => g.sessions.length > 0)
})

const menuVisible = ref(false)
const menuStyle = ref({})
const selectedSessionId = ref<string | null>(null)

function showMenu(event: MouseEvent, sessionId: string) {
  selectedSessionId.value = sessionId
  menuVisible.value = true
  menuStyle.value = {
    position: 'fixed',
    left: event.clientX - 120 + 'px',
    top: event.clientY + 8 + 'px',
    zIndex: 9999
  }
}

function handleRename() {
  if (!selectedSessionId.value) return
  const session = props.sessions.find(s => s.id === selectedSessionId.value)
  if (!session) return

  const newTitle = prompt('请输入新名称：', session.title)
  if (newTitle?.trim()) {
    emit('rename-session', selectedSessionId.value, newTitle.trim())
  }
  menuVisible.value = false
}

function handleDelete() {
  if (!selectedSessionId.value) return
  if (confirm('确定要删除这个会话吗？')) {
    emit('delete-session', selectedSessionId.value)
  }
  menuVisible.value = false
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (!target.closest('.dropdown-menu')) {
    menuVisible.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.history-list {
  min-height: calc(100vh - 80px);
}

.empty-state {
  text-align: center;
  padding: 80px 24px;
  color: var(--text-secondary);
}

.empty-state svg {
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state p {
  margin-bottom: 16px;
}

.new-chat-link {
  padding: 8px 24px;
  background: var(--primary-color);
  color: white;
  border-radius: var(--radius-md);
  font-size: 14px;
  transition: var(--transition);
}

.new-chat-link:hover {
  background: var(--primary-hover);
}

.history-group {
  margin-bottom: 32px;
}

.history-group-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
  padding-left: 4px;
}

.history-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-card {
  background: var(--bg-main);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 16px;
  cursor: pointer;
  transition: var(--transition);
}

.history-card:hover {
  border-color: var(--primary-color);
  box-shadow: var(--shadow-md);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
}

.card-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.history-card:hover .card-actions {
  opacity: 1;
}

.card-star,
.card-menu {
  padding: 4px;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  transition: var(--transition);
}

.card-star:hover,
.card-menu:hover {
  background: var(--bg-sidebar);
}

.card-star svg[fill="currentColor"] {
  color: #fbbf24;
}

.card-preview {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.card-last-message {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
  opacity: 0.8;
}

.dropdown-menu {
  background: white;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  min-width: 140px;
  padding: 4px 0;
  z-index: 10000;
}

.dropdown-item {
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  transition: var(--transition);
}

.dropdown-item:hover {
  background: var(--bg-sidebar);
}

.dropdown-item.danger {
  color: #dc2626;
}

.dropdown-item.danger:hover {
  background: #fef2f2;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>