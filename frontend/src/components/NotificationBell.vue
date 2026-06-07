<script setup lang="ts">
import { Bell, Check, CheckCheck } from 'lucide-vue-next'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useNotificationStore } from '@/stores/notification'
import { useSessionStore } from '@/stores/session'

const notification = useNotificationStore()
const session = useSessionStore()
const router = useRouter()
const open = ref(false)

async function toggle() {
  open.value = !open.value
  if (open.value) {
    await notification.load()
  }
}

async function markAll() {
  await notification.markAllRead()
}

async function openItem(id: number, link: string | null | undefined) {
  await notification.markRead(id)
  open.value = false
  if (link) {
    router.push(link)
  }
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const diff = Date.now() - date.getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`
  return date.toLocaleDateString()
}

onMounted(() => {
  notification.refreshUnread()
  notification.startPolling(30000)
})

onBeforeUnmount(() => {
  notification.stopPolling()
})
</script>

<template>
  <div v-if="session.isAuthed" class="notif-bell" :class="{ open }">
    <button
      class="icon-button notif-button"
      type="button"
      :aria-expanded="open"
      aria-haspopup="true"
      aria-label="通知中心"
      @click="toggle"
    >
      <Bell :size="18" aria-hidden="true" />
      <span v-if="notification.unread > 0" class="notif-badge">{{ notification.unread > 99 ? '99+' : notification.unread }}</span>
    </button>
    <div v-if="open" class="notif-panel surface-panel">
      <header class="notif-header">
        <strong>通知中心</strong>
        <button class="button secondary" type="button" :disabled="!notification.unread" @click="markAll">
          <CheckCheck :size="14" aria-hidden="true" />
          全部已读
        </button>
      </header>
      <ul v-if="notification.items.length" class="notif-list">
        <li v-for="item in notification.items" :key="item.id" :class="{ unread: !item.isRead }">
          <button type="button" class="notif-item" @click="openItem(item.id, item.link)">
            <div class="notif-title">
              <Check v-if="item.isRead" :size="14" color="#16805a" aria-hidden="true" />
              <Bell v-else :size="14" color="#2663eb" aria-hidden="true" />
              <strong>{{ item.title }}</strong>
              <span class="muted notif-time">{{ formatTime(item.createdAt) }}</span>
            </div>
            <p>{{ item.content }}</p>
          </button>
        </li>
      </ul>
      <div v-else class="notif-empty">暂无通知</div>
    </div>
    <div v-if="open" class="notif-backdrop" @click="open = false" />
  </div>
</template>

<style scoped>
.notif-bell {
  position: relative;
}

.notif-button {
  position: relative;
}

.notif-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 999px;
  background: var(--danger);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  line-height: 18px;
  text-align: center;
}

.notif-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  width: 360px;
  max-height: 480px;
  display: flex;
  flex-direction: column;
  z-index: 60;
  padding: 0;
}

.notif-backdrop {
  position: fixed;
  inset: 0;
  z-index: 55;
}

.notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}

.notif-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow: auto;
  flex: 1;
}

.notif-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 12px 16px;
  border-bottom: 1px solid var(--line);
  background: transparent;
  cursor: pointer;
}

.notif-item:hover {
  background: var(--surface-muted);
}

.notif-item p {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.45;
}

.notif-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.notif-title strong {
  flex: 1;
}

.notif-time {
  font-size: 12px;
}

.notif-empty {
  padding: 24px;
  text-align: center;
  color: var(--muted);
}

.notif-list li.unread .notif-title strong {
  color: var(--text);
}

@media (max-width: 720px) {
  .notif-panel {
    width: min(360px, calc(100vw - 24px));
  }
}
</style>
