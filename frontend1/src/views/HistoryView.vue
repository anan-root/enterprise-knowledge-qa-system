<template>
  <div class="history-view">
    <header class="history-header">
      <button class="back-btn" @click="router.back()">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
        返回
      </button>
      <h1>历史记录</h1>
      <button class="clear-all-btn" @click="clearAllHistory" v-if="hasHistory">
        清空所有
      </button>
    </header>

    <div class="history-content">
      <HistoryList
        :sessions="sessionStore.sessions"
        @select-session="handleSelectSession"
        @delete-session="sessionStore.deleteSession"
        @rename-session="handleRenameSession"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import HistoryList from '../components/HistoryList.vue'

const router = useRouter()
const sessionStore = useSessionStore()

const hasHistory = computed(() => sessionStore.sessions.length > 0)

function handleSelectSession(id: string) {
  sessionStore.setCurrentSession(id)
  router.push(`/session/${id}`)
}

function handleRenameSession(id: string, title: string) {
  sessionStore.updateSession(id, { title })
}

function clearAllHistory() {
  if (confirm('确定要删除所有历史记录吗？此操作不可恢复。')) {
    sessionStore.sessions.forEach(session => {
      sessionStore.deleteSession(session.id)
    })
  }
}
</script>

<style scoped>
.history-view {
  min-height: 100vh;
  background: var(--bg-sidebar);
}

.history-header {
  position: sticky;
  top: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: var(--bg-main);
  border-bottom: 1px solid var(--border-color);
  z-index: 10;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  transition: var(--transition);
}

.back-btn:hover {
  background: var(--bg-sidebar);
  color: var(--text-primary);
}

.history-header h1 {
  font-size: 20px;
  font-weight: 600;
}

.clear-all-btn {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  color: #dc2626;
  transition: var(--transition);
}

.clear-all-btn:hover {
  background: #fef2f2;
}

.history-content {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
}
</style>