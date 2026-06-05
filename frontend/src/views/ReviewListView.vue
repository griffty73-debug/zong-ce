<script setup lang="ts">
import { Eye, RotateCw } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { apiFetch } from '@/api/client'
import type { Material } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import MotionCaptureControl from '@/components/MotionCaptureControl.vue'
import StatusTag from '@/components/StatusTag.vue'

type MotionPayload = {
  response: {
    uiFeedback: { level: string; message: string }
    data: {
      items?: Material[]
      pageIndex?: number
      scrollDirection?: 'up' | 'down'
    }
  }
}

const items = ref<Material[]>([])
const error = ref('')
const loading = ref(false)
const reviewPageIndex = ref(1)
const reviewPageSize = 8
const reviewListRef = ref<HTMLDivElement | null>(null)

async function load() {
  error.value = ''
  loading.value = true
  try {
    const result = await apiFetch<{ items: Material[] }>('/api/review/list')
    items.value = result.items
    reviewPageIndex.value = 1
  } catch (err: any) {
    error.value = err.message || '加载待审核列表失败'
  } finally {
    loading.value = false
  }
}

function handleReviewMotion(payload: MotionPayload) {
  const { data, uiFeedback } = payload.response
  if (Array.isArray(data.items)) {
    items.value = data.items
  }
  if (typeof data.pageIndex === 'number') {
    reviewPageIndex.value = data.pageIndex
  }
  if (data.scrollDirection) {
    reviewListRef.value?.scrollBy({
      top: data.scrollDirection === 'up' ? -220 : 220,
      behavior: 'smooth',
    })
  }
  error.value = uiFeedback.level === 'warning' ? uiFeedback.message : ''
}

onMounted(load)
</script>

<template>
  <div class="grid">
    <header class="page-header">
      <div>
        <p class="eyebrow">老师 / 辅导员端</p>
        <h1>待审核列表</h1>
        <p class="muted">提交材料会先进入[已提交]，审核动作会推进到[审核中]再完成通过或打回。</p>
      </div>
      <button class="button secondary" type="button" @click="load">
        <RotateCw :size="16" aria-hidden="true" />
        刷新
      </button>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>
    <section class="panel">
      <h2>待审核材料</h2>
      <MotionCaptureControl
        v-if="items.length"
        class="motion-inline"
        page="list"
        :page-index="reviewPageIndex"
        :page-size="reviewPageSize"
        @captured="handleReviewMotion"
      />
      <div v-if="items.length" ref="reviewListRef" class="table-wrap motion-table">
        <table>
          <thead>
            <tr>
              <th>材料</th>
              <th>学生</th>
              <th>班级</th>
              <th>五育</th>
              <th>分数</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>
                <strong>{{ item.title }}</strong>
                <div class="muted">{{ item.certificateNo }}</div>
              </td>
              <td>{{ item.student?.name }}</td>
              <td>{{ item.student?.className || '-' }}</td>
              <td>{{ item.category }}</td>
              <td>{{ item.score }}</td>
              <td><StatusTag :value="item.status" /></td>
              <td>
                <RouterLink class="icon-button" :to="`/review/${item.id}`" title="查看审核详情">
                  <Eye :size="17" aria-hidden="true" />
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState v-else title="暂无待审材料" />
    </section>
  </div>
</template>

<style scoped>
.motion-inline {
  margin-bottom: 12px;
}

.motion-table {
  max-height: 520px;
  overflow: auto;
}
</style>