<script setup lang="ts">
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  RadarController,
  RadialLinearScale,
  Tooltip,
} from 'chart.js'
import { Bar, Doughnut, Line, Radar } from 'vue-chartjs'

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  RadarController,
  RadialLinearScale,
  Tooltip,
)

defineProps<{
  type: 'bar' | 'line' | 'radar' | 'doughnut'
  data: any
  options?: any
  height?: number
}>()
</script>

<template>
  <div class="chart-wrap" :style="{ height: `${height ?? 240}px` }">
    <Bar v-if="type === 'bar'" :data="data" :options="options" />
    <Line v-else-if="type === 'line'" :data="data" :options="options" />
    <Radar v-else-if="type === 'radar'" :data="data" :options="options" />
    <Doughnut v-else :data="data" :options="options" />
  </div>
</template>

<style scoped>
.chart-wrap {
  position: relative;
  width: 100%;
}
</style>
