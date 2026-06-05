<script setup lang="ts">
const props = defineProps<{
  value: string
}>()

const toneMap: Record<string, string> = {
  已通过: 'success',
  公示结束: 'success',
  已提交: 'primary',
  审核中: 'primary',
  公示中: 'primary',
  草稿: '',
  申诉处理中: 'warning',
  待处理: 'warning',
  已打回: 'danger',
  已驳回: 'danger',
}
</script>

<template>
  <span class="tag" :class="toneMap[props.value]">{{ props.value }}</span>
</template>
