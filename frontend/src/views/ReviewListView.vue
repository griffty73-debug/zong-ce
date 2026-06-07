<script setup lang="ts">
import { CheckCircle2, Eye, RotateCw, XCircle } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { apiFetch, postJson } from '@/api/client'
import type { Material } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTermRefresh } from '@/composables/useTermRefresh'
import { useTermStore } from '@/stores/term'

const items = ref<Material[]>([])
const error = ref('')
const success = ref('')
const loading = ref(false)
const selected = ref<Set<number>>(new Set())
const batchOpinion = ref('')
const batchSubmitting = ref(false)
const termStore = useTermStore()

async function load() {
  error.value = ''
  loading.value = true
  try {
    const qs = termStore.currentId ? `?termId=${termStore.currentId}` : ''
    const result = await apiFetch<{ items: Material[] }>(`/api/review/list${qs}`)
    items.value = result.items
    selected.value = new Set()
  } catch (err: any) {
    error.value = err.message || '加载待审核列表失败'
  } finally {
    loading.value = false
  }
}

const allSelected = computed(() => items.value.length > 0 && selected.value.size === items.value.length)

function toggleAll() {
  if (allSelected.value) {
    selected.value = new Set()
  } else {
    selected.value = new Set(items.value.map((item) => item.id))
  }
}

function toggleOne(id: number) {
  const next = new Set(selected.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  selected.value = next
}

async function batchAction(action: 'pass' | 'reject') {
  if (selected.value.size === 0) return
  if (action === 'reject' && !batchOpinion.value.trim()) {
    error.value = '打回材料必须填写统一意见'
    return
  }
  error.value = ''
  success.value = ''
  batchSubmitting.value = true
  try {
    const result = await postJson<{ message?: string; count?: number }>('/api/review/batch-action', {
      materialIds: Array.from(selected.value),
      action,
      opinion: batchOpinion.value || (action === 'pass' ? '批量审核通过' : '批量打回'),
    })
    success.value = result.message || `已${action === 'pass' ? '通过' : '打回'} ${result.count ?? selected.value.size} 条材料`
    batchOpinion.value = ''
    await load()
  } catch (err: any) {
    error.value = err.message || '批量审核失败'
  } finally {
    batchSubmitting.value = false
  }
}

onMounted(load)
watch(() => termStore.currentId, load)
useTermRefresh(load)
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
    <div v-if="success" class="success-message">{{ success }}</div>

    <section v-if="selected.size > 0" class="panel table-toolbar">
      <span>已选 {{ selected.size }} / {{ items.length }} 条</span>
      <input
        v-model.trim="batchOpinion"
        class="batch-opinion"
        type="text"
        placeholder="批量意见（打回时必填）"
      />
      <div class="toolbar">
        <button
          class="button"
          type="button"
          :disabled="batchSubmitting"
          @click="batchAction('pass')"
        >
          <CheckCircle2 :size="16" aria-hidden="true" />
          批量通过
        </button>
        <button
          class="button danger"
          type="button"
          :disabled="batchSubmitting"
          @click="batchAction('reject')"
        >
          <XCircle :size="16" aria-hidden="true" />
          批量打回
        </button>
        <button class="button secondary" type="button" @click="selected = new Set()">
          取消选择
        </button>
      </div>
    </section>

    <section class="panel">
      <h2>待审核材料</h2>
      <div v-if="items.length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="table-checkbox">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  aria-label="全选"
                  @change="toggleAll"
                />
              </th>
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
            <tr v-for="item in items" :key="item.id" :class="{ 'is-selected': selected.has(item.id) }">
              <td class="table-checkbox">
                <input
                  type="checkbox"
                  :checked="selected.has(item.id)"
                  :aria-label="`选择 ${item.title}`"
                  @change="toggleOne(item.id)"
                />
              </td>
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
.batch-opinion {
  flex: 1;
  min-width: 200px;
  height: 36px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: #ffffff;
}
</style>