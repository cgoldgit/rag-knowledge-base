import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../store/auth'

// 页面路由表：定义每个网址对应哪个页面
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true },  // 公开页面，无需登录
  },
  {
    path: '/',
    component: () => import('../views/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'Chat',
        component: () => import('../views/ChatView.vue'),
      },
      {
        path: 'kb',
        name: 'KnowledgeBase',
        component: () => import('../views/KnowledgeBaseView.vue'),
        meta: { adminOnly: true },  // 仅管理员可访问
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('../views/ProfileView.vue'),
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：没登录不能进系统，普通用户不能进知识库管理
router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    return true
  }
  if (!auth.isLoggedIn) {
    return { path: '/login' }
  }
  if (to.meta.adminOnly && !auth.isAdmin) {
    return { path: '/' }  // 非管理员回到问答页
  }
  return true
})

export default router
