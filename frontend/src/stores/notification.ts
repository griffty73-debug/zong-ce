import { defineStore } from 'pinia'

import { apiFetch, postJson } from '@/api/client'
import type { NotificationItem } from '@/api/types'

type State = {
  items: NotificationItem[]
  unread: number
  loading: boolean
  pollTimer: number | null
}

export const useNotificationStore = defineStore('notification', {
  state: (): State => ({
    items: [],
    unread: 0,
    loading: false,
    pollTimer: null,
  }),
  actions: {
    async load() {
      this.loading = true
      try {
        const result = await apiFetch<{ items: NotificationItem[]; unreadCount: number }>(
          '/api/notifications/list',
        )
        this.items = result.items
        this.unread = result.unreadCount
      } catch (err) {
        // 静默失败：通知拉取不影响主流程
      } finally {
        this.loading = false
      }
    },
    async refreshUnread() {
      try {
        const result = await apiFetch<{ unreadCount: number }>('/api/notifications/unread-count')
        this.unread = result.unreadCount
      } catch (err) {
        // ignore
      }
    },
    async markRead(id: number) {
      try {
        await postJson(`/api/notifications/${id}/read`, {})
        this.items = this.items.map((item) => (item.id === id ? { ...item, isRead: true } : item))
        this.unread = Math.max(0, this.unread - 1)
      } catch (err) {
        // ignore
      }
    },
    async markAllRead() {
      try {
        await postJson('/api/notifications/read-all', {})
        this.items = this.items.map((item) => ({ ...item, isRead: true }))
        this.unread = 0
      } catch (err) {
        // ignore
      }
    },
    startPolling(intervalMs: number = 30000) {
      this.stopPolling()
      this.pollTimer = window.setInterval(() => {
        this.refreshUnread()
      }, intervalMs)
    },
    stopPolling() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },
  },
})
