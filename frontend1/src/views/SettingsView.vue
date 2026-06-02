<template>
  <div class="settings-view">
    <header class="settings-header">
      <button class="back-btn" @click="router.back()">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
        返回
      </button>
      <h1>设置</h1>
    </header>

    <div class="settings-content">
      <SettingsPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import SettingsPanel from '../components/SettingsPanel.vue'

const router = useRouter()
</script>

<style scoped>
.settings-view {
  min-height: 100vh;
  background: var(--bg-sidebar);
}

.settings-header {
  position: sticky;
  top: 0;
  display: flex;
  align-items: center;
  gap: 16px;
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

.settings-header h1 {
  font-size: 20px;
  font-weight: 600;
}

.settings-content {
  max-width: 600px;
  margin: 0 auto;
  padding: 24px;
}
</style>