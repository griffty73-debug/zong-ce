<script setup lang="ts">
import { Bot, RotateCw, SendHorizontal, Sparkles } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import { apiFetch, postJson } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

type AiStatus = {
  configured: boolean
  model: string
  baseUrl: string
  message?: string
}

type AiChatResponse = {
  model: string
  content: string
  usage?: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
  }
  message?: string
}

const session = useSessionStore()
const status = ref<AiStatus | null>(null)
const prompt = ref('')
const messages = ref<ChatMessage[]>([])
const loadingStatus = ref(false)
const sending = ref(false)
const error = ref('')

const canSend = computed(() => Boolean(status.value?.configured && prompt.value.trim() && !sending.value))
const tokenText = computed(() => {
  const usage = lastUsage.value
  if (!usage?.total_tokens) return ''
  return `Tokens ${usage.total_tokens}`
})
const lastUsage = ref<AiChatResponse['usage'] | null>(null)

async function loadStatus() {
  loadingStatus.value = true
  error.value = ''
  try {
    status.value = await apiFetch<AiStatus>('/api/ai/status')
  } catch (err: any) {
    error.value = err.message || '模型状态加载失败'
  } finally {
    loadingStatus.value = false
  }
}

async function sendPrompt() {
  const content = prompt.value.trim()
  if (!content || sending.value) return
  error.value = ''
  sending.value = true
  prompt.value = ''
  messages.value.push({ role: 'user', content })
  try {
    const response = await postJson<AiChatResponse>('/api/ai/chat', {
      messages: messages.value.slice(-10),
      temperature: 0.2,
      maxTokens: 900,
    })
    messages.value.push({ role: 'assistant', content: response.content || response.message || '模型未返回内容' })
    lastUsage.value = response.usage || null
  } catch (err: any) {
    error.value = err.message || 'DeepSeek 调用失败'
    messages.value.pop()
  } finally {
    sending.value = false
  }
}

function clearChat() {
  messages.value = []
  lastUsage.value = null
  error.value = ''
}

onMounted(loadStatus)
</script>

<template>
  <div>
    <header class="page-header">
      <div>
        <p class="eyebrow">{{ session.user?.className || '全校' }}</p>
        <h1>智能助手</h1>
        <p class="muted">{{ status?.model || 'deepseek-v4-pro' }}</p>
      </div>
      <div class="toolbar">
        <button class="button secondary" type="button" :disabled="loadingStatus" @click="loadStatus">
          <RotateCw :size="16" aria-hidden="true" />
          刷新
        </button>
        <button class="button secondary" type="button" :disabled="!messages.length" @click="clearChat">
          清空
        </button>
      </div>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>

    <section class="panel ai-panel">
      <div class="ai-status">
        <span class="status-icon">
          <Sparkles :size="18" aria-hidden="true" />
        </span>
        <div>
          <strong>{{ status?.configured ? 'DeepSeek V4 Pro 已启用' : 'DeepSeek V4 Pro 未配置' }}</strong>
          <p class="muted">{{ status?.baseUrl || 'https://api.deepseek.com' }}</p>
        </div>
        <span v-if="tokenText" class="tag primary">{{ tokenText }}</span>
      </div>

      <div class="chat-window">
        <div v-if="!messages.length" class="assistant-empty">
          <Bot :size="38" aria-hidden="true" />
          <strong>综测智能问答</strong>
        </div>
        <div v-for="(item, index) in messages" :key="index" class="chat-row" :class="item.role">
          <div class="chat-bubble">{{ item.content }}</div>
        </div>
      </div>

      <form class="chat-input" @submit.prevent="sendPrompt">
        <textarea
          v-model="prompt"
          :disabled="!status?.configured || sending"
          placeholder="输入综测问题"
          rows="3"
        />
        <button class="button send-button" type="submit" :disabled="!canSend">
          <SendHorizontal :size="18" aria-hidden="true" />
          发送
        </button>
      </form>
    </section>
  </div>
</template>

<style scoped>
.ai-panel {
  display: grid;
  gap: 16px;
}

.ai-status {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
}

.status-icon {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: var(--primary);
  background: var(--primary-weak);
}

.ai-status p {
  margin: 2px 0 0;
}

.chat-window {
  min-height: 420px;
  max-height: 58vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px;
}

.assistant-empty {
  min-height: 320px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  color: var(--muted);
}

.chat-row {
  display: flex;
}

.chat-row.user {
  justify-content: flex-end;
}

.chat-bubble {
  width: min(760px, 88%);
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
  background: #f8fafc;
}

.chat-row.user .chat-bubble {
  border-color: #bcd0ff;
  background: var(--primary-weak);
}

.chat-input {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 10px;
  border-top: 1px solid var(--line);
  padding-top: 14px;
}

.chat-input textarea {
  width: 100%;
  min-height: 72px;
  resize: vertical;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px;
  background: #ffffff;
  color: var(--text);
}

.send-button {
  min-width: 92px;
  height: 42px;
}

@media (max-width: 720px) {
  .ai-status {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .ai-status .tag {
    grid-column: 2;
    justify-self: start;
  }

  .chat-input {
    grid-template-columns: 1fr;
  }

  .send-button {
    width: 100%;
  }
}
</style>
