<script setup lang="ts">
import {
  CheckCircle2,
  FileSearch,
  FileText,
  FileUp,
  Image,
  RotateCw,
  SearchCheck,
  UploadCloud,
  X,
} from 'lucide-vue-next'
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { apiFetch, postForm, postJson } from '@/api/client'
import type { Material } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'

interface ParseResult {
  title: string
  category: string
  certificateNo: string
  description: string
  suggestedScore: number
  level: string
  role: string
  reasoning: string
  confidence: 'high' | 'medium' | 'low'
  rawContent: string
  fileName?: string
}

type ParseResponse = {
  data: ParseResult
  message?: string
}

const categories = ['德育', '智育', '体育', '美育', '劳育', '能力']
const today = new Date().toISOString().slice(0, 10)
const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf']
const maxFileSize = 5 * 1024 * 1024

const form = reactive({
  title: '',
  category: '德育',
  description: '',
  certificateNo: '',
  issuedAt: today,
  expiresAt: '',
  fileName: '',
  fileUrl: '',
  score: 1,
})
const materials = ref<Material[]>([])
const error = ref('')
const success = ref('')
const loading = ref(false)
const riskMessage = ref('')
const suggestions = ref<string[]>([])
const parsing = ref(false)
const parsedResult = ref<ParseResult | null>(null)
const isDragging = ref(false)
const uploadError = ref('')
const selectedFile = ref<File | null>(null)
const previewUrl = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

async function loadMaterials() {
  error.value = ''
  try {
    const result = await apiFetch<{ items: Material[] }>('/api/materials/list')
    materials.value = result.items
  } catch (err: any) {
    error.value = err.message || '加载材料失败'
  }
}

async function inspectRisk() {
  riskMessage.value = ''
  error.value = ''
  try {
    const result = await postJson<{ riskLevel: string; riskReasons: string[] }>('/api/risk/inspect', form)
    riskMessage.value = result.riskReasons.length
      ? `${result.riskLevel}: ${result.riskReasons.join('、')}`
      : 'low: 未发现重复或过期风险'
  } catch (err: any) {
    error.value = err.message || '风险检测失败'
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

function handleDragEnter() {
  isDragging.value = true
}

function handleDragLeave(event: DragEvent) {
  if (event.currentTarget === event.target) {
    isDragging.value = false
  }
}

function handleDrop(event: DragEvent) {
  isDragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) {
    uploadAndParse(file)
  }
}

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    uploadAndParse(file)
  }
  input.value = ''
}

function validateFile(file: File): string {
  if (!allowedTypes.includes(file.type)) {
    return '不支持的文件类型，请上传 JPG、PNG、GIF、WebP 或 PDF'
  }
  if (file.size > maxFileSize) {
    return '文件大小超过 5MB 限制'
  }
  return ''
}

async function uploadAndParse(file: File) {
  const validation = validateFile(file)
  uploadError.value = validation
  error.value = ''
  success.value = ''
  if (validation) return

  selectedFile.value = file
  setPreview(file)
  parsing.value = true
  parsedResult.value = null

  const data = new FormData()
  data.append('file', file)
  try {
    const response = await postForm<ParseResponse>('/api/materials/upload-file', data)
    parsedResult.value = response.data
    success.value = response.message || 'AI 解析完成，请核实后提交'
  } catch (err: any) {
    uploadError.value = err.message || '文件解析失败'
  } finally {
    parsing.value = false
  }
}

function setPreview(file: File) {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = file.type.startsWith('image/') ? URL.createObjectURL(file) : ''
}

function applyParsedResult(result: ParseResult) {
  Object.assign(form, {
    title: result.title,
    category: categories.includes(result.category) ? result.category : '能力',
    description: result.description,
    certificateNo: result.certificateNo,
    fileName: result.fileName || selectedFile.value?.name || '',
    fileUrl: '',
    score: result.suggestedScore || 1,
  })
  riskMessage.value = ''
  success.value = 'AI 解析结果已填入表单，请核实后提交'
}

function clearParsedResult() {
  parsedResult.value = null
  selectedFile.value = null
  uploadError.value = ''
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

onBeforeUnmount(() => {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
})

async function upload() {
  error.value = ''
  success.value = ''
  loading.value = true
  try {
    const result = await postJson<{ message?: string; suggestions?: string[] }>('/api/materials/upload', form)
    success.value = result.message || '材料已提交，状态进入[已提交]'
    suggestions.value = result.suggestions || []
    Object.assign(form, {
      title: '',
      category: '德育',
      description: '',
      certificateNo: '',
      issuedAt: today,
      expiresAt: '',
      fileName: '',
      fileUrl: '',
      score: 1,
    })
    clearParsedResult()
    await loadMaterials()
  } catch (err: any) {
    error.value = err.message || '上传失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadMaterials)
</script>

<template>
  <div class="grid">
    <header class="page-header">
      <div>
        <p class="eyebrow">学生端</p>
        <h1>材料上传</h1>
        <p class="muted">提交后进入审核流，公示阶段材料会自动锁定。</p>
      </div>
      <button class="button secondary" type="button" @click="loadMaterials">
        <RotateCw :size="16" aria-hidden="true" />
        刷新
      </button>
    </header>

    <section class="panel">
      <h2>新增材料</h2>
      <div
        class="dropzone"
        :class="{ dragging: isDragging, 'has-file': selectedFile }"
        role="button"
        tabindex="0"
        @click="openFilePicker"
        @keydown.enter.prevent="openFilePicker"
        @keydown.space.prevent="openFilePicker"
        @dragenter.prevent="handleDragEnter"
        @dragover.prevent
        @dragleave.prevent="handleDragLeave"
        @drop.prevent="handleDrop"
      >
        <input
          ref="fileInput"
          class="sr-only"
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
          @change="handleFileSelect"
        />
        <div class="dropzone-main">
          <span class="dropzone-icon">
            <UploadCloud v-if="!selectedFile" :size="26" aria-hidden="true" />
            <Image v-else-if="selectedFile.type.startsWith('image/')" :size="26" aria-hidden="true" />
            <FileText v-else :size="26" aria-hidden="true" />
          </span>
          <div>
            <strong>{{ selectedFile ? selectedFile.name : '拖拽图片或 PDF 到此处，或点击选择文件' }}</strong>
            <p class="muted">支持 JPG、PNG、GIF、WebP、PDF，最大 5MB</p>
          </div>
        </div>
        <div v-if="previewUrl" class="file-preview">
          <img :src="previewUrl" alt="材料预览" />
        </div>
        <div v-if="parsing" class="parse-progress">
          <span></span>
        </div>
      </div>

      <div v-if="uploadError" class="alert upload-alert">{{ uploadError }}</div>

      <article v-if="parsedResult" class="parse-result">
        <div class="parse-result-header">
          <CheckCircle2 :size="20" color="#16805a" aria-hidden="true" />
          <div>
            <h3>AI 解析结果</h3>
            <p class="muted">仅供参考，请核实后提交</p>
          </div>
          <span class="tag" :class="parsedResult.confidence === 'high' ? 'success' : parsedResult.confidence === 'low' ? 'danger' : 'warning'">
            {{ parsedResult.confidence }}
          </span>
        </div>
        <div class="parse-grid">
          <div>
            <span class="muted">标题</span>
            <strong>{{ parsedResult.title }}</strong>
          </div>
          <div>
            <span class="muted">类别</span>
            <strong>{{ parsedResult.category }}</strong>
          </div>
          <div>
            <span class="muted">建议分</span>
            <strong>{{ parsedResult.suggestedScore }}</strong>
          </div>
          <div>
            <span class="muted">级别</span>
            <strong>{{ parsedResult.level }}</strong>
          </div>
          <div>
            <span class="muted">角色</span>
            <strong>{{ parsedResult.role }}</strong>
          </div>
          <div>
            <span class="muted">证书号</span>
            <strong>{{ parsedResult.certificateNo || '未识别' }}</strong>
          </div>
        </div>
        <p class="parse-text">{{ parsedResult.description }}</p>
        <p class="parse-text"><FileSearch :size="16" aria-hidden="true" />{{ parsedResult.reasoning }}</p>
        <details class="raw-content">
          <summary>识别原文</summary>
          <pre>{{ parsedResult.rawContent }}</pre>
        </details>
        <div class="toolbar">
          <button class="button secondary" type="button" @click="applyParsedResult(parsedResult)">
            <CheckCircle2 :size="16" aria-hidden="true" />
            应用结果
          </button>
          <button class="button secondary" type="button" @click="clearParsedResult">
            <X :size="16" aria-hidden="true" />
            清除结果
          </button>
        </div>
      </article>

      <form class="form-grid" @submit.prevent="upload">
        <label class="field">
          <span>材料标题</span>
          <input v-model.trim="form.title" required />
        </label>
        <label class="field">
          <span>五育类别</span>
          <select v-model="form.category">
            <option v-for="item in categories" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label class="field">
          <span>证书编号</span>
          <input v-model.trim="form.certificateNo" required />
          <small class="field-tip">Tips：没有编号可填写无</small>
        </label>
        <label class="field">
          <span>建议分</span>
          <input v-model.number="form.score" type="number" min="0" step="0.5" required />
        </label>
        <label class="field">
          <span>发证日期</span>
          <input v-model="form.issuedAt" type="date" required />
        </label>
        <label class="field">
          <span>有效期至</span>
          <input v-model="form.expiresAt" type="date" />
        </label>
        <label class="field">
          <span>文件名</span>
          <input v-model.trim="form.fileName" placeholder="certificate.pdf" />
        </label>
        <label class="field">
          <span>文件地址</span>
          <input v-model.trim="form.fileUrl" placeholder="https://..." />
        </label>
        <label class="field full">
          <span>说明</span>
          <textarea v-model.trim="form.description" />
        </label>
        <div v-if="error" class="alert field full">{{ error }}</div>
        <div v-if="success" class="success-message field full">{{ success }}</div>
        <div v-if="riskMessage" class="success-message field full">{{ riskMessage }}</div>
        <div v-if="suggestions.length" class="field full toolbar">
          <span v-for="item in suggestions" :key="item" class="tag primary">{{ item }}</span>
        </div>
        <div class="toolbar field full">
          <button class="button secondary" type="button" @click="inspectRisk">
            <SearchCheck :size="16" aria-hidden="true" />
            风险检测
          </button>
          <button class="button" type="submit" :disabled="loading">
            <FileUp :size="16" aria-hidden="true" />
            {{ loading ? '提交中' : '提交材料' }}
          </button>
        </div>
      </form>
    </section>

    <section class="panel">
      <h2>材料列表</h2>
      <div v-if="materials.length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>材料</th>
              <th>五育</th>
              <th>分数</th>
              <th>状态</th>
              <th>风险</th>
              <th>OCR</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in materials" :key="item.id">
              <td>
                <strong>{{ item.title }}</strong>
                <div class="muted">{{ item.certificateNo }}</div>
              </td>
              <td>{{ item.category }}</td>
              <td>{{ item.score }}</td>
              <td><StatusTag :value="item.status" /></td>
              <td>{{ item.riskReasons.length ? item.riskReasons.join('、') : 'low' }}</td>
              <td>{{ item.ocrText }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState v-else title="暂无材料" />
    </section>
  </div>
</template>

<style scoped>
.dropzone {
  position: relative;
  display: grid;
  gap: 14px;
  min-height: 160px;
  margin-bottom: 16px;
  padding: 24px;
  border: 2px dashed #c7d0df;
  border-radius: 8px;
  background: #fbfcff;
  cursor: pointer;
  transition:
    border-color 0.2s,
    background 0.2s;
}

.dropzone:hover,
.dropzone.dragging {
  border-color: var(--primary);
  background: #f8fafc;
}

.dropzone.has-file {
  border-style: solid;
  border-color: var(--success);
}

.dropzone-main {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  text-align: left;
}

.dropzone-main p {
  margin: 4px 0 0;
}

.dropzone-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: var(--primary);
  background: var(--primary-weak);
}

.file-preview {
  width: min(360px, 100%);
  margin: 0 auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  background: #ffffff;
}

.file-preview img {
  display: block;
  width: 100%;
  max-height: 220px;
  object-fit: contain;
}

.parse-progress {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 14px;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: #e6ebf3;
}

.parse-progress span {
  display: block;
  width: 42%;
  height: 100%;
  border-radius: inherit;
  background: var(--primary);
  animation: parse-progress 1.1s ease-in-out infinite;
}

.upload-alert {
  margin-bottom: 16px;
}

.parse-result {
  display: grid;
  gap: 14px;
  margin-bottom: 18px;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
}

.parse-result-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
}

.parse-result-header h3,
.parse-result-header p {
  margin: 0;
}

.parse-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.parse-grid div {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #f8fafc;
}

.parse-grid span,
.parse-grid strong {
  display: block;
}

.parse-grid strong {
  margin-top: 2px;
  overflow-wrap: anywhere;
}

.parse-text {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  color: #3c485c;
}

.raw-content {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #f8fafc;
}

.raw-content summary {
  padding: 10px 12px;
  cursor: pointer;
  font-weight: 650;
}

.raw-content pre {
  max-height: 220px;
  margin: 0;
  padding: 0 12px 12px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  color: #3c485c;
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

@keyframes parse-progress {
  0% {
    transform: translateX(-110%);
  }

  100% {
    transform: translateX(260%);
  }
}

@media (max-width: 720px) {
  .dropzone-main {
    flex-direction: column;
    text-align: center;
  }

  .parse-result-header,
  .parse-grid {
    grid-template-columns: 1fr;
  }
}

.field-tip {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
}
</style>
