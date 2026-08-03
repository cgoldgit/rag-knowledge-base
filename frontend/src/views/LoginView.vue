<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, register } from '../api/auth'
import { useAuthStore } from '../store/auth'

const router = useRouter()
const auth = useAuthStore()

// 登录/注册模式切换
const isLogin = ref(true)
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
})

async function handleSubmit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    if (isLogin.value) {
      // 登录
      const res = await login({ username: form.username, password: form.password })
      auth.setLogin(res.access_token, res.username, res.is_admin)
      ElMessage.success(`欢迎回来，${res.username}！`)
      router.push('/')
    } else {
      // 注册
      if (form.password.length < 6) {
        ElMessage.warning('密码至少需要 6 位')
        return
      }
      if (form.password !== form.confirmPassword) {
        ElMessage.warning('两次输入的密码不一致')
        return
      }
      const res = await register({ username: form.username, password: form.password })
      auth.setLogin(res.access_token, res.username, res.is_admin)
      ElMessage.success('注册成功，欢迎使用！')
      router.push('/')
    }
  } catch (e) {
    // 错误提示已在请求封装中处理
  } finally {
    loading.value = false
  }
}

function switchMode() {
  isLogin.value = !isLogin.value
  form.confirmPassword = ''
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <h1>电商知识库问答系统</h1>
        <p>基于 LangChain 的 RAG 智能问答</p>
      </div>

      <el-form @submit.prevent="handleSubmit">
        <el-form-item>
          <el-input
            v-model="form.username"
            placeholder="用户名"
            size="large"
            :prefix-icon="'User'"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            :prefix-icon="'Lock'"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>
        <el-form-item v-if="!isLogin">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="确认密码"
            size="large"
            show-password
            :prefix-icon="'Lock'"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="submit-btn"
          :loading="loading"
          @click="handleSubmit"
        >
          {{ isLogin ? '登 录' : '注 册' }}
        </el-button>
      </el-form>

      <div class="switch-line">
        <span v-if="isLogin">还没有账号？</span>
        <span v-else>已有账号？</span>
        <el-link type="primary" @click="switchMode">
          {{ isLogin ? '立即注册' : '去登录' }}
        </el-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #3b82f6 100%);
}

.login-card {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h1 {
  font-size: 22px;
  color: #1e3a5f;
  margin-bottom: 8px;
}

.login-header p {
  font-size: 13px;
  color: #909399;
}

.submit-btn {
  width: 100%;
  font-size: 16px;
  letter-spacing: 4px;
}

.switch-line {
  margin-top: 16px;
  text-align: center;
  font-size: 14px;
  color: #909399;
}
</style>
