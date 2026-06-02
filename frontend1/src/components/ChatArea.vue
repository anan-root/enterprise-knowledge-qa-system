<template>
  <div class="chat-area" :class="{ empty: messages.length === 0 }">
    <div v-if="messages.length === 0" class="welcome-section">
      <div class="welcome-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--primary-color)" stroke-width="1.5">
          <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      </div>
      <h1 class="welcome-title">企业知识库智能问答系统</h1>
      <p class="welcome-subtitle">
        基于企业知识库与实时数据，提供专业、可追溯的智能问答服务
      </p>
<!--      <div class="quick-actions">-->
<!--        <div-->
<!--          v-for="action in quickActions"-->
<!--          :key="action.title"-->
<!--          class="quick-card"-->
<!--          @click="$emit('quick-action', action.query)"-->
<!--        >-->
<!--          <div class="quick-card-icon" v-html="action.icon" />-->
<!--          <div class="quick-card-title">{{ action.title }}</div>-->
<!--          <div class="quick-card-desc">{{ action.description }}</div>-->
<!--        </div>-->
<!--      </div>-->
    </div>

    <div v-else class="messages-container" ref="messagesContainer">
      <div class="messages-list">
        <MessageItem
          v-for="msg in messages"
          :key="msg.id"
          :message="msg"
          @copy="$emit('copy-message', msg.content)"
          @regenerate="$emit('regenerate-message', msg.id)"
          @feedback="(type) => $emit('feedback', msg.id, type)"
        />

        <div v-if="isLoading" class="message assistant">
          <div class="message-avatar">AI</div>
          <div class="message-bubble">
            <div class="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="input-container">
      <div class="input-wrapper">
        <textarea
          ref="textareaRef"
          v-model="inputContent"
          class="input-textarea"
          :placeholder="placeholder"
          rows="1"
          @keydown="handleKeyDown"
          @input="autoResize"
        />
<!--        <div class="input-tools">-->
<!--          <button-->
<!--            class="tool-btn"-->
<!--            :class="{ active: activeTools.webSearch }"-->
<!--            @click="activeTools.webSearch = !activeTools.webSearch"-->
<!--            title="联网搜索"-->
<!--          >-->
<!--            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">-->
<!--              <path d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />-->
<!--            </svg>-->
<!--          </button>-->
<!--          <button-->
<!--            class="tool-btn"-->
<!--            :class="{ active: activeTools.vectorSearch }"-->
<!--            @click="activeTools.vectorSearch = !activeTools.vectorSearch"-->
<!--            title="法规库查询"-->
<!--          >-->
<!--            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">-->
<!--              <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />-->
<!--            </svg>-->
<!--          </button>-->
<!--        </div>-->
        <button
          v-if="isLoading"
          class="stop-btn"
          @click="stopGeneration"
          title="停止生成"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2"/>
          </svg>
        </button>

        <button
          class="send-btn"
          :disabled="!inputContent.trim() || isLoading"
          @click="sendMessage"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
      <div class="input-hint">
        <span>Enter 发送，Shift+Enter 换行</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import MessageItem from './MessageItem.vue'
import type { Message, ToolConfig } from '../types'

const props = defineProps<{
  messages: Message[]
  isLoading: boolean
}>()
const emit = defineEmits<{
  'send-message': [content: string, tools: ToolConfig]
  'quick-action': [query: string]
  'copy-message': [content: string]
  'regenerate-message': [msgId: string]
  'feedback': [msgId: string, type: 'like' | 'dislike']
  'stop-generation': []  // 新增
}>()


const inputContent = ref('')
const textareaRef = ref<HTMLTextAreaElement>()
const messagesContainer = ref<HTMLDivElement>()
const activeTools = ref<ToolConfig>({ webSearch: false, vectorSearch: false })
const placeholder = '输入您的问题，例如：查询2024年上海医疗设备招标项目...'

// const quickActions: QuickAction[] = [
//   {
//     title: '招标信息检索',
//     description: '查询历史招标记录、中标信息等',
//     icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>',
//     query: '2024年上海的医疗设备招标项目有哪些？'
//   },
//   {
//     title: '法规合规判断',
//     description: '判断资质、评分标准是否合规',
//     icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" /></svg>',
//     query: '某评分标准设置AAA证书每项2分，是否符合法规？'
//   },
//   {
//     title: '企业风险分析',
//     description: '查询企业资质、信用、经营风险',
//     icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>',
//     query: '查询北京远洋控股集团的企业风险'
//   },
//   {
//     title: '供应商推荐',
//     description: '按价格、距离、风险推荐供应商',
//     icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>',
//     query: '推荐几家混凝土供应商，按距离排序'
//   }
// ]

watch(() => props.messages.length, () => scrollToBottom())
watch(() => props.isLoading, () => scrollToBottom())

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}
function stopGeneration() {
  emit('stop-generation')
}
function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

function sendMessage() {
  const content = inputContent.value.trim()
  if (!content || props.isLoading) return

  emit('send-message', content, { ...activeTools.value })
  inputContent.value = ''

  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
    }
  })
}
</script>

<style scoped>
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-chat);
  position: relative;
  height: 100%;
}

.chat-area.empty {
  justify-content: center;
}

.welcome-section {
  text-align: center;
  padding: 48px 24px;
  max-width: 600px;
  margin: 0 auto;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
}

.welcome-icon {
  margin-bottom: 24px;
}

.welcome-title {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 12px;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.welcome-subtitle {
  font-size: 16px;
  color: var(--text-secondary);
  margin-bottom: 32px;
  line-height: 1.6;
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.quick-card {
  background: var(--bg-main);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 16px;
  text-align: left;
  cursor: pointer;
  transition: var(--transition);
}

.quick-card:hover {
  border-color: var(--primary-color);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.quick-card-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--primary-light);
  color: var(--primary-color);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}

.quick-card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}

.quick-card-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  min-height: 0;
}

.messages-list {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.message {
  display: flex;
  gap: 12px;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #10b981;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.message-bubble {
  flex: 1;
  background: var(--bg-main);
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--text-secondary);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.input-container {
  border-top: 1px solid var(--border-color);
  background: var(--bg-main);
  padding: 16px 24px 24px;
  flex-shrink: 0;
  margin-top: auto;
}

.input-wrapper {
  max-width: 800px;
  margin: 0 auto;
  position: relative;
}

.input-textarea {
  width: 100%;
  min-height: 52px;
  max-height: 200px;
  padding: 14px 120px 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  outline: none;
  font-family: inherit;
  transition: var(--transition);
}

.input-textarea:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.input-textarea::placeholder {
  color: var(--text-secondary);
}

.input-tools {
  position: absolute;
  left: 12px;
  bottom: 12px;
  display: flex;
  gap: 8px;
}

.tool-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: var(--transition);
}

.tool-btn:hover {
  background: var(--bg-sidebar);
  color: var(--text-primary);
}

.tool-btn.active {
  background: var(--primary-light);
  color: var(--primary-color);
}

.send-btn {
  position: absolute;
  right: 12px;
  bottom: 12px;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--primary-color);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition);
}

.send-btn:hover:not(:disabled) {
  background: var(--primary-hover);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.stop-btn {
  position: absolute;
  right: 48px; /* 在发送按钮左边 */
  bottom: 12px;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: #ef4444;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition);
}

.stop-btn:hover {
  background: #dc2626;
}

.input-hint {
  max-width: 800px;
  margin: 8px auto 0;
  font-size: 12px;
  color: var(--text-secondary);
  text-align: right;
}

@media (max-width: 768px) {
  .quick-actions {
    grid-template-columns: 1fr;
  }

  .messages-container {
    padding: 16px;
  }

  .input-container {
    padding: 12px 16px 20px;
  }
}
</style>
