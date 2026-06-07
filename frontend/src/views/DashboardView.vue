<script setup lang="ts">
import {
  ClipboardList,
  Download,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  RotateCw,
  ShieldAlert,
  Trophy,
} from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import { apiFetch } from '@/api/client'
import ChartView from '@/components/ChartView.vue'
import EmptyState from '@/components/EmptyState.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useTermRefresh } from '@/composables/useTermRefresh'
import { useSessionStore } from '@/stores/session'
import { useTermStore } from '@/stores/term'
import type { Material, StatsOverview, StudentStats } from '@/api/types'

const session = useSessionStore()
const termStore = useTermStore()
const loading = ref(false)
const error = ref('')
const stats = ref<StatsOverview | null>(null)
const studentStats = ref<StudentStats | null>(null)
const downloadFormat = ref<string>('')

const roleTitle = computed(() => {
  if (session.role === 'student') return '学生工作台'
  if (session.role === 'teacher') return '老师工作台'
  return '辅导员工作台'
})

const categoryData = computed(() => {
  if (session.role === 'student' && studentStats.value) {
    return {
      labels: studentStats.value.category.map((item) => item.category),
      datasets: [
        {
          label: '当前学期五育得分',
          data: studentStats.value.category.map((item) => item.score),
          backgroundColor: 'rgba(38, 99, 235, 0.6)',
          borderColor: '#2663eb',
          borderWidth: 1,
        },
      ],
    }
  }
  if (stats.value) {
    return {
      labels: stats.value.categoryBreakdown.map((item) => item.category),
      datasets: [
        {
          label: '本学期五育累计',
          data: stats.value.categoryBreakdown.map((item) => item.score),
          backgroundColor: [
            'rgba(38, 99, 235, 0.65)',
            'rgba(15, 118, 110, 0.65)',
            'rgba(245, 158, 11, 0.65)',
            'rgba(124, 58, 237, 0.65)',
            'rgba(22, 128, 90, 0.65)',
            'rgba(189, 46, 46, 0.65)',
          ],
        },
      ],
    }
  }
  return { labels: [], datasets: [] }
})

const radarData = computed(() => {
  if (session.role !== 'student' || !studentStats.value) return null
  return {
    labels: studentStats.value.category.map((item) => item.category),
    datasets: [
      {
        label: '当前能力分布',
        data: studentStats.value.category.map((item) => item.score),
        backgroundColor: 'rgba(15, 118, 110, 0.18)',
        borderColor: '#0f766e',
        pointBackgroundColor: '#0f766e',
        borderWidth: 2,
      },
    ],
  }
})

const trendData = computed(() => {
  if (!stats.value) return { labels: [], datasets: [] }
  return {
    labels: stats.value.trend.map((item) => item.date),
    datasets: [
      {
        label: '近 14 天新提交材料',
        data: stats.value.trend.map((item) => item.count),
        borderColor: '#2663eb',
        backgroundColor: 'rgba(38, 99, 235, 0.18)',
        fill: true,
        tension: 0.35,
      },
    ],
  }
})

const topStudents = computed(() => stats.value?.topStudents ?? [])

const summaryCards = computed(() => {
  if (session.role === 'student' && studentStats.value) {
    return [
      { label: '当前状态', value: studentStats.value.materials[0]?.status || '未提交', icon: FileCheck2, color: '#2663eb' },
      { label: '本学期总分', value: studentStats.value.totalScore, icon: Trophy, color: '#16805a' },
      { label: '已通过材料', value: studentStats.value.statusDistribution['已通过'] ?? 0, icon: ClipboardList, color: '#a56704' },
    ]
  }
  if (stats.value) {
    return [
      { label: '待审材料', value: stats.value.summary.pending, icon: ClipboardList, color: '#2663eb' },
      { label: '风险材料', value: stats.value.summary.totalMaterials - stats.value.summary.approved, icon: ShieldAlert, color: '#bd2e2e' },
      { label: '榜首分数', value: topStudents.value[0]?.totalScore ?? 0, icon: Trophy, color: '#16805a' },
    ]
  }
  return []
})

async function loadDashboard() {
  error.value = ''
  loading.value = true
  try {
    if (session.role === 'student') {
      const termQs = termStore.currentId ? `?termId=${termStore.currentId}` : ''
      studentStats.value = await apiFetch<StudentStats>(`/api/stats/student${termQs}`)
    } else {
      const termQs = termStore.currentId ? `?termId=${termStore.currentId}` : ''
      stats.value = await apiFetch<StatsOverview>(`/api/stats/overview${termQs}`)
    }
  } catch (err: any) {
    error.value = err.message || '加载总览失败'
  } finally {
    loading.value = false
  }
}

async function downloadStudent(format: 'pdf' | 'xlsx') {
  if (downloadFormat.value) return
  downloadFormat.value = format
  try {
    const token = sessionStorage.getItem('zc_token') || ''
    const termQs = termStore.currentId ? `?termId=${termStore.currentId}` : ''
    const response = await fetch(`/api/export/student-summary.${format}${termQs}`, {
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
    a.download = `我的综测成绩单-${new Date().toISOString().slice(0, 10)}.${format}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (err: any) {
    error.value = err.message || '导出失败'
  } finally {
    downloadFormat.value = ''
  }
}

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
  },
  scales: {
    y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
    x: { grid: { display: false } },
  },
}

const radarOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      beginAtZero: true,
      ticks: { stepSize: 2 },
      grid: { color: 'rgba(0,0,0,0.06)' },
      angleLines: { color: 'rgba(0,0,0,0.06)' },
    },
  },
}

onMounted(loadDashboard)
watch(() => termStore.currentId, loadDashboard)
useTermRefresh(loadDashboard)
</script>

<template>
  <div>
    <header class="page-header">
      <div>
        <p class="eyebrow">{{ session.user?.className || '全校' }}</p>
        <h1>{{ roleTitle }}</h1>
        <p class="muted">{{ session.user?.name }}，{{ session.user?.studentNo }}</p>
      </div>
      <div class="toolbar">
        <template v-if="session.role === 'student'">
          <button
            class="button secondary"
            type="button"
            :disabled="Boolean(downloadFormat)"
            @click="downloadStudent('xlsx')"
          >
            <FileSpreadsheet :size="16" aria-hidden="true" />
            {{ downloadFormat === 'xlsx' ? '导出中' : '导出 Excel' }}
          </button>
          <button
            class="button secondary"
            type="button"
            :disabled="Boolean(downloadFormat)"
            @click="downloadStudent('pdf')"
          >
            <FileText :size="16" aria-hidden="true" />
            {{ downloadFormat === 'pdf' ? '导出中' : '导出 PDF' }}
          </button>
        </template>
        <button class="button secondary" type="button" :disabled="loading" @click="loadDashboard">
          <RotateCw :size="16" aria-hidden="true" />
          刷新
        </button>
      </div>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>

    <section v-if="summaryCards.length" class="grid cols-3">
      <article v-for="card in summaryCards" :key="card.label" class="card metric">
        <component :is="card.icon" :size="22" :color="card.color" aria-hidden="true" />
        <span class="muted">{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
      </article>
    </section>

    <section v-if="session.role === 'student' && radarData" class="grid cols-2">
      <article class="panel">
        <h2>五育能力雷达</h2>
        <ChartView type="radar" :data="radarData" :options="radarOptions" :height="280" />
      </article>
      <article class="panel">
        <h2>各类别得分</h2>
        <ChartView type="bar" :data="categoryData" :options="chartOptions" :height="280" />
      </article>
    </section>

    <section v-else-if="stats" class="grid cols-2">
      <article class="panel">
        <h2>五育累计得分</h2>
        <ChartView type="doughnut" :data="categoryData" :options="{ responsive: true, maintainAspectRatio: false }" :height="280" />
      </article>
      <article class="panel">
        <h2>近 14 天提交趋势</h2>
        <ChartView type="line" :data="trendData" :options="chartOptions" :height="280" />
      </article>
    </section>

    <section v-if="session.role !== 'student' && stats" class="grid cols-2">
      <article class="panel">
        <h2>Top 8 学生</h2>
        <div v-if="topStudents.length" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>学号</th>
                <th>姓名</th>
                <th>班级</th>
                <th>总分</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in topStudents" :key="item.studentNo">
                <td>{{ index + 1 }}</td>
                <td>{{ item.name }}</td>
                <td>{{ item.className || '-' }}</td>
                <td>{{ item.totalScore }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else title="暂无排名数据" />
      </article>
      <article class="panel">
        <h2>班级对比</h2>
        <div v-if="stats.classBreakdown.length" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>班级</th>
                <th>累计总分</th>
                <th>学生数</th>
                <th>人均</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in stats.classBreakdown" :key="item.className">
                <td>{{ item.className }}</td>
                <td>{{ item.totalScore.toFixed(2) }}</td>
                <td>{{ item.studentCount }}</td>
                <td>{{ item.studentCount ? (item.totalScore / item.studentCount).toFixed(2) : '0.00' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else title="暂无班级数据" />
      </article>
    </section>

    <section v-if="session.role === 'student' && studentStats" class="panel">
      <h2>本学期材料</h2>
      <div v-if="studentStats.materials.length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>材料</th>
              <th>五育</th>
              <th>分数</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in studentStats.materials" :key="item.id">
              <td>
                <strong>{{ item.title }}</strong>
                <div class="muted">{{ item.certificateNo }}</div>
              </td>
              <td>{{ item.category }}</td>
              <td>{{ item.score }}</td>
              <td><StatusTag :value="item.status" /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState v-else title="本学期暂无材料" />
    </section>

    <p v-if="session.role === 'student'" class="muted small-tip">
      <Download :size="14" aria-hidden="true" />
      成绩单 PDF/Excel 可在右上角直接下载
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
