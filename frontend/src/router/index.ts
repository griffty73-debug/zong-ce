import { createRouter, createWebHistory } from 'vue-router'

import { useSessionStore } from '@/stores/session'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/register', component: () => import('@/views/RegisterView.vue'), meta: { public: true } },
    { path: '/dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/materials', component: () => import('@/views/MaterialsView.vue') },
    { path: '/review', component: () => import('@/views/ReviewListView.vue') },
    { path: '/review/:id', component: () => import('@/views/ReviewDetailView.vue') },
    { path: '/appeals', component: () => import('@/views/AppealsView.vue') },
    { path: '/publicity', component: () => import('@/views/PublicityView.vue') },
    { path: '/gesture', redirect: '/dashboard' },
    { path: '/ai', component: () => import('@/views/AiAssistantView.vue') },
  ],
})

router.beforeEach((to) => {
  const session = useSessionStore()
  if (!to.meta.public && !session.isAuthed) return '/login'
  if (to.meta.public && session.isAuthed) return '/dashboard'
})

export default router
