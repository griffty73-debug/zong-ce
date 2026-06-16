import { defineStore } from 'pinia'

import { apiFetch, postJson } from '@/api/client'
import type { User } from '@/api/types'

export type Portal = 'student' | 'staff'

type LoginPayload = {
  studentNo: string
  password: string
  portal?: Portal
}

type RegisterPayload = LoginPayload & {
  name: string
  role?: string
  className?: string
  collegeId?: number | null
  majorId?: number | null
  classGroupId?: number | null
}

type AuthResponse = {
  token: string
  user: User
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    token: sessionStorage.getItem('zc_token') || '',
    user: JSON.parse(sessionStorage.getItem('zc_user') || 'null') as User | null,
    portal: (sessionStorage.getItem('zc_portal') as Portal | null) || null,
    loading: false,
  }),
  getters: {
    isAuthed: (state) => Boolean(state.token && state.user),
    role: (state) => state.user?.role,
    loginPath: (state) => (state.portal === 'staff' ? '/login/teacher' : '/login/student'),
  },
  actions: {
    persist(payload: AuthResponse, portal?: Portal) {
      this.token = payload.token
      this.user = payload.user
      sessionStorage.setItem('zc_token', payload.token)
      sessionStorage.setItem('zc_user', JSON.stringify(payload.user))
      const resolved: Portal = portal ?? (payload.user.role === 'student' ? 'student' : 'staff')
      this.portal = resolved
      sessionStorage.setItem('zc_portal', resolved)
    },
    async login(payload: LoginPayload) {
      const result = await postJson<AuthResponse>('/api/auth/login', payload)
      this.persist(result, payload.portal)
    },
    async register(payload: RegisterPayload) {
      const result = await postJson<AuthResponse>('/api/auth/register', payload)
      this.persist(result, payload.portal ?? 'student')
    },
    async refresh() {
      if (!this.token) return
      const result = await apiFetch<{ user: User }>('/api/auth/me')
      this.user = result.user
      sessionStorage.setItem('zc_user', JSON.stringify(result.user))
    },
    logout() {
      this.token = ''
      this.user = null
      sessionStorage.removeItem('zc_token')
      sessionStorage.removeItem('zc_user')
    },
  },
})
