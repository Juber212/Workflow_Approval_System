import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

/** API 基础 URL（不含 /api/v1 后缀） */
export const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/api\/v1$/, '') || ''

/** Axios 实例 —— 统一 baseURL、超时、拦截器 */
const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const request: AxiosInstance = axios.create({
  baseURL: BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

/** 请求拦截器 —— 自动注入 Token */
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

/** 响应拦截器 —— 统一错误处理、401 跳转登录 */
request.interceptors.response.use(
  (response: AxiosResponse) => {
    // HTTP 2xx 即成功，直接返回 body
    return response.data
  },
  (error) => {
    // HTTP 4xx/5xx 错误响应
    if (error.response) {
      const { status, data } = error.response
      // 401 未认证 → 跳转登录
      if (status === 401) {
        localStorage.removeItem('token')
        window.location.href = '/login'
        return Promise.reject(error)
      }
      // 提取后端返回的业务错误消息
      const msg = data?.message || `请求失败 (${status})`
      ElMessage.error(msg)
      return Promise.reject(new Error(msg))
    }
    // 无响应的网络异常
    ElMessage.error('网络连接异常，请检查网络')
    return Promise.reject(error)
  },
)

export default request
