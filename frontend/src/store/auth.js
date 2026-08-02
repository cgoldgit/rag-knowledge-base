import { defineStore } from 'pinia'

// 登录状态管理：记住"谁登录了"，刷新页面也不丢失
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    username: localStorage.getItem('username') || '',
    isAdmin: localStorage.getItem('isAdmin') === 'true',
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
  },
  actions: {
    setLogin(token, username, isAdmin) {
      this.token = token
      this.username = username
      this.isAdmin = isAdmin
      localStorage.setItem('token', token)
      localStorage.setItem('username', username)
      localStorage.setItem('isAdmin', String(isAdmin))
    },
    logout() {
      this.token = ''
      this.username = ''
      this.isAdmin = false
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      localStorage.removeItem('isAdmin')
    },
  },
})
