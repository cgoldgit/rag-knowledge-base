import request from './request'

// 认证相关接口
export const login = (data) => request.post('/auth/login', data)
export const register = (data) => request.post('/auth/register', data)
export const getMe = () => request.get('/auth/me')
export const changePassword = (data) => request.put('/auth/password', data)
