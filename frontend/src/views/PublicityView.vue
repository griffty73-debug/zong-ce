<script setup lang="ts">
import { Megaphone, RotateCw, Trophy } from 'lucide-vue-next'
import { onMounted, reactive, ref } from 'vue'

import { apiFetch, postJson } from '@/api/client'
import type { RankItem } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import MotionCaptureControl from '@/components/MotionCaptureControl.vue'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const ranks = ref<RankItem[]>([])
const error = ref('')
const success = ref('')
const loading = ref(false)
const confirmPending = ref(false)
const suggestions = ref<string[]>([])
const countdown = ref('')
const pageIndex = ref(1)
const pageSize = 8
const totalRanks = ref(0)
const tableWrapRef = ref<HTMLDivElement | null>(null)
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

type MotionPayload = {
  direction: 'up' | 'down' | 'left' | 'right'
  response: {
    uiFeedback: { level: string; message: string }
    data: {
      items?: RankItem[]
      pageIndex?: number
      total?: number
      scrollDirection?: 'up' | 'down'
    }
  }
}

async function loadRanks() {
  error.value = ''
  loading.value = true
  try {
    const anonymous = session.role === 'student' ? '1' : '0'
    const result = await apiFetch<PublicityResponse>(`/api/publicity/rank?anonymous=${anonymous}`)
    ranks.value = result.items || []
    pageIndex.value = 1
    totalRanks.value = ranks.value.length
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
    const result = await postJson<PublicityResponse>('/api/publicity/start', {
      ...form,
      confirm: confirmPending.value ? '确认公示' : undefined,
    })
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

function handleMotionCaptured(payload: MotionPayload) {
  const { data, uiFeedback } = payload.response
  if (Array.isArray(data.items)) {
    ranks.value = data.items
  }
  if (typeof data.pageIndex === 'number') {
    pageIndex.value = data.pageIndex
  }
  if (typeof data.total === 'number') {
    totalRanks.value = data.total
  }
  if (data.scrollDirection) {
    tableWrapRef.value?.scrollBy({
      top: data.scrollDirection === 'up' ? -220 : 220,
      behavior: 'smooth',
    })
  }
  error.value = uiFeedback.level === 'warning' ? uiFeedback.message : ''
  success.value = uiFeedback.level === 'warning' ? '' : uiFeedback.message
}

onMounted(loadRanks)
</script>

<template>
  <div class="grid">
    <header class="page-header">
      <div>
        <p class="eyebrow">公示与归档</p>
        <h1>公示排名</h1>
        <p class="muted">排名按已通过、公示中和公示结束材料总分降序生成。</p>
      </div>
      <button class="button secondary" type="button" @click="loadRanks">
        <RotateCw :size="16" aria-hidden="true" />
        刷新
      </button>
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
      <MotionCaptureControl
        v-if="session.role === 'student'"
        class="motion-inline"
        page="publicity"
        :page-index="pageIndex"
        :page-size="pageSize"
        :context="{ total: totalRanks }"
        @captured="handleMotionCaptured"
      />
      <div v-if="ranks.length" ref="tableWrapRef" class="table-wrap motion-table">
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
  </div>
</template>

<style scoped>
.motion-inline {
  margin-bottom: 12px;
}

.motion-table {
  max-height: 520px;
}
</style>
