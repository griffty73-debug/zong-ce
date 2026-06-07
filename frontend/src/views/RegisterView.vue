<script setup lang="ts">
import { UserPlus } from 'lucide-vue-next'
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type { ClassGroup, College, Major } from '@/api/types'
import { useSessionStore } from '@/stores/session'

const router = useRouter()
const session = useSessionStore()
const form = reactive({
  studentNo: '',
  name: '',
  password: '',
  className: '',
  collegeId: '' as string,
  majorId: '' as string,
  classGroupId: '' as string,
})
const error = ref('')
const loading = ref(false)
const colleges = ref<College[]>([])
const majors = ref<Major[]>([])
const classes = ref<ClassGroup[]>([])

const filteredMajors = computed(() =>
  form.collegeId ? majors.value.filter((item) => String(item.collegeId) === String(form.collegeId)) : [],
)
const filteredClasses = computed(() =>
  form.majorId ? classes.value.filter((item) => String(item.majorId) === String(form.majorId)) : [],
)

async function loadOrg() {
  try {
    const tree = await apiFetch<{
      tree: { id: number; name: string; code: string; majors: { id: number; name: string; code: string; classes: { id: number; name: string; gradeYear?: number | null }[] }[] }[]
    }>('/api/organization/tree')
    colleges.value = tree.tree.map((c) => ({ id: c.id, name: c.name, code: c.code }))
    const allMajors: Major[] = []
    const allClasses: ClassGroup[] = []
    tree.tree.forEach((c) => {
      c.majors.forEach((m) => {
        allMajors.push({ id: m.id, collegeId: c.id, name: m.name, code: m.code, collegeName: c.name })
        m.classes.forEach((cl) => {
          allClasses.push({ id: cl.id, majorId: m.id, name: cl.name, majorName: m.name, collegeId: c.id, collegeName: c.name, gradeYear: cl.gradeYear ?? null })
        })
      })
    })
    majors.value = allMajors
    classes.value = allClasses
  } catch (err) {
    // 忽略：注册页允许组织架构为空
  }
}

function resetMajor() {
  form.majorId = ''
  form.classGroupId = ''
}

function resetClass() {
  form.classGroupId = ''
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await session.register({
      studentNo: form.studentNo,
      name: form.name,
      password: form.password,
      className: form.className,
      collegeId: form.collegeId || null,
      majorId: form.majorId || null,
      classGroupId: form.classGroupId || null,
    })
    router.push('/dashboard')
  } catch (err: any) {
    error.value = err.message || '注册失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadOrg)
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
          <span>学院</span>
          <select v-model="form.collegeId" @change="resetMajor">
            <option value="">不指定</option>
            <option v-for="item in colleges" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>专业</span>
          <select v-model="form.majorId" :disabled="!form.collegeId" @change="resetClass">
            <option value="">不指定</option>
            <option v-for="item in filteredMajors" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>班级</span>
          <select v-model="form.classGroupId" :disabled="!form.majorId">
            <option value="">不指定</option>
            <option v-for="item in filteredClasses" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>班级备注</span>
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
