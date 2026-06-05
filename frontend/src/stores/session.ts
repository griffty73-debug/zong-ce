import { defineStore } from 'pinia'

import { apiFetch, postJson } from '@/api/client'
import type { User } from '@/api/types'

type LoginPayload = {
  studentNo: string
  password: string
}

type RegisterPayload = LoginPayload & {
  name: string
  role?: string
  className?: string
}

type AuthResponse = {
  token: string
  user: User
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    token: sessionStorage.getItem('zc_token') || '',
    user: JSON.parse(sessionStorage.getItem('zc_user') || 'null') as User | null,
    loading: false,
  }),
  getters: {
    isAuthed: (state) => Boolean(state.token && state.user),
    role: (state) => state.user?.role,
  },
  actions: {
    persist(payload: AuthResponse) {
      this.token = payload.token
      this.user = payload.user
      sessionStorage.setItem('zc_token', payload.token)
      sessionStorage.setItem('zc_user', JSON.stringify(payload.user))
    },
    async login(payload: LoginPayload) {
      const result = await postJson<AuthResponse>('/api/auth/login', payload)
      this.persist(result)
    },
    async register(payload: RegisterPayload) {
      const result = await postJson<AuthResponse>('/api/auth/register', payload)
      this.persist(result)
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
