<script setup lang="ts">
import { LogIn } from 'lucide-vue-next'
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

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
    await session.login({ ...form, portal: 'student' })
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
      <p class="eyebrow">学生端入口</p>
      <h1>学生登录</h1>
      <p class="muted">输入 20 开头的 11 位学号，进入个人综测工作台。</p>

      <form class="grid" @submit.prevent="submit">
        <label class="field">
          <span>学号</span>
          <input v-model.trim="form.studentNo" autocomplete="username" placeholder="如 20240000001" required />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="form.password" type="password" autocomplete="current-password" required />
        </label>
        <div v-if="error" class="alert">{{ error }}</div>
        <div class="login-hints">
          <p><strong>提示：</strong></p>
          <p>所有学生初始密码为 <code>123456</code></p>
          <p>本入口仅限学生使用，教师/辅导员请前往教师端。</p>
        </div>
        <button class="button" type="submit" :disabled="loading">
          <LogIn :size="16" aria-hidden="true" />
          {{ loading ? '登录中' : '学生登录' }}
        </button>
        <RouterLink class="button secondary" to="/register">注册新账号</RouterLink>
      </form>
    </section>
    <section class="auth-aside">
      <div class="auth-copy">
        <p class="eyebrow">Student Portal</p>
        <h1>提交、追踪、申诉一站搞定</h1>
        <p>上传证书、AI 自动识别、查看审核进度、参与公示与申诉，全部在学生端完成。</p>
      </div>
    </section>
  </div>
</template>
