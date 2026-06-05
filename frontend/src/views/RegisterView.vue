<script setup lang="ts">
import { UserPlus } from 'lucide-vue-next'
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { useSessionStore } from '@/stores/session'

const router = useRouter()
const session = useSessionStore()
const form = reactive({
  studentNo: '',
  name: '',
  password: '',
  className: '',
})
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await session.register(form)
    router.push('/dashboard')
  } catch (err: any) {
    error.value = err.message || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-layout">
    <section class="auth-panel">
      <p class="eyebrow">账号注册</p>
      <h1>创建账号</h1>
      <p class="muted">系统会根据纯数字学号或工号自动识别学生、老师或辅导员。</p>

      <form class="grid" @submit.prevent="submit">
        <label class="field">
          <span>学工号</span>
          <input v-model.trim="form.studentNo" autocomplete="username" required />
        </label>
        <label class="field">
          <span>姓名</span>
          <input v-model.trim="form.name" autocomplete="name" required />
        </label>
        <label class="field">
          <span>班级</span>
          <input v-model.trim="form.className" placeholder="如 计科 2301" />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="form.password" type="password" autocomplete="new-password" required />
        </label>
        <div v-if="error" class="alert">{{ error }}</div>
        <button class="button" type="submit" :disabled="loading">
          <UserPlus :size="16" aria-hidden="true" />
          {{ loading ? '创建中' : '创建账号' }}
        </button>
        <RouterLink class="button secondary" to="/login">已有账号登录</RouterLink>
      </form>
    </section>
    <section class="auth-aside">
      <div class="auth-copy">
        <p class="eyebrow">Role Based Workflow</p>
        <h1>按职责进入流程</h1>
        <p>学生提交材料，老师完成审核，辅导员发起公示并处理申诉。</p>
      </div>
    </section>
  </div>
</template>
