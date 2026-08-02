import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'
import { useAuthStore } from '../store/auth'

// HTTP 请求封装：自动携带登录凭证、统一处理错误
const request = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 请求拦截器：每次请求自动带上登录凭证（token）
request.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截器：统一处理错误提示
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail

    if (status === 401) {
      // 登录过期：清空状态，跳回登录页
      const auth = useAuthStore()
      auth.logout()
      ElMessage.error(detail || '登录已过期，请重新登录')
      router.push('/login')
    } else {
      ElMessage.error(detail || '网络错误，请稍后重试')
    }
    return Promise.reject(error)
  },
)

export default request
