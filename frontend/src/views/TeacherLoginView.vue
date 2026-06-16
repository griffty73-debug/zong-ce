<script setup lang="ts">
import { LogIn } from 'lucide-vue-next'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useSessionStore } from '@/stores/session'

const router = useRouter()
const session = useSessionStore()
const form = reactive({
  studentNo: '',
  password: '',
})
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await session.login({ ...form, portal: 'staff' })
    router.push('/dashboard')
  } catch (err: any) {
    error.value = err.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-layout">
    <section class="auth-panel">
      <p class="eyebrow">教师端入口</p>
      <h1>教师 / 辅导员登录</h1>
      <p class="muted">用工号或辅导员账号登录，进入审核、申诉与公示工作台。</p>

      <form class="grid" @submit.prevent="submit">
        <label class="field">
          <span>工号 / 账号</span>
          <input v-model.trim="form.studentNo" autocomplete="username" placeholder="如 10000000001 或 admin" required />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="form.password" type="password" autocomplete="current-password" required />
        </label>
        <div v-if="error" class="alert">{{ error }}</div>
        <div class="login-hints">
          <p><strong>提示：</strong></p>
          <p>辅导员账号 <code>admin</code> / 密码 <code>admin123</code></p>
          <p>本入口仅限教师与辅导员，学生请前往学生端。</p>
        </div>
        <button class="button" type="submit" :disabled="loading">
          <LogIn :size="16" aria-hidden="true" />
          {{ loading ? '登录中' : '教师登录' }}
        </button>
      </form>
    </section>
    <section class="auth-aside">
      <div class="auth-copy">
        <p class="eyebrow">Staff Portal</p>
        <h1>批量审核、公示、归档</h1>
        <p>查看待审材料、批量通过/打回、发起公示、处理申诉，所有教务流程一屏掌控。</p>
      </div>
    </section>
  </div>
</template>
