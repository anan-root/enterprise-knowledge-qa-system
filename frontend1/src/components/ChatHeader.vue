<template>
  <header class="chat-header">
    <div class="header-left">
      <button class="menu-btn" @click="$emit('toggle-sidebar')">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <div class="title-section">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--primary-color)" stroke-width="2">
          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span class="title">{{ title }}</span>
        <span v-if="hasMessages" class="message-count">{{ messageCount }} 条消息</span>
      </div>
    </div>
    <div class="header-right">
      <button class="action-btn" @click="$emit('star-session')" :title="isStarred ? '取消收藏' : '收藏会话'">
        <svg width="18" height="18" viewBox="0 0 24 24" :fill="isStarred ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
      </button>
      <button v-if="hasMessages" class="action-btn" @click="$emit('clear-session')" title="清空会话">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  title: string
  hasMessages: boolean
  isStarred?: boolean
}>()

const emit = defineEmits<{
  'toggle-sidebar': []
  'clear-session': []
  'star-session': []
}>()

const messageCount = computed(() => {
  // 这个值需要从父组件传递，这里简化处理
  return 0
})
</script>

<style scoped>
.chat-header {
  height: 60px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-main);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-btn {
  display: none;
  padding: 8px;
  border-radius: var(--radius-md);
  color: var(--text-primary);
  transition: var(--transition);
}

.menu-btn:hover {
  background: var(--bg-sidebar);
}

.title-section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title {
  font-size: 16px;
  font-weight: 600;
}

.message-count {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-sidebar);
  padding: 2px 8px;
  border-radius: 12px;
}

.header-right {
  display: flex;
  gap: 8px;
}

.action-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: var(--transition);
}

.action-btn:hover {
  background: var(--bg-sidebar);
  color: var(--text-primary);
}

.action-btn svg[fill="currentColor"] {
  color: #fbbf24;
}

@media (max-width: 768px) {
  .menu-btn {
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
</style>