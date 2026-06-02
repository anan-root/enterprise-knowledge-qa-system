<template>
  <div class="settings-panel">
    <div class="settings-section">
      <h3 class="section-title">外观设置</h3>
      <div class="setting-item">
        <label>主题</label>
        <div class="theme-options">
          <button
            class="theme-option"
            :class="{ active: settings.theme === 'light' }"
            @click="updateSetting('theme', 'light')"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            浅色
          </button>
          <button
            class="theme-option"
            :class="{ active: settings.theme === 'dark' }"
            @click="updateSetting('theme', 'dark')"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
            深色
          </button>
          <button
            class="theme-option"
            :class="{ active: settings.theme === 'auto' }"
            @click="updateSetting('theme', 'auto')"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707" />
              <path d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
            跟随系统
          </button>
        </div>
      </div>
      <div class="setting-item">
        <label>字体大小</label>
        <div class="font-size-options">
          <button
            class="font-option"
            :class="{ active: settings.fontSize === 'small' }"
            @click="updateSetting('fontSize', 'small')"
          >
            A小
          </button>
          <button
            class="font-option"
            :class="{ active: settings.fontSize === 'medium' }"
            @click="updateSetting('fontSize', 'medium')"
          >
            A中
          </button>
          <button
            class="font-option"
            :class="{ active: settings.fontSize === 'large' }"
            @click="updateSetting('fontSize', 'large')"
          >
            A大
          </button>
        </div>
      </div>
    </div>

    <div class="settings-section">
      <h3 class="section-title">聊天设置</h3>
      <div class="setting-item toggle">
        <label>回车发送消息</label>
        <button
          class="toggle-switch"
          :class="{ active: settings.enterToSend }"
          @click="updateSetting('enterToSend', !settings.enterToSend)"
        >
          <span class="toggle-slider"></span>
        </button>
      </div>
      <div class="setting-item toggle">
        <label>显示消息时间戳</label>
        <button
          class="toggle-switch"
          :class="{ active: settings.showTimestamp }"
          @click="updateSetting('showTimestamp', !settings.showTimestamp)"
        >
          <span class="toggle-slider"></span>
        </button>
      </div>
    </div>

    <div class="settings-section">
      <h3 class="section-title">数据管理</h3>
      <div class="setting-item">
        <label>存储位置</label>
        <span class="setting-value">本地存储 (LocalStorage)</span>
      </div>
      <div class="setting-item">
        <label>数据大小</label>
        <span class="setting-value">{{ storageSize }}</span>
      </div>
      <div class="setting-item">
        <button class="danger-btn" @click="exportData">导出数据</button>
        <button class="danger-btn" @click="clearAllData">清空所有数据</button>
      </div>
    </div>

    <div class="settings-section">
      <h3 class="section-title">关于</h3>
      <div class="about-info">
        <p><strong>企业知识库智能问答系统</strong></p>
        <p>版本 v1.0.0</p>
        <p>基于企业知识库与实时数据，提供专业、可追溯的智能问答服务</p>
        <p class="copyright">© 2026 企业知识库智能问答系统</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import type { UserSettings } from '../types'
import { useSessionStore } from '../stores/session'

const sessionStore = useSessionStore()

const settings = reactive<UserSettings>({
  theme: 'light',
  fontSize: 'medium',
  autoSend: false,
  enterToSend: true,
  showTimestamp: true
})

const storageSize = computed(() => {
  const data = localStorage.getItem('bid_sessions')
  if (!data) return '0 KB'
  const size = new Blob([data]).size
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  return `${(size / (1024 * 1024)).toFixed(2)} MB`
})

onMounted(() => {
  const saved = localStorage.getItem('bid_settings')
  if (saved) {
    try {
      Object.assign(settings, JSON.parse(saved))
    } catch {}
  }
  applyTheme(settings.theme)
  applyFontSize(settings.fontSize)
})

function updateSetting<K extends keyof UserSettings>(key: K, value: UserSettings[K]) {
  settings[key] = value
  localStorage.setItem('bid_settings', JSON.stringify(settings))

  if (key === 'theme') applyTheme(value as string)
  if (key === 'fontSize') applyFontSize(value as string)
}

function applyTheme(theme: string) {
  if (theme === 'dark') {
    document.documentElement.style.setProperty('--bg-sidebar', '#1e293b')
    document.documentElement.style.setProperty('--bg-main', '#0f172a')
    document.documentElement.style.setProperty('--bg-chat', '#1e293b')
    document.documentElement.style.setProperty('--text-primary', '#f1f5f9')
    document.documentElement.style.setProperty('--text-secondary', '#94a3b8')
    document.documentElement.style.setProperty('--border-color', '#334155')
  } else {
    document.documentElement.style.setProperty('--bg-sidebar', '#f8fafc')
    document.documentElement.style.setProperty('--bg-main', '#ffffff')
    document.documentElement.style.setProperty('--bg-chat', '#f1f5f9')
    document.documentElement.style.setProperty('--text-primary', '#1e293b')
    document.documentElement.style.setProperty('--text-secondary', '#64748b')
    document.documentElement.style.setProperty('--border-color', '#e2e8f0')
  }
}

function applyFontSize(size: string) {
  const sizes = { small: '13px', medium: '14px', large: '16px' }
  document.documentElement.style.setProperty('--font-size-base', sizes[size as keyof typeof sizes])
}

function exportData() {
  const data = {
    sessions: sessionStore.sessions,
    settings: settings,
    exportTime: new Date().toISOString()
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `bid-qa-backup-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function clearAllData() {
  if (confirm('确定要清空所有数据吗？此操作不可恢复。')) {
    sessionStore.sessions.forEach(session => {
      sessionStore.deleteSession(session.id)
    })
    localStorage.removeItem('bid_sessions')
    localStorage.removeItem('bid_current_session')
    localStorage.removeItem('bid_settings')
    alert('数据已清空')
    location.reload()
  }
}
</script>

<style scoped>
.settings-panel {
  background: var(--bg-main);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.settings-section {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
}

.settings-section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--text-primary);
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
}

.setting-item label {
  font-size: 14px;
  color: var(--text-primary);
}

.setting-value {
  font-size: 14px;
  color: var(--text-secondary);
}

.theme-options,
.font-size-options {
  display: flex;
  gap: 8px;
}

.theme-option,
.font-option {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-main);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: var(--transition);
}

.theme-option:hover,
.font-option:hover {
  border-color: var(--primary-color);
}

.theme-option.active,
.font-option.active {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
}

.setting-item.toggle {
  justify-content: space-between;
}

.toggle-switch {
  position: relative;
  width: 44px;
  height: 24px;
  background: var(--border-color);
  border-radius: 12px;
  cursor: pointer;
  transition: var(--transition);
}

.toggle-switch.active {
  background: var(--primary-color);
}

.toggle-slider {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  transition: transform 0.2s;
}

.toggle-switch.active .toggle-slider {
  transform: translateX(20px);
}

.danger-btn {
  padding: 8px 16px;
  border: 1px solid #dc2626;
  border-radius: var(--radius-md);
  background: transparent;
  color: #dc2626;
  font-size: 13px;
  cursor: pointer;
  transition: var(--transition);
}

.danger-btn:hover {
  background: #fef2f2;
}

.about-info {
  text-align: center;
  padding: 16px 0;
}

.about-info p {
  margin: 8px 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.about-info strong {
  color: var(--text-primary);
}

.copyright {
  margin-top: 16px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
