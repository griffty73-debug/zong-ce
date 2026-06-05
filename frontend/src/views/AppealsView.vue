<script setup lang="ts">
import { CheckCircle2, RotateCw, Send, XCircle } from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'

import { apiFetch, postJson } from '@/api/client'
import type { Appeal, Material } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import MotionCaptureControl from '@/components/MotionCaptureControl.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const appeals = ref<Appeal[]>([])
const materials = ref<Material[]>([])
const error = ref('')
const success = ref('')
const loading = ref(false)
const suggestions = ref<string[]>([])
const appealPageIndex = ref(1)
const appealPageSize = 5
const appealListRef = ref<HTMLDivElement | null>(null)
const submitForm = reactive({
  materialId: '',
  reason: '',
})
const resolveForm = reactive<Record<number, { opinion: string }>>({})

const publicizingMaterials = computed(() =>
  materials.value.filter((item) => item.status === '公示中'),
)

type MotionPayload = {
  response: {
    uiFeedback: { level: string; message: string }
    data: {
      items?: Appeal[]
      pageIndex?: number
      scrollDirection?: 'up' | 'down'
    }
  }
}

async function load() {
  error.value = ''
  loading.value = true
  try {
    const appealResult = await apiFetch<{ items: Appeal[] }>('/api/appeal/list')
    appeals.value = appealResult.items
    appealPageIndex.value = 1
    if (session.role === 'student') {
      const materialResult = await apiFetch<{ items: Material[] }>('/api/materials/list')
      materials.value = materialResult.items
    }
  } catch (err: any) {
    error.value = err.message || '加载申诉失败'
  } finally {
    loading.value = false
  }
}

async function submitAppeal() {
  error.value = ''
  success.value = ''
  try {
    const result = await postJson<{ message?: string; suggestions?: string[] }>('/api/appeal/submit', {
      materialId: Number(submitForm.materialId),
      reason: submitForm.reason,
    })
    success.value = result.message || '申诉已提交，材料状态进入[申诉处理中]'
    suggestions.value = result.suggestions || []
    submitForm.materialId = ''
    submitForm.reason = ''
    await load()
  } catch (err: any) {
    error.value = err.message || '提交申诉失败'
  }
}

async function resolveAppeal(appealId: number, action: 'accept' | 'reject') {
  error.value = ''
  success.value = ''
  try {
    const result = await postJson<{ message?: string; suggestions?: string[] }>('/api/appeal/resolve', {
      appealId,
      action,
      opinion: resolveForm[appealId]?.opinion || '',
    })
    success.value = result.message || (action === 'accept' ? '复核通过，材料回到公示中' : '复核驳回，材料进入公示结束')
    suggestions.value = result.suggestions || []
    await load()
  } catch (err: any) {
    error.value = err.message || '处理申诉失败'
  }
}

function ensureResolveForm(appealId: number) {
  resolveForm[appealId] ||= { opinion: '' }
  return resolveForm[appealId]
}

function handleAppealMotion(payload: MotionPayload) {
  const { data, uiFeedback } = payload.response
  if (Array.isArray(data.items)) {
    appeals.value = data.items
  }
  if (typeof data.pageIndex === 'number') {
    appealPageIndex.value = data.pageIndex
  }
  if (data.scrollDirection) {
    appealListRef.value?.scrollBy({
      top: data.scrollDirection === 'up' ? -220 : 220,
      behavior: 'smooth',
    })
  }
  error.value = uiFeedback.level === 'warning' ? uiFeedback.message : ''
  success.value = uiFeedback.level === 'warning' ? '' : uiFeedback.message
}

onMounted(load)
</script>

<template>
  <div class="grid">
    <header class="page-header">
      <div>
        <p class="eyebrow">{{ session.role === 'student' ? '学生端' : '辅导员端' }}</p>
        <h1>{{ session.role === 'student' ? '我的申诉' : '申诉处理' }}</h1>
        <p class="muted">申诉只在[公示中]材料上生效。</p>
      </div>
      <button class="button secondary" type="button" @click="load">
        <RotateCw :size="16" aria-hidden="true" />
        刷新
      </button>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>
    <div v-if="success" class="success-message">{{ success }}</div>
    <div v-if="suggestions.length" class="panel toolbar">
      <span v-for="item in suggestions" :key="item" class="tag primary">{{ item }}</span>
    </div>

    <section v-if="session.role === 'student'" class="panel">
      <h2>提交申诉</h2>
      <form class="form-grid" @submit.prevent="submitAppeal">
        <label class="field">
          <span>公示中材料</span>
          <select v-model="submitForm.materialId" required>
            <option value="" disabled>选择材料</option>
            <option v-for="item in publicizingMaterials" :key="item.id" :value="String(item.id)">
              {{ item.title }} · {{ item.score }}分
            </option>
          </select>
        </label>
        <label class="field full">
          <span>申诉原因</span>
          <textarea v-model.trim="submitForm.reason" required />
        </label>
        <button class="button field full" type="submit">
          <Send :size="16" aria-hidden="true" />
          提交申诉
        </button>
      </form>
    </section>

    <section class="panel">
      <h2>申诉列表</h2>
      <MotionCaptureControl
        v-if="appeals.length"
        class="motion-inline"
        page="appeal"
        :page-index="appealPageIndex"
        :page-size="appealPageSize"
        @captured="handleAppealMotion"
      />
      <div v-if="appeals.length" ref="appealListRef" class="grid appeal-list">
        <article v-for="appeal in appeals" :key="appeal.id" class="card">
          <div class="page-header" style="margin-bottom: 10px">
            <div>
              <h3>{{ appeal.material.title }}</h3>
              <p class="muted">{{ appeal.student.name }} · {{ appeal.material.certificateNo }}</p>
            </div>
            <StatusTag :value="appeal.status" />
          </div>
          <p><strong>申诉原因：</strong>{{ appeal.reason }}</p>
          <p v-if="appeal.resultOpinion"><strong>复核意见：</strong>{{ appeal.resultOpinion }}</p>
          <div v-if="session.role !== 'student' && appeal.status === '待处理'" class="grid">
            <label class="field">
              <span>复核意见</span>
              <textarea v-model.trim="ensureResolveForm(appeal.id).opinion" />
            </label>
            <div class="toolbar">
              <button class="button" type="button" @click="resolveAppeal(appeal.id, 'accept')">
                <CheckCircle2 :size="16" aria-hidden="true" />
                通过
              </button>
              <button class="button danger" type="button" @click="resolveAppeal(appeal.id, 'reject')">
                <XCircle :size="16" aria-hidden="true" />
                驳回
              </button>
            </div>
          </div>
        </article>
      </div>
      <EmptyState v-else title="暂无申诉" />
    </section>
  </div>
</template>

<style scoped>
.motion-inline {
  margin-bottom: 12px;
}

.appeal-list {
  max-height: 560px;
  overflow: auto;
  padding-right: 2px;
}
</style>
