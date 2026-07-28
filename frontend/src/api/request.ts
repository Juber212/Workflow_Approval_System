import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

/** API 基础 URL（不含 /api/v1 后缀） */
export const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/api\/v1$/, '') || ''

/** 统一获取认证 Token（所有 token 访问的唯一入口） */
export function getToken(): string | null {
  return localStorage.getItem('token')
}

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
    const token = getToken()
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
      // 401 未认证 → 跳转登录（登录接口自身的 401 不跳转，取后端中文消息）
      if (status === 401) {
        const isLoginRequest = error.config?.url?.includes('/auth/login')
        if (!isLoginRequest) {
          localStorage.removeItem('token')
          window.location.href = '/login'
        }
        // 用后端返回的中文消息，避免 Axios 英文 error message
        const msg = data?.message || '认证失败'
        return Promise.reject(new Error(msg))
      }
      // 提取后端返回的中文错误消息
      const msg = data?.message || '请求失败，请稍后重试'
      ElMessage.error(msg)
      return Promise.reject(new Error(msg))
    }
    // 无响应的网络异常
    ElMessage.error('网络连接异常，请检查网络')
    return Promise.reject(error)
  },
)

export default request
