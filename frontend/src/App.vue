<script setup lang="ts">
import {
  ClipboardCheck,
  Bot,
  FileUp,
  Gavel,
  LayoutDashboard,
  LogOut,
  Megaphone,
  Menu,
  Trophy,
  X,
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import NotificationBell from '@/components/NotificationBell.vue'
import TermSelector from '@/components/TermSelector.vue'
import { useSessionStore } from '@/stores/session'
import { useTermStore } from '@/stores/term'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const term = useTermStore()

const isPublic = computed(() => Boolean(route.meta.public))
const navOpen = ref(false)
const isMobile = ref(false)

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

const currentTitle = computed(() => {
  const path = route.path
  const match = navItems.value.find((item) => item.to === path)
  if (match) return match.label
  if (path.startsWith('/review/')) return '审核详情'
  if (path === '/login/student') return '学生登录'
  if (path === '/login/teacher') return '教师登录'
  if (path.startsWith('/login')) return '登录'
  if (path === '/register') return '注册'
  return '高校综测系统'
})

function syncViewport() {
  if (typeof window === 'undefined') return
  const next = window.matchMedia('(max-width: 920px)').matches
  isMobile.value = next
  if (!next) navOpen.value = false
}

function toggleNav() {
  navOpen.value = !navOpen.value
}

function closeNav() {
  navOpen.value = false
}

function handleNavClick() {
  if (isMobile.value) closeNav()
}

function logout() {
  const target = session.loginPath || '/login/student'
  session.logout()
  router.push(target)
  closeNav()
}

watch(() => route.fullPath, () => {
  if (isMobile.value) closeNav()
})

onMounted(() => {
  syncViewport()
  window.addEventListener('resize', syncViewport)
  if (session.isAuthed) {
    term.load()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncViewport)
})
</script>

<template>
  <RouterView v-if="isPublic" />
  <div v-else class="app-shell">
    <header v-if="isMobile" class="app-bar">
      <button
        class="icon-button"
        type="button"
        :aria-expanded="navOpen"
        aria-controls="primary-sidebar"
        aria-label="打开导航菜单"
        @click="toggleNav"
      >
        <Menu v-if="!navOpen" :size="20" aria-hidden="true" />
        <X v-else :size="20" aria-hidden="true" />
      </button>
      <div class="app-bar-brand">
        <span class="brand-mark">综</span>
        <span class="app-bar-brand-text">{{ currentTitle }}</span>
      </div>
      <NotificationBell />
      <button
        class="icon-button"
        type="button"
        aria-label="退出登录"
        @click="logout"
      >
        <LogOut :size="18" aria-hidden="true" />
      </button>
    </header>

    <div
      v-if="isMobile && navOpen"
      class="drawer-backdrop"
      aria-hidden="true"
      @click="closeNav"
    />

    <aside
      id="primary-sidebar"
      class="sidebar"
      :class="{ 'drawer-open': navOpen }"
      :aria-hidden="isMobile && !navOpen"
      :inert="isMobile && !navOpen ? true : undefined"
    >
      <div class="brand">
        <span class="brand-mark">综</span>
        <span>高校综测系统</span>
      </div>
      <TermSelector />
      <nav class="nav" @click="handleNavClick">
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
        <div class="sidebar-footer-actions">
          <NotificationBell />
          <button class="button secondary" type="button" @click="logout">
            <LogOut :size="16" aria-hidden="true" />
            退出
          </button>
        </div>
      </div>
    </aside>

    <main class="page">
      <div class="page-inner">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<style scoped>
.sidebar-footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
