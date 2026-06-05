<script setup lang="ts">
import { ClipboardList, FileCheck2, RotateCw, ShieldAlert, Trophy } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import { apiFetch } from '@/api/client'
import type { Appeal, Material, RankItem } from '@/api/types'
import EmptyState from '@/components/EmptyState.vue'
import MotionCaptureControl from '@/components/MotionCaptureControl.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useSessionStore } from '@/stores/session'

type DashboardResponse = {
  user: unknown
  dashboard: {
    summary?: {
      status: string
      totalScore: number
      materials: Material[]
    }
    appeals?: {
      items: Appeal[]
    }
    pending?: {
      items: Material[]
    }
    rank?: {
      items: RankItem[]
    }
    risk?: {
      totalRisk: number
      items: Material[]
    }
  }
}

const session = useSessionStore()
const loading = ref(false)
const error = ref('')
const success = ref('')
const dashboard = ref<DashboardResponse['dashboard']>({})
const materialPageIndex = ref(1)
const materialPageSize = 8
const materialTableRef = ref<HTMLDivElement | null>(null)

const roleTitle = computed(() => {
  if (session.role === 'student') return '学生工作台'
  if (session.role === 'teacher') return '老师工作台'
  return '辅导员工作台'
})

const firstRank = computed(() => dashboard.value.rank?.items?.[0])
const materialItems = computed(() =>
  session.role === 'student'
    ? dashboard.value.summary?.materials
    : dashboard.value.pending?.items,
)

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

async function loadDashboard() {
  error.value = ''
  success.value = ''
  loading.value = true
  try {
    const result = await apiFetch<DashboardResponse>('/api/auth/me')
    dashboard.value = result.dashboard
    materialPageIndex.value = 1
  } catch (err: any) {
    error.value = err.message || '加载总览失败'
  } finally {
    loading.value = false
  }
}

function handleMaterialMotion(payload: MotionPayload) {
  const { data, uiFeedback } = payload.response
  if (Array.isArray(data.items)) {
    if (session.role === 'student' && dashboard.value.summary) {
      dashboard.value.summary.materials = data.items
    } else if (dashboard.value.pending) {
      dashboard.value.pending.items = data.items
    }
  }
  if (typeof data.pageIndex === 'number') {
    materialPageIndex.value = data.pageIndex
  }
  if (data.scrollDirection) {
    materialTableRef.value?.scrollBy({
      top: data.scrollDirection === 'up' ? -220 : 220,
      behavior: 'smooth',
    })
  }
  error.value = uiFeedback.level === 'warning' ? uiFeedback.message : ''
  success.value = uiFeedback.level === 'warning' ? '' : uiFeedback.message
}

onMounted(loadDashboard)
</script>

<template>
  <div>
    <header class="page-header">
      <div>
        <p class="eyebrow">{{ session.user?.className || '全校' }}</p>
        <h1>{{ roleTitle }}</h1>
        <p class="muted">{{ session.user?.name }}，{{ session.user?.studentNo }}</p>
      </div>
      <button class="button secondary" type="button" @click="loadDashboard">
        <RotateCw :size="16" aria-hidden="true" />
        刷新
      </button>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>
    <div v-if="success" class="success-message">{{ success }}</div>
    <div v-if="!error" class="grid">
      <section v-if="session.role === 'student'" class="grid cols-3">
        <article class="card metric">
          <FileCheck2 :size="22" color="#2663eb" aria-hidden="true" />
          <span class="muted">当前状态</span>
          <strong>{{ dashboard.summary?.status || '未提交' }}</strong>
        </article>
        <article class="card metric">
          <Trophy :size="22" color="#16805a" aria-hidden="true" />
          <span class="muted">总分</span>
          <strong>{{ dashboard.summary?.totalScore ?? 0 }}</strong>
        </article>
        <article class="card metric">
          <ClipboardList :size="22" color="#a56704" aria-hidden="true" />
          <span class="muted">申诉</span>
          <strong>{{ dashboard.appeals?.items.length ?? 0 }}</strong>
        </article>
      </section>

      <section v-else class="grid cols-3">
        <article class="card metric">
          <ClipboardList :size="22" color="#2663eb" aria-hidden="true" />
          <span class="muted">待审材料</span>
          <strong>{{ dashboard.pending?.items.length ?? 0 }}</strong>
        </article>
        <article class="card metric">
          <ShieldAlert :size="22" color="#bd2e2e" aria-hidden="true" />
          <span class="muted">风险材料</span>
          <strong>{{ dashboard.risk?.totalRisk ?? 0 }}</strong>
        </article>
        <article class="card metric">
          <Trophy :size="22" color="#16805a" aria-hidden="true" />
          <span class="muted">榜首分数</span>
          <strong>{{ firstRank?.totalScore ?? 0 }}</strong>
        </article>
      </section>

      <section class="panel">
        <h2>{{ session.role === 'student' ? '我的材料' : '待处理材料' }}</h2>
        <MotionCaptureControl
          v-if="materialItems?.length"
          class="motion-inline"
          page="list"
          :page-index="materialPageIndex"
          :page-size="materialPageSize"
          @captured="handleMaterialMotion"
        />
        <div
          v-if="materialItems?.length"
          ref="materialTableRef"
          class="table-wrap motion-table"
        >
          <table>
            <thead>
              <tr>
                <th>材料</th>
                <th>学生</th>
                <th>五育</th>
                <th>分数</th>
                <th>状态</th>
                <th>风险</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in materialItems" :key="item.id">
                <td>
                  <strong>{{ item.title }}</strong>
                  <div class="muted">{{ item.certificateNo }}</div>
                </td>
                <td>{{ item.student?.name || session.user?.name }}</td>
                <td>{{ item.category }}</td>
                <td>{{ item.score }}</td>
                <td><StatusTag :value="item.status" /></td>
                <td>
                  <span class="tag" :class="item.riskLevel === 'low' ? 'success' : 'danger'">
                    {{ item.riskLevel }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else title="暂无数据" />
      </section>

      <section class="panel">
        <h2>排行榜</h2>
        <div v-if="dashboard.rank?.items.length" class="table-wrap">
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
              <tr v-for="item in dashboard.rank.items.slice(0, 8)" :key="item.rank">
                <td>{{ item.rank }}</td>
                <td>{{ item.student.name }}</td>
                <td>{{ item.student.studentNo }}</td>
                <td>{{ item.student.className || '-' }}</td>
                <td>{{ item.totalScore }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else title="暂无排名" />
      </section>
    </div>
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
