<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { changePassword } from '../api/auth'

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})
const loading = ref(false)

async function handleSubmit() {
  if (!form.oldPassword || !form.newPassword) {
    ElMessage.warning('请填写完整')
    return
  }
  if (form.newPassword.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (form.newPassword !== form.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  loading.value = true
  try {
    await changePassword({
      old_password: form.oldPassword,
      new_password: form.newPassword,
    })
    ElMessage.success('密码修改成功')
    form.oldPassword = ''
    form.newPassword = ''
    form.confirmPassword = ''
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="profile-page">
    <el-card class="profile-card">
      <template #header>
        <span>修改密码</span>
      </template>
      <el-form label-width="90px" @submit.prevent="handleSubmit">
        <el-form-item label="原密码">
          <el-input
            v-model="form.oldPassword"
            type="password"
            show-password
            placeholder="请输入原密码"
          />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="form.newPassword"
            type="password"
            show-password
            placeholder="至少 6 位"
          />
        </el-form-item>
        <el-form-item label="确认新密码">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            placeholder="再次输入新密码"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleSubmit">
            确认修改
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.profile-page {
  padding: 20px;
  display: flex;
  justify-content: center;
}

.profile-card {
  width: 480px;
}
</style>
