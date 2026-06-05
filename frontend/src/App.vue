<script setup lang="ts">
import {
  ClipboardCheck,
  Bot,
  FileUp,
  Gavel,
  LayoutDashboard,
  LogOut,
  Megaphone,
  Trophy,
} from 'lucide-vue-next'
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import { useSessionStore } from '@/stores/session'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()

const isPublic = computed(() => Boolean(route.meta.public))

const navItems = computed(() => {
  if (!session.user) return []
  const common = [
    { to: '/dashboard', label: '总览', icon: LayoutDashboard },
    { to: '/publicity', label: '公示排名', icon: Trophy },
    { to: '/ai', label: '智能助手', icon: Bot },
  ]
  if (session.user.role === 'student') {
    return [
      ...common,
      { to: '/materials', label: '材料上传', icon: FileUp },
      { to: '/appeals', label: '我的申诉', icon: Gavel },
    ]
  }
  if (session.user.role === 'teacher') {
    return [
      ...common,
      { to: '/review', label: '材料审核', icon: ClipboardCheck },
    ]
  }
  return [
    ...common,
    { to: '/review', label: '班级审核', icon: ClipboardCheck },
    { to: '/appeals', label: '申诉处理', icon: Gavel },
    { to: '/publicity', label: '公示发起', icon: Megaphone },
  ]
})

function logout() {
  session.logout()
  router.push('/login')
}
</script>

<template>
  <RouterView v-if="isPublic" />
  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">综</span>
        <span>高校综测系统</span>
      </div>
      <nav class="nav">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to">
          <component :is="item.icon" :size="18" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-footer">
        <div class="user-mini">
          <strong>{{ session.user?.name }}</strong>
          <div>{{ session.user?.studentNo }} · {{ session.user?.role }}</div>
        </div>
        <button class="button secondary" type="button" @click="logout">
          <LogOut :size="16" aria-hidden="true" />
          退出
        </button>
      </div>
    </aside>
    <main class="page">
      <RouterView />
    </main>
  </div>
</template>
