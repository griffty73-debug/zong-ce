import { defineStore } from 'pinia'

import { apiFetch } from '@/api/client'
import type { Term } from '@/api/types'

type TermState = {
  items: Term[]
  currentId: number | null
  loading: boolean
}

export const useTermStore = defineStore('term', {
  state: (): TermState => ({
    items: [],
    currentId: null,
    loading: false,
  }),
  getters: {
    current(state): Term | null {
      return state.items.find((item) => item.id === state.currentId) || null
    },
  },
  actions: {
    async load() {
      this.loading = true
      try {
        const result = await apiFetch<{ items: Term[] }>('/api/terms/list')
        this.items = result.items
        const local = sessionStorage.getItem('zc_term_id')
        const localId = local ? Number(local) : null
        const candidate = this.items.find((item) => item.id === localId) || this.items.find((item) => item.isCurrent) || this.items[0]
        this.currentId = candidate ? candidate.id : null
        if (this.currentId) {
          sessionStorage.setItem('zc_term_id', String(this.currentId))
        }
      } finally {
        this.loading = false
      }
    },
    setCurrent(id: number) {
      this.currentId = id
      sessionStorage.setItem('zc_term_id', String(id))
    },
  },
})
