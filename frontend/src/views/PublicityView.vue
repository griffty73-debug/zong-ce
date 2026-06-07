<script setup lang="ts">
import { Download, FileSpreadsheet, FileText, Megaphone, RotateCw, Trophy } from 'lucide-vue-next'
import { onMounted, reactive, ref, watch } from 'vue'

import { apiFetch, postJson } from '@/api/client'
import type { RankItem } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import { useTermRefresh } from '@/composables/useTermRefresh'
import { useSessionStore } from '@/stores/session'
import { useTermStore } from '@/stores/term'

const session = useSessionStore()
const termStore = useTermStore()
const ranks = ref<RankItem[]>([])
const error = ref('')
const success = ref('')
const loading = ref(false)
const confirmPending = ref(false)
const suggestions = ref<string[]>([])
const countdown = ref('')
const exporting = ref<string>('')
const form = reactive({
  title: '综合测评公示',
  className: session.user?.className || '',
  days: 3,
})

type PublicityResponse = {
  message?: string
  items?: RankItem[]
  preview?: RankItem[]
  suggestions?: string[]
  requiresConfirmation?: boolean
  countdown?: { text: string } | null
  count?: number
  batch?: { title: string }
}

async function loadRanks() {
  error.value = ''
  loading.value = true
  try {
    const anonymous = session.role === 'student' ? '1' : '0'
    const qs = termStore.currentId ? `&termId=${termStore.currentId}` : ''
    const result = await apiFetch<PublicityResponse>(`/api/publicity/rank?anonymous=${anonymous}${qs}`)
    ranks.value = result.items || []
    suggestions.value = result.suggestions || []
    countdown.value = result.countdown?.text || ''
  } catch (err: any) {
    error.value = err.message || '加载排行榜失败'
  } finally {
    loading.value = false
  }
}

async function startPublicity() {
  error.value = ''
  success.value = ''
  try {
    const payload: Record<string, unknown> = { ...form, confirm: confirmPending.value ? '确认公示' : undefined }
    if (termStore.currentId) payload.termId = termStore.currentId
    const result = await postJson<PublicityResponse>('/api/publicity/start', payload)
    suggestions.value = result.suggestions || []
    if (result.requiresConfirmation) {
      confirmPending.value = true
      ranks.value = result.preview || ranks.value
      success.value = result.message || '已生成匿名公示预览'
      return
    }
    confirmPending.value = false
    success.value = result.message || `已发起公示：${result.batch?.title}，纳入 ${result.count} 份材料`
    await loadRanks()
  } catch (err: any) {
    error.value = err.message || '发起公示失败'
  }
}

async function downloadExport(format: 'pdf' | 'xlsx') {
  if (exporting.value) return
  exporting.value = format
  error.value = ''
  try {
    const token = sessionStorage.getItem('zc_token') || ''
    const termQs = termStore.currentId ? `&termId=${termStore.currentId}` : ''
    const response = await fetch(`/api/export/ranking.${format}?anonymous=0${termQs}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      throw new Error(payload.message || '导出失败')
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `综测排行榜-${new Date().toISOString().slice(0, 10)}.${format}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (err: any) {
    error.value = err.message || '导出失败'
  } finally {
    exporting.value = ''
  }
}

onMounted(loadRanks)
watch(() => termStore.currentId, loadRanks)
useTermRefresh(loadRanks)
</script>

<template>
  <div class="grid">
    <header class="page-header">
      <div>
        <p class="eyebrow">公示与归档</p>
        <h1>公示排名</h1>
        <p class="muted">排名按已通过、公示中和公示结束材料总分降序生成。</p>
      </div>
      <div class="toolbar">
        <button
          v-if="session.role === 'counselor' || session.role === 'teacher'"
          class="button secondary"
          type="button"
          :disabled="Boolean(exporting)"
          @click="downloadExport('xlsx')"
        >
          <FileSpreadsheet :size="16" aria-hidden="true" />
          {{ exporting === 'xlsx' ? '导出中' : '导出 Excel' }}
        </button>
        <button
          v-if="session.role === 'counselor' || session.role === 'teacher'"
          class="button secondary"
          type="button"
          :disabled="Boolean(exporting)"
          @click="downloadExport('pdf')"
        >
          <FileText :size="16" aria-hidden="true" />
          {{ exporting === 'pdf' ? '导出中' : '导出 PDF' }}
        </button>
        <button class="button secondary" type="button" @click="loadRanks">
          <RotateCw :size="16" aria-hidden="true" />
          刷新
        </button>
      </div>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>
    <div v-if="success" class="success-message">{{ success }}</div>
    <div v-if="countdown" class="success-message">{{ countdown }}</div>

    <section v-if="session.role === 'counselor'" class="panel">
      <h2>发起公示</h2>
      <form class="form-grid" @submit.prevent="startPublicity">
        <label class="field">
          <span>公示标题</span>
          <input v-model.trim="form.title" required />
        </label>
        <label class="field">
          <span>班级</span>
          <input v-model.trim="form.className" />
        </label>
        <label class="field">
          <span>公示天数</span>
          <input v-model.number="form.days" type="number" min="1" max="15" />
        </label>
        <button class="button field" type="submit">
          <Megaphone :size="16" aria-hidden="true" />
          {{ confirmPending ? '确认公示' : '发起公示' }}
        </button>
      </form>
    </section>

    <section class="panel">
      <div class="page-header" style="margin-bottom: 12px">
        <h2>排行榜</h2>
        <Trophy :size="22" color="#a56704" aria-hidden="true" />
      </div>
      <div v-if="ranks.length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>排名</th>
              <th>学生</th>
              <th>学号</th>
              <th>班级</th>
              <th>总分</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in ranks" :key="item.rank">
              <td>{{ item.rank }}</td>
              <td>{{ item.student.name }}</td>
              <td>{{ item.student.studentNo }}</td>
              <td>{{ item.student.className || '-' }}</td>
              <td><strong>{{ item.totalScore }}</strong></td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState v-else title="暂无公示排名" />
    </section>

    <section v-if="suggestions.length" class="panel">
      <h2>操作建议</h2>
      <div class="toolbar">
        <span v-for="item in suggestions" :key="item" class="tag primary">{{ item }}</span>
      </div>
    </section>

    <p v-if="session.role === 'student'" class="muted small-tip">
      <Download :size="14" aria-hidden="true" />
      学生个人成绩单请前往【总览】页右上角下载。
    </p>
  </div>
</template>

<style scoped>
.small-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
</style>
