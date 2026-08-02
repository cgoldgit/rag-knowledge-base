<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '../store/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => (route.path.startsWith('/kb') ? '/kb' : '/'))

// 侧边栏菜单：管理员多一个"知识库管理"入口
const menus = computed(() => {
  const items = [
    { path: '/', label: '知识库问答', icon: 'ChatDotRound' },
  ]
  if (auth.isAdmin) {
    items.push({ path: '/kb', label: '知识库管理', icon: 'FolderOpened' })
  }
  return items
})

function handleLogout() {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '退出',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    auth.logout()
    router.push('/login')
  })
}
</script>

<template>
  <el-container class="main-layout">
    <!-- 侧边栏 -->
    <el-aside width="200px" class="sidebar">
      <div class="logo-area">
        <div class="logo-icon">📚</div>
        <div class="logo-text">知识库问答</div>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="menu"
      >
        <el-menu-item
          v-for="item in menus"
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶栏 -->
      <el-header class="header">
        <div class="header-title">
          {{ route.path.startsWith('/kb') ? '知识库管理' : '知识库问答' }}
        </div>
        <div class="header-right">
          <el-dropdown>
            <span class="user-info">
              <el-avatar :size="32" class="avatar">{{ auth.username.charAt(0).toUpperCase() }}</el-avatar>
              <span class="username">{{ auth.username }}</span>
              <el-tag v-if="auth.isAdmin" size="small" type="danger">管理员</el-tag>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/settings')">设置</el-dropdown-item>
                <el-dropdown-item @click="router.push('/profile')">修改密码</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.main-layout {
  height: 100%;
}

.sidebar {
  background: #1e3a5f;
  color: #fff;
  display: flex;
  flex-direction: column;
}

.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}

.menu {
  border-right: none;
  background: transparent;
  flex: 1;
}

.menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.75);
}

.menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.menu :deep(.el-menu-item.is-active) {
  background: #2563eb;
  color: #fff;
}

.header {
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #1e3a5f;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.avatar {
  background: #2563eb;
  color: #fff;
}

.username {
  font-size: 14px;
  color: #333;
}

.content {
  padding: 0;
  overflow: hidden;
}
</style>
