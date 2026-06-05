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
    await session.login(form)
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
      <p class="eyebrow">统一身份入口</p>
      <h1>登录</h1>
      <p class="muted">学生、老师、辅导员使用同一入口进入对应工作台。</p>

      <form class="grid" @submit.prevent="submit">
        <label class="field">
          <span>学工号</span>
          <input v-model.trim="form.studentNo" autocomplete="username" required />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="form.password" type="password" autocomplete="current-password" required />
        </label>
        <div v-if="error" class="alert">{{ error }}</div>
        <div class="login-hints">
          <p><strong>提示：</strong></p>
          <p>所有用户初始密码为 <code>123456</code></p>
          <p>辅导员账号: <code>admin</code> / 密码: <code>admin123</code></p>
        </div>
        <button class="button" type="submit" :disabled="loading">
          <LogIn :size="16" aria-hidden="true" />
          {{ loading ? '登录中' : '登录' }}
        </button>
        <RouterLink class="button secondary" to="/register">注册新账号</RouterLink>
      </form>
    </section>
    <section class="auth-aside">
      <div class="auth-copy">
        <p class="eyebrow">Comprehensive Assessment</p>
        <h1>综测流程一屏串联</h1>
        <p>材料提交、审核、复核、公示和归档都由状态机约束，角色看到的就是自己要处理的事。</p>
      </div>
    </section>
  </div>
</template>
