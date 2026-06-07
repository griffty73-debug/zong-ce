<script setup lang="ts">
import { CheckCircle2, Paperclip, RotateCw, Send, Upload, X, XCircle } from 'lucide-vue-next'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { apiFetch, postForm, postJson } from '@/api/client'
import type { Appeal, Material } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTermRefresh } from '@/composables/useTermRefresh'
import { useSessionStore } from '@/stores/session'
import { useTermStore } from '@/stores/term'

type EvidenceFile = { name: string; url: string }

const session = useSessionStore()
const termStore = useTermStore()
const appeals = ref<Appeal[]>([])
const materials = ref<Material[]>([])
const error = ref('')
const success = ref('')
const loading = ref(false)
const suggestions = ref<string[]>([])
const submitForm = reactive({
  materialId: '',
  reason: '',
  files: [] as EvidenceFile[],
})
const resolveForm = reactive<Record<number, { opinion: string }>>({})
const fileInput = ref<HTMLInputElement | null>(null)
const evidenceUploading = ref(false)

const publicizingMaterials = computed(() =>
  materials.value.filter((item) => item.status === '公示中'),
)

async function load() {
  error.value = ''
  loading.value = true
  try {
    const qs = termStore.currentId ? `?termId=${termStore.currentId}` : ''
    const appealResult = await apiFetch<{ items: Appeal[] }>(`/api/appeal/list${qs}`)
    appeals.value = appealResult.items
    if (session.role === 'student') {
      const materialResult = await apiFetch<{ items: Material[] }>(`/api/materials/list${qs}`)
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
      evidenceFiles: submitForm.files,
    })
    success.value = result.message || '申诉已提交，材料状态进入[申诉处理中]'
    suggestions.value = result.suggestions || []
    submitForm.materialId = ''
    submitForm.reason = ''
    submitForm.files = []
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

function openEvidencePicker() {
  fileInput.value?.click()
}

async function handleEvidenceSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return
  evidenceUploading.value = true
  error.value = ''
  try {
    for (const file of Array.from(files)) {
      const data = new FormData()
      data.append('file', file)
      const result = await postForm<{ data: EvidenceFile }>('/api/appeal/upload-file', data)
      submitForm.files.push(result.data)
    }
  } catch (err: any) {
    error.value = err.message || '证据上传失败'
  } finally {
    evidenceUploading.value = false
    input.value = ''
  }
}

function removeEvidence(index: number) {
  submitForm.files.splice(index, 1)
}

onMounted(load)
watch(() => termStore.currentId, load)
useTermRefresh(load)
</script>

<template>
  <div class="grid">
    <header class="page-header">
      <div>
        <p class="eyebrow">{{ session.role === 'student' ? '学生端' : '辅导员端' }}</p>
        <h1>{{ session.role === 'student' ? '我的申诉' : '申诉处理' }}</h1>
        <p class="muted">申诉只在[公示中]材料上生效，可附图佐证。</p>
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
        <div class="field full">
          <span>证据附件</span>
          <div class="evidence-zone">
            <button
              class="button secondary"
              type="button"
              :disabled="evidenceUploading"
              @click="openEvidencePicker"
            >
              <Upload :size="16" aria-hidden="true" />
              {{ evidenceUploading ? '上传中' : '添加证据' }}
            </button>
            <input
              ref="fileInput"
              class="sr-only"
              type="file"
              accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
              multiple
              @change="handleEvidenceSelect"
            />
            <ul v-if="submitForm.files.length" class="evidence-list">
              <li v-for="(file, index) in submitForm.files" :key="file.url">
                <Paperclip :size="14" aria-hidden="true" />
                <a :href="file.url" target="_blank" rel="noopener">{{ file.name }}</a>
                <button class="icon-button" type="button" aria-label="移除" @click="removeEvidence(index)">
                  <X :size="14" aria-hidden="true" />
                </button>
              </li>
            </ul>
            <span v-else class="muted">支持 JPG/PNG/GIF/WebP/PDF，最多 5MB / 个</span>
          </div>
        </div>
        <button class="button field full" type="submit">
          <Send :size="16" aria-hidden="true" />
          提交申诉
        </button>
      </form>
    </section>

    <section class="panel">
      <h2>申诉列表</h2>
      <div v-if="appeals.length" class="grid appeal-list">
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
.appeal-list {
  padding-right: 2px;
}

.evidence-zone {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px dashed var(--line);
  border-radius: var(--radius);
  background: var(--surface-muted);
}

.evidence-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
}

.evidence-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  font-size: 13px;
}

.evidence-list a {
  color: var(--primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
