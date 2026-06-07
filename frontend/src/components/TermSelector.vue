<script setup lang="ts">
import { Calendar } from 'lucide-vue-next'
import { onMounted, watch } from 'vue'

import { useTermStore } from '@/stores/term'

const term = useTermStore()

onMounted(() => {
  if (term.items.length === 0) {
    term.load()
  }
})

function onChange(event: Event) {
  const value = Number((event.target as HTMLSelectElement).value)
  if (Number.isFinite(value)) {
    term.setCurrent(value)
  }
}

watch(
  () => term.currentId,
  (value) => {
    if (value) {
      window.dispatchEvent(new CustomEvent('zc:term-changed', { detail: value }))
    }
  },
)
</script>

<template>
  <label v-if="term.items.length > 1" class="term-select">
    <Calendar :size="14" aria-hidden="true" />
    <select :value="term.currentId ?? ''" @change="onChange">
      <option v-for="item in term.items" :key="item.id" :value="item.id">
        {{ item.name }}{{ item.isCurrent ? '（当前）' : '' }}
      </option>
    </select>
  </label>
  <span v-else-if="term.current" class="term-pill">
    <Calendar :size="14" aria-hidden="true" />
    {{ term.current.name }}
  </span>
</template>

<style scoped>
.term-select,
.term-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--sidebar-text);
  font-size: 13px;
}

.term-select select {
  background: transparent;
  color: inherit;
  border: 0;
  font: inherit;
  padding: 0;
  cursor: pointer;
}

.term-select select:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.4);
  border-radius: 6px;
}

.term-pill {
  font-weight: 600;
}
</style>
