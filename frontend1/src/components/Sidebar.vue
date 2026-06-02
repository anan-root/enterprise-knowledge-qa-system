<template>
  <aside class="sidebar" :class="{ open: isOpen }">
    <div class="sidebar-header">
      <button class="new-chat-btn" @click="$emit('new-session')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 4v16m8-8H4" />
        </svg>
        新建会话
      </button>
    </div>

    <div class="sidebar-nav">
      <router-link to="/" class="nav-item" @click="closeSidebar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
        聊天
      </router-link>
      <router-link to="/history" class="nav-item" @click="closeSidebar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        历史记录
      </router-link>
      <router-link to="/settings" class="nav-item" @click="closeSidebar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        设置
      </router-link>
    </div>

    <div class="sidebar-divider" />

    <div class="sidebar-content">
      <div v-for="group in groupedSessions" :key="group.label" class="session-group">
        <div class="session-group-title">{{ group.label }}</div>
        <div
          v-for="session in group.sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === currentSessionId }"
          @click="$emit('select-session', session.id)"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 4v-4z" />
          </svg>
          <span class="session-title">{{ session.title }}</span>
          <div class="session-actions">
            <button class="session-star" @click.stop="$emit('star-session', session.id)">
              <svg width="14" height="14" viewBox="0 0 24 24" :fill="session.isStarred ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
            </button>
            <button class="session-menu" @click.stop="showMenu($event, session.id)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 5v.01M12 12v.01M12 19v.01" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="sidebar-footer">
      <div class="footer-info">
        <span>企业知识库智能问答系统</span>
        <span class="version">v1.0.0</span>
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
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import type { Session } from '../types'

const props = defineProps<{
  sessions: Session[]
  currentSessionId: string | null
  modelValue?: boolean
}>()

const emit = defineEmits<{
  'select-session': [id: string]
  'new-session': []
  'delete-session': [id: string]
  'rename-session': [id: string, title: string]
  'star-session': [id: string]
}>()

const isOpen = computed(() => props.modelValue)

const groupedSessions = computed(() => {
  const today = new Date()
  const groups: { label: string; sessions: Session[] }[] = [
    { label: '今天', sessions: [] },
    { label: '昨天', sessions: [] },
    { label: '最近7天', sessions: [] },
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
    left: event.clientX - 140 + 'px',
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

function closeSidebar() {
  emit('update:modelValue', false)
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
.sidebar {
  width: 280px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: transform 0.3s ease;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.new-chat-btn {
  width: 100%;
  padding: 12px;
  background: var(--primary-color);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: var(--transition);
}

.new-chat-btn:hover {
  background: var(--primary-hover);
}

.sidebar-nav {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  color: var(--text-primary);
  text-decoration: none;
  transition: var(--transition);
}

.nav-item:hover {
  background: #e2e8f0;
}

.nav-item.router-link-active {
  background: var(--primary-light);
  color: var(--primary-color);
}

.sidebar-divider {
  height: 1px;
  background: var(--border-color);
  margin: 8px 16px;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-group {
  margin-bottom: 16px;
}

.session-group-title {
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.session-item {
  padding: 10px 12px;
  margin: 2px 0;
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--text-primary);
  transition: var(--transition);
}

.session-item:hover {
  background: #e2e8f0;
}

.session-item.active {
  background: var(--primary-light);
  color: var(--primary-color);
}

.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-actions {
  opacity: 1;
}

.session-star,
.session-menu {
  padding: 4px;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  transition: var(--transition);
}

.session-star:hover,
.session-menu:hover {
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-primary);
}

.session-star svg[fill="currentColor"] {
  color: #fbbf24;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--border-color);
}

.footer-info {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}

.version {
  font-family: monospace;
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

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 200;
    transform: translateX(-100%);
  }

  .sidebar.open {
    transform: translateX(0);
  }
}
</style>
