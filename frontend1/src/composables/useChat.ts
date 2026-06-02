// frontend1/src/composables/useChat.ts
import { ref } from 'vue'
import type { ApiResponse, HistoryMessage } from '../types'

const API_BASE_URL = ''

export function useChat() {
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  let abortController: AbortController | null = null

  async function sendMessage(
    question: string,
    sessionId: string | null = null,
    history: HistoryMessage[] = [],
    onChunk?: (chunk: string) => void
  ): Promise<ApiResponse> {
    isLoading.value = true
    error.value = null

    abortController = new AbortController()
    let fullContent = ''

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question,
          session_id: sessionId,
          cot: true,
          max_concurrent: 5,
          stream: true,
          history: history.length > 0 ? history : undefined,
        }),
        signal: abortController.signal
      })

      if (!response.ok) {
        const errText = await response.text()
        throw new Error(errText)
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder('utf-8')
      let done = false

      while (!done) {
        const { value, done: readerDone } = await reader.read()
        done = readerDone

        if (value) {
          const chunk = decoder.decode(value, { stream: true })
          fullContent += chunk
          onChunk?.(fullContent)
        }
      }

      return {
        content: fullContent,
        category: undefined,
        sources: []
      }

    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return {
          content: fullContent + '\n\n已停止生成',
          category: undefined,
          sources: []
        }
      }

      error.value = err instanceof Error ? err.message : '请求失败'
      return {
        content: `请求失败：${error.value}`,
        category: undefined,
        sources: []
      }
    } finally {
      isLoading.value = false
      abortController = null
    }
  }

  function stopGenerate() {
    if (abortController) {
      abortController.abort()
    }
  }

  return {
    isLoading,
    error,
    sendMessage,
    stopGenerate
  }
}
