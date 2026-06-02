<template>
  <div class="message" :class="message.role">
    <div class="message-avatar">{{ message.role === 'user' ? '我' : 'AI' }}</div>
    <div class="message-content-wrapper">
      <div class="message-bubble">
        <div class="message-text" v-html="formattedContent" />
      </div>
      <div class="message-meta">
        <span class="message-time">{{ formatTime(message.timestamp) }}</span>
        <span v-if="message.category" class="category-tag">{{ message.category }}</span>
      </div>
      <div v-if="message.role === 'assistant'" class="message-actions">
        <button class="action-btn" @click="$emit('copy')" title="复制">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
          </svg>
        </button>
        <button class="action-btn" @click="$emit('regenerate')" title="重新生成">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
        <div class="feedback-buttons">
          <button
            class="action-btn"
            :class="{ active: message.feedback === 'like' }"
            @click="$emit('feedback', 'like')"
            title="有帮助"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
            </svg>
          </button>
          <button
            class="action-btn"
            :class="{ active: message.feedback === 'dislike' }"
            @click="$emit('feedback', 'dislike')"
            title="无帮助"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06L17 4m-7 10v5a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Message } from '../types'

const props = defineProps<{
  message: Message
}>()

defineEmits<{
  copy: []
  regenerate: []
  feedback: [type: 'like' | 'dislike']
}>()

const formattedContent = computed(() => {
  let content = props.message.content

  // 1. 代码块（优先处理，避免内部被其他正则干扰）
  content = content.replace(/```(\w+)?\n([\s\S]*?)```/g, (_, lang, code) => `
    <div class="code-block">
      <div class="code-header">
        <span class="code-lang">${lang || 'text'}</span>
      </div>
      <pre><code>${escapeHtml(code.trim())}</code></pre>
    </div>
  `)

  // 2. 行内代码
  content = content.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // 3. 标题（### 优先级高于 ## 高于 #，避免重复替换）
  content = content.replace(/^#### (.*$)/gim, '<h4>$1</h4>')
  content = content.replace(/^### (.*$)/gim, '<h3>$1</h3>')
  content = content.replace(/^## (.*$)/gim, '<h2>$1</h2>')
  content = content.replace(/^# (.*$)/gim, '<h1>$1</h1>')

  // 4. 粗体、斜体、删除线
  content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  content = content.replace(/\*(.*?)\*/g, '<em>$1</em>')
  content = content.replace(/~~(.*?)~~/g, '<del>$1</del>')

  // 5. 引用块
  content = content.replace(/^>\s+(.*$)/gim, '<blockquote>$1</blockquote>')

  // 6. 表格（在列表之前处理）
  content = formatTable(content)

  // 7. 无序列表（只匹配 - 或 *，不匹配 1. 2. 等数字）
  content = content.replace(/^(\s*)[-*+]\s+(.*$)/gim, '$1<li>$2</li>')

  // 8. 有序列表（只匹配数字+点+空格，如 "1. "、"2. "）
  // 注意：这里用 \d+\.\s 匹配，但标题里的 "1. " 已经被上面的 h1-h4 处理了
  // 如果还有没被处理的，说明是真的列表
  content = content.replace(/^(\s*)\d+\.\s+(.*$)/gim, '$1<li>$2</li>')

  // 包裹连续的 li 为 ul/ol
  content = content.replace(/(<li>.*<\/li>(?:\n|$))+/g, (match) => {
    // 判断是有序还是无序：如果原始行以数字开头就是有序，否则无序
    const isOrdered = /^\s*\d+\./.test(match.split('\n')[0] || '')
    const tag = isOrdered ? 'ol' : 'ul'
    return `<${tag}>${match}</${tag}>`
  })

  // 9. 链接
  content = content.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')

  // 10. 水平线
  content = content.replace(/^---+$/gim, '<hr>')

  // 11. 换行处理：最多保留一个空行，避免间距过大
  // 先处理段落：两个换行 -> 段落分隔
  content = content.replace(/\n\n+/g, '</p>\n<p>')
  // 单个换行 -> <br>
  content = content.replace(/\n/g, '<br>')

  // 包裹为段落（如果没有被其他标签包裹）
  content = content.split(/(<\/?(?:h[1-6]|ul|ol|li|blockquote|pre|div|table|hr)[^>]*>)/).map((part, index) => {
    if (index % 2 === 1) return part // 是标签，原样返回
    if (!part.trim()) return '' // 空字符串
    if (part.startsWith('<p>') || part.startsWith('<br>')) return part
    return `<p>${part}</p>`
  }).join('')

  // 清理空的段落
  content = content.replace(/<p><\/p>/g, '')
  content = content.replace(/<p><br><\/p>/g, '<br>')

  // 修复段落嵌套问题
  content = content.replace(/<\/p>\s*<p>/g, '</p><p>')

  return content
})

function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function formatTable(text: string): string {
  const lines = text.split('\n')
  let inTable = false
  let result: string[] = []
  let tableRows: string[] = []

  for (const line of lines) {
    if (line.trim().startsWith('|')) {
      if (!inTable) {
        inTable = true
        tableRows = []
      }
      tableRows.push(line)
    } else {
      if (inTable) {
        result.push(renderTable(tableRows))
        inTable = false
      }
      result.push(line)
    }
  }

  if (inTable) {
    result.push(renderTable(tableRows))
  }

  return result.join('\n')
}

function renderTable(rows: string[]): string {
  if (rows.length < 2) return rows.join('\n')

  // 过滤分隔行 |---|---|
  const dataRows = rows.filter(row => {
    const content = row.replace(/\|/g, '').trim()
    return !/^[\s\-:|]+$/.test(content)
  })

  if (dataRows.length < 1) return rows.join('\n')

  let html = '<div class="table-wrapper"><table class="msg-table"><thead><tr>'
  const headers = dataRows[0].split('|').map(c => c.trim()).filter(c => c)
  html += headers.map(h => `<th>${escapeHtml(h)}</th>`).join('')
  html += '</tr></thead><tbody>'

  for (let i = 1; i < dataRows.length; i++) {
    const cells = dataRows[i].split('|').map(c => c.trim()).filter(c => c)
    html += '<tr>' + cells.map(c => `<td>${escapeHtml(c)}</td>`).join('') + '</tr>'
  }
  html += '</tbody></table></div>'

  return html
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease;
}

.message.user {
  flex-direction: row-reverse;
}

.message.user .message-bubble {
  background: var(--primary-light);
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.message.user .message-avatar {
  background: var(--primary-color);
  color: white;
}

.message.assistant .message-avatar {
  background: #10b981;
  color: white;
}

.message-content-wrapper {
  flex: 1;
  max-width: calc(100% - 48px);
}

.message.user .message-content-wrapper {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.message-bubble {
  background: var(--bg-main);
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  max-width: 100%;
  overflow-wrap: break-word;
}

.message.user .message-bubble {
  background: var(--primary-light);
}

.message-text {
  line-height: 1.6;
  font-size: 14px;
  color: var(--text-primary);
}

/* ===== Markdown 样式 ===== */

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(h4) {
  margin: 12px 0 8px 0;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text-primary);
}

.message-text :deep(h1) { font-size: 1.4em; }
.message-text :deep(h2) { font-size: 1.25em; }
.message-text :deep(h3) { font-size: 1.1em; }
.message-text :deep(h4) { font-size: 1em; }

.message-text :deep(p) {
  margin: 0 0 8px 0;
}

.message-text :deep(p:last-child) {
  margin-bottom: 0;
}

/* 列表样式 */
.message-text :deep(ul),
.message-text :deep(ol) {
  margin: 4px 0;
  padding-left: 20px;
}

.message-text :deep(li) {
  margin: 2px 0;
  line-height: 1.6;
}

/* 有序列表数字样式 */
.message-text :deep(ol) {
  list-style-type: decimal;
}

.message-text :deep(ol) li {
  display: list-item;
}

/* 无序列表 */
.message-text :deep(ul) {
  list-style-type: disc;
}

/* 引用块 */
.message-text :deep(blockquote) {
  border-left: 3px solid var(--primary-color);
  margin: 8px 0;
  padding: 6px 12px;
  background: var(--primary-light);
  border-radius: 0 6px 6px 0;
}

/* 链接 */
.message-text :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
}

.message-text :deep(a:hover) {
  text-decoration: underline;
}

/* 水平线 */
.message-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 12px 0;
}

/* 删除线 */
.message-text :deep(del) {
  color: var(--text-secondary);
}

/* 粗体 */
.message-text :deep(strong) {
  font-weight: 600;
}

/* 斜体 */
.message-text :deep(em) {
  font-style: italic;
}

/* 代码块 */
.message-text :deep(.code-block) {
  background: #1e293b;
  border-radius: 8px;
  margin: 8px 0;
  overflow: hidden;
}

.message-text :deep(.code-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #0f172a;
  border-bottom: 1px solid #334155;
}

.message-text :deep(.code-lang) {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
}

.message-text :deep(pre) {
  margin: 0;
  padding: 10px 12px;
  overflow-x: auto;
}

.message-text :deep(pre code) {
  color: #e2e8f0;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
}

/* 行内代码 */
.message-text :deep(.inline-code) {
  background: var(--bg-sidebar);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  color: var(--primary-color);
}

/* 表格 */
.message-text :deep(.table-wrapper) {
  overflow-x: auto;
  margin: 8px 0;
}

.message-text :deep(.msg-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.message-text :deep(.msg-table th),
.message-text :deep(.msg-table td) {
  border: 1px solid var(--border-color);
  padding: 6px 10px;
  text-align: left;
}

.message-text :deep(.msg-table th) {
  background: var(--bg-sidebar);
  font-weight: 600;
}

.message-text :deep(.msg-table tr:nth-child(even)) {
  background: var(--bg-sidebar);
}

/* 元信息 */
.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-secondary);
}

.message.user .message-meta {
  justify-content: flex-end;
}

.category-tag {
  background: var(--primary-light);
  color: var(--primary-color);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
}

/* 操作按钮 */
.message-actions {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message-content-wrapper:hover .message-actions {
  opacity: 1;
}

.message.user .message-actions {
  justify-content: flex-end;
}

.action-btn {
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  transition: var(--transition);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  cursor: pointer;
}

.action-btn:hover {
  background: var(--bg-sidebar);
  color: var(--text-primary);
}

.action-btn.active {
  color: var(--primary-color);
}

.feedback-buttons {
  display: flex;
  gap: 2px;
  margin-left: 4px;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>