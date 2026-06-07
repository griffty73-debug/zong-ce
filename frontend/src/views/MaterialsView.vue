<script setup lang="ts">
import {
  CheckCircle2,
  FileSearch,
  FileText,
  FileUp,
  Image as ImageIcon,
  RotateCw,
  Scale,
  SearchCheck,
  Sparkles,
  UploadCloud,
  X,
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import { apiFetch, postForm, postJson } from '@/api/client'
import type { Material } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTermRefresh } from '@/composables/useTermRefresh'
import { useTermStore } from '@/stores/term'

type RegionLabel = 'title' | 'certificateNo' | 'issuer'

interface Region {
  label: RegionLabel
  text: string
  box: [number, number, number, number]
  confidence: number
}

interface ScoreBasis {
  category: string
  ruleName: string
  level: string
  role: string
  rawScore: number
  score: number
  cap: number | null
  ruleKey: string
  eventKey: string | null
  reasons: string[]
  confidence: string
  citation: string
}

interface ParseResult {
  title: string
  category: string
  certificateNo: string
  issuer?: string
  description: string
  suggestedScore: number
  level: string
  role: string
  reasoning: string
  confidence: 'high' | 'medium' | 'low'
  rawContent: string
  fileName?: string
  regions?: Region[]
  scoreBasis?: ScoreBasis | null
}

type ParseResponse = {
  data: ParseResult
  message?: string
}

const categories = ['德育', '智育', '体育', '美育', '劳育', '能力']
const today = new Date().toISOString().slice(0, 10)
const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf']
const maxFileSize = 5 * 1024 * 1024
const termStore = useTermStore()

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
const imageNaturalSize = ref<{ width: number; height: number } | null>(null)

const regionColors: Record<RegionLabel, { stroke: string; fill: string; label: string }> = {
  title: { stroke: '#dc2626', fill: 'rgba(220, 38, 38, 0.10)', label: '奖项名称' },
  certificateNo: { stroke: '#2563eb', fill: 'rgba(37, 99, 235, 0.10)', label: '证书编号' },
  issuer: { stroke: '#7c3aed', fill: 'rgba(124, 58, 237, 0.10)', label: '颁奖机构' },
}

const hasRegions = computed(() => Boolean(parsedResult.value?.regions?.length))
const hasScoreBasis = computed(() => Boolean(parsedResult.value?.scoreBasis))
const stageAspectRatio = computed(() => {
  const size = imageNaturalSize.value
  if (!size || !size.width || !size.height) return '4 / 3'
  return `${size.width} / ${size.height}`
})

async function loadMaterials() {
  error.value = ''
  try {
    const qs = termStore.currentId ? `?termId=${termStore.currentId}` : ''
    const result = await apiFetch<{ items: Material[] }>(`/api/materials/list${qs}`)
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
  imageNaturalSize.value = null
  previewUrl.value = file.type.startsWith('image/') ? URL.createObjectURL(file) : ''
}

function onPreviewLoad(event: Event) {
  const img = event.target as HTMLImageElement
  if (img.naturalWidth && img.naturalHeight) {
    imageNaturalSize.value = { width: img.naturalWidth, height: img.naturalHeight }
  }
}

function clearImageNaturalSize() {
  imageNaturalSize.value = null
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
  clearImageNaturalSize()
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
    const payload = { ...form }
    if (termStore.currentId) payload.termId = termStore.currentId
    const result = await postJson<{ message?: string; suggestions?: string[] }>('/api/materials/upload', payload)
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
watch(() => termStore.currentId, loadMaterials)
useTermRefresh(loadMaterials)
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
            <ImageIcon v-else-if="selectedFile.type.startsWith('image/')" :size="26" aria-hidden="true" />
            <FileText v-else :size="26" aria-hidden="true" />
          </span>
          <div>
            <strong>{{ selectedFile ? selectedFile.name : '拖拽图片或 PDF 到此处，或点击选择文件' }}</strong>
            <p class="muted">支持 JPG、PNG、GIF、WebP、PDF，最大 5MB</p>
          </div>
        </div>
        <div v-if="previewUrl" class="file-preview">
          <div class="image-stage" :style="{ aspectRatio: stageAspectRatio }">
            <img :src="previewUrl" alt="材料预览" @load="onPreviewLoad" />
            <svg
              v-if="hasRegions"
              class="image-overlay"
              viewBox="0 0 1 1"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <g v-for="(region, idx) in parsedResult?.regions || []" :key="`${region.label}-${idx}`">
                <rect
                  :x="region.box[0]"
                  :y="region.box[1]"
                  :width="Math.max(region.box[2] - region.box[0], 0.005)"
                  :height="Math.max(region.box[3] - region.box[1], 0.005)"
                  :stroke="regionColors[region.label].stroke"
                  :fill="regionColors[region.label].fill"
                  stroke-width="0.004"
                  vector-effect="non-scaling-stroke"
                />
                <line
                  :x1="(region.box[0] + region.box[2]) / 2"
                  :y1="(region.box[1] + region.box[3]) / 2"
                  :x2="1.02"
                  :y2="region.box[1] + 0.012 + idx * 0.06"
                  :stroke="regionColors[region.label].stroke"
                  stroke-width="0.003"
                  vector-effect="non-scaling-stroke"
                />
              </g>
            </svg>
            <ul v-if="hasRegions" class="region-labels">
              <li
                v-for="(region, idx) in parsedResult?.regions || []"
                :key="`lbl-${region.label}-${idx}`"
                :style="{
                  top: `${(region.box[1] + (region.box[3] - region.box[1]) / 2) * 100}%`,
                  '--swatch': regionColors[region.label].stroke,
                }"
              >
                <span class="region-tag">{{ regionColors[region.label].label }}</span>
                <strong>{{ region.text }}</strong>
                <span class="region-confidence">置信度 {{ Math.round(region.confidence * 100) }}%</span>
              </li>
            </ul>
          </div>
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
        <div class="parse-result-body">
          <div class="parse-result-main">
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
              <div v-if="parsedResult.issuer" class="span-3">
                <span class="muted">颁奖机构</span>
                <strong>{{ parsedResult.issuer }}</strong>
              </div>
            </div>
            <p class="parse-text">{{ parsedResult.description }}</p>
            <p class="parse-text"><FileSearch :size="16" aria-hidden="true" />{{ parsedResult.reasoning }}</p>
            <ul v-if="hasRegions" class="region-legend">
              <li
                v-for="region in parsedResult.regions"
                :key="`legend-${region.label}-${region.text}`"
                :style="{ '--swatch': regionColors[region.label].stroke }"
              >
                <span class="region-tag">{{ regionColors[region.label].label }}</span>
                <span class="muted">·</span>
                <strong>{{ region.text }}</strong>
                <span class="region-confidence">置信度 {{ Math.round(region.confidence * 100) }}%</span>
              </li>
            </ul>
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
          </div>

          <aside v-if="hasScoreBasis" class="score-basis">
            <header class="score-basis-header">
              <Sparkles :size="18" color="#7c3aed" aria-hidden="true" />
              <h3>打分依据</h3>
            </header>
            <div class="score-basis-hero">
              <Scale :size="16" aria-hidden="true" />
              <span class="score-formula">
                <strong>{{ parsedResult.scoreBasis!.level }} · {{ parsedResult.scoreBasis!.ruleName }}</strong>
                <span class="score-arrow" aria-hidden="true">→</span>
                <span class="score-final">{{ parsedResult.scoreBasis!.score }} 分</span>
              </span>
            </div>
            <p class="score-basis-citation">
              <em>依据：</em>{{ parsedResult.scoreBasis!.citation }}
            </p>
            <dl class="score-basis-grid">
              <div>
                <dt>分类</dt>
                <dd>{{ parsedResult.scoreBasis!.category }}</dd>
              </div>
              <div>
                <dt>级别</dt>
                <dd>{{ parsedResult.scoreBasis!.level }}</dd>
              </div>
              <div>
                <dt>角色</dt>
                <dd>{{ parsedResult.scoreBasis!.role }}</dd>
              </div>
              <div>
                <dt>基础分</dt>
                <dd>{{ parsedResult.scoreBasis!.rawScore }}</dd>
              </div>
              <div>
                <dt>单项上限</dt>
                <dd>{{ parsedResult.scoreBasis!.cap ?? '不限' }}</dd>
              </div>
              <div>
                <dt>匹配度</dt>
                <dd>{{ parsedResult.scoreBasis!.confidence }}</dd>
              </div>
            </dl>
            <p v-if="parsedResult.scoreBasis!.eventKey" class="score-basis-event">
              赛事指纹：<code>{{ parsedResult.scoreBasis!.eventKey }}</code>
            </p>
            <div v-if="parsedResult.scoreBasis!.reasons.length" class="score-basis-reasons">
              <h4>细则说明</h4>
              <ul>
                <li v-for="(reason, idx) in parsedResult.scoreBasis!.reasons" :key="idx">{{ reason }}</li>
              </ul>
            </div>
            <p v-else class="score-basis-tip">
              已按当前分类细则与赛事指纹自动匹配，同赛事仅取最高项。
            </p>
          </aside>
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
  width: min(560px, 100%);
  margin: 0 auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  background: #0f172a;
}

.image-stage {
  position: relative;
  width: 100%;
  background: #0f172a;
}

.image-stage img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: fill;
  user-select: none;
  -webkit-user-drag: none;
}

.image-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.region-labels {
  position: absolute;
  inset: 0;
  margin: 0;
  padding: 0;
  list-style: none;
  pointer-events: none;
}

.region-labels li {
  position: absolute;
  right: -8px;
  transform: translate(100%, -50%);
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 140px;
  max-width: 200px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #ffffff;
  border-left: 4px solid var(--swatch, #2663eb);
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.18);
  font-size: 12px;
  line-height: 1.35;
  color: #1f2937;
}

.region-labels li strong {
  font-weight: 600;
  overflow-wrap: anywhere;
  color: #0f172a;
}

.region-tag {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: #ffffff;
  background: var(--swatch, #2663eb);
  letter-spacing: 0.02em;
}

.region-confidence {
  font-size: 11px;
  color: #6b7280;
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

.parse-result-body {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.parse-result-main {
  display: grid;
  gap: 14px;
  min-width: 0;
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

.parse-grid .span-3 {
  grid-column: 1 / -1;
}

.region-legend {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.region-legend li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #f8fafc;
  border-left: 3px solid var(--swatch, #2663eb);
  font-size: 13px;
}

.score-basis {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid #e9d5ff;
  border-radius: 10px;
  background: linear-gradient(180deg, #faf5ff 0%, #f5f3ff 100%);
  min-width: 0;
}

.score-basis-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.score-basis-header h3 {
  margin: 0;
  font-size: 15px;
  color: #5b21b6;
}

.score-basis-hero {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #ffffff;
  border-radius: 8px;
  color: #1e293b;
}

.score-formula {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 14px;
}

.score-arrow {
  color: #7c3aed;
  font-weight: 700;
}

.score-final {
  font-weight: 700;
  font-size: 18px;
  color: #7c3aed;
}

.score-basis-citation {
  margin: 0;
  font-size: 13px;
  color: #334155;
  line-height: 1.5;
}

.score-basis-citation em {
  color: #7c3aed;
  font-style: normal;
  font-weight: 600;
  margin-right: 4px;
}

.score-basis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.score-basis-grid div {
  padding: 8px 10px;
  background: #ffffff;
  border-radius: 6px;
}

.score-basis-grid dt {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.score-basis-grid dd {
  margin: 2px 0 0;
  font-size: 13px;
  color: #1f2937;
  font-weight: 600;
}

.score-basis-event {
  margin: 0;
  font-size: 12px;
  color: #475569;
  word-break: break-all;
}

.score-basis-event code {
  font-size: 12px;
  background: rgba(124, 58, 237, 0.08);
  padding: 1px 4px;
  border-radius: 4px;
  color: #5b21b6;
}

.score-basis-reasons h4 {
  margin: 0 0 4px;
  font-size: 12px;
  color: #5b21b6;
}

.score-basis-reasons ul {
  margin: 0;
  padding-left: 18px;
  color: #334155;
  font-size: 12px;
  line-height: 1.55;
}

.score-basis-tip {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
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

@media (max-width: 960px) {
  .parse-result-body {
    grid-template-columns: 1fr;
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

  .region-labels li {
    position: static;
    transform: none;
    margin-top: 6px;
  }

  .region-labels {
    position: static;
    margin-top: 10px;
    display: grid;
    gap: 6px;
  }
}

.field-tip {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #94a3b8;
}
</style>
