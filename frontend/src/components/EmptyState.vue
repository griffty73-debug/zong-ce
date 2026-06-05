<script setup lang="ts">
import { Inbox } from 'lucide-vue-next'

defineProps<{
  title: string
  message?: string
}>()
</script>

<template>
  <div class="empty">
    <Inbox :size="32" aria-hidden="true" />
    <strong>{{ title }}</strong>
    <span v-if="message">{{ message }}</span>
  </div>
</template>

<style scoped>
.empty {
  min-height: 180px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: #657084;
  border: 1px dashed #cfd7e4;
  border-radius: 8px;
  background: #ffffff;
  text-align: center;
}

.empty strong {
  color: #263247;
}
</style>
