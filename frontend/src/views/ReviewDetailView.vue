<script setup lang="ts">
import { CheckCircle2, Download, FileText, RotateCw, XCircle } from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { apiFetch, postJson } from '@/api/client'
import type { Material, ReviewRecord } from '@/api/types'
import StatusTag from '@/components/StatusTag.vue'

const route = useRoute()
const router = useRouter()
const material = ref<Material | null>(null)
const reviews = ref<ReviewRecord[]>([])
const error = ref('')
const success = ref('')
const loading = ref(false)
const form = reactive({
  opinion: '',
  scoreDelta: 0,
})

const materialId = computed(() => Number(route.params.id))

const fileExt = computed(() => {
  const source = material.value?.fileUrl || material.value?.fileName || ''
  const match = source.toLowerCase().match(/\.([a-z0-9]+)(?:$|\?)/)
  return match ? match[1] : ''
})

const isImage = computed(() => ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].includes(fileExt.value))
const isPdf = computed(() => fileExt.value === 'pdf')

async function load() {
  error.value = ''
  try {
    const result = await apiFetch<{ material: Material; reviews: ReviewRecord[] }>(
      `/api/review/detail/${materialId.value}`,
    )
    material.value = result.material
    reviews.value = result.reviews
  } catch (err: any) {
    error.value = err.message || '加载审核详情失败'
  }
}

async function act(action: 'pass' | 'reject') {
  error.value = ''
  success.value = ''
  loading.value = true
  try {
    await postJson('/api/review/action', {
      materialId: materialId.value,
      action,
      opinion: form.opinion,
      scoreDelta: form.scoreDelta,
    })
    success.value = action === 'pass' ? '审核通过' : '已打回'
    await load()
  } catch (err: any) {
    error.value = err.message || '审核操作失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="grid">
    <header class="page-header">
      <div>
        <p class="eyebrow">审核详情</p>
        <h1>{{ material?.title || '材料详情' }}</h1>
        <p class="muted">{{ material?.student?.name }} · {{ material?.certificateNo }}</p>
      </div>
      <button class="button secondary" type="button" @click="router.push('/review')">
        返回列表
      </button>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>
    <div v-if="success" class="success-message">{{ success }}</div>

    <section v-if="material" class="grid cols-2">
      <article class="panel">
        <h2>材料信息</h2>
        <div class="grid">
          <p><strong>状态：</strong><StatusTag :value="material.status" /></p>
          <p><strong>五育类别：</strong>{{ material.category }}</p>
          <p><strong>建议分：</strong>{{ material.score }}</p>
          <p><strong>发证日期：</strong>{{ material.issuedAt }}</p>
          <p><strong>有效期：</strong>{{ material.expiresAt || '-' }}</p>
          <p><strong>风险：</strong>{{ material.riskReasons.length ? material.riskReasons.join('、') : 'low' }}</p>
          <p><strong>OCR：</strong>{{ material.ocrText }}</p>
          <p><strong>说明：</strong>{{ material.description || '-' }}</p>
        </div>
      </article>

      <article class="panel">
        <h2>审核动作</h2>
        <form class="grid" @submit.prevent>
          <label class="field">
            <span>审核意见</span>
            <textarea v-model.trim="form.opinion" />
          </label>
          <label class="field">
            <span>分数调整</span>
            <input v-model.number="form.scoreDelta" type="number" step="0.5" />
          </label>
          <div class="toolbar">
            <button class="button" type="button" :disabled="loading" @click="act('pass')">
              <CheckCircle2 :size="16" aria-hidden="true" />
              通过
            </button>
            <button class="button danger" type="button" :disabled="loading" @click="act('reject')">
              <XCircle :size="16" aria-hidden="true" />
              打回
            </button>
            <button class="button secondary" type="button" @click="load">
              <RotateCw :size="16" aria-hidden="true" />
              刷新
            </button>
          </div>
        </form>
      </article>
    </section>

    <section v-if="material" class="panel">
      <header class="material-file-header">
        <div>
          <h2>学生上传材料</h2>
          <p class="muted">
            {{ material.fileName || (material.fileUrl ? '在线材料' : '该材料未附文件，仅文字说明') }}
          </p>
        </div>
        <a
          v-if="material.fileUrl"
          class="button secondary"
          :href="material.fileUrl"
          target="_blank"
          rel="noopener"
          :download="material.fileName || true"
        >
          <Download :size="16" aria-hidden="true" />
          下载原件
        </a>
      </header>
      <div v-if="material.fileUrl" class="material-file-body">
        <div v-if="isImage" class="material-file-stage">
          <img :src="material.fileUrl" :alt="material.fileName || '学生上传材料'" />
        </div>
        <iframe
          v-else-if="isPdf"
          class="material-file-pdf"
          :src="material.fileUrl"
          :title="material.fileName || '学生上传 PDF'"
        />
        <div v-else class="material-file-fallback">
          <FileText :size="28" aria-hidden="true" />
          <div>
            <strong>{{ material.fileName || '未知文件' }}</strong>
            <p class="muted">该格式不支持在线预览，请点击右上方“下载原件”后查看。</p>
          </div>
        </div>
      </div>
      <div v-else class="material-file-empty">
        <FileText :size="28" aria-hidden="true" />
        <div>
          <strong>暂无原始文件</strong>
          <p class="muted">学生未上传或未保留原始证书文件，可参考 OCR 与说明字段进行核验。</p>
        </div>
      </div>
    </section>

    <section class="panel">
      <h2>审核记录</h2>
      <div v-if="reviews.length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>动作</th>
              <th>审核人</th>
              <th>意见</th>
              <th>调分</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in reviews" :key="record.id">
              <td>{{ record.action }}</td>
              <td>{{ record.reviewer.name }}</td>
              <td>{{ record.opinion }}</td>
              <td>{{ record.scoreDelta }}</td>
              <td>{{ new Date(record.createdAt).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted">暂无审核记录。</p>
    </section>
  </div>
</template>

<style scoped>
.material-file-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.material-file-header h2 {
  margin: 0;
}

.material-file-header p {
  margin: 4px 0 0;
}

.material-file-body {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: #0f172a;
  overflow: hidden;
}

.material-file-stage {
  display: grid;
  place-items: center;
  max-height: 640px;
  padding: 12px;
}

.material-file-stage img {
  max-width: 100%;
  max-height: 600px;
  display: block;
  object-fit: contain;
  background: #ffffff;
  border-radius: 4px;
}

.material-file-pdf {
  width: 100%;
  height: 640px;
  border: 0;
  background: #ffffff;
}

.material-file-fallback,
.material-file-empty {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px;
  border: 1px dashed var(--line);
  border-radius: var(--radius);
  background: var(--surface-muted);
  color: var(--ink);
}

.material-file-fallback strong,
.material-file-empty strong {
  display: block;
  margin-bottom: 4px;
}

.material-file-fallback p,
.material-file-empty p {
  margin: 0;
}
</style>
