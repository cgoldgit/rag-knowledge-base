import request from './request'

// 用户设置
export const getSettings = () => request.get('/auth/settings')
export const saveSettings = (data) => request.put('/auth/settings', data)

// 回答评价
export const rateMessage = (messageId, rating) =>
  request.put(`/conversations/messages/${messageId}/rating`, { rating })
