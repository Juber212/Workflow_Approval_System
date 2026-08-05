import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

/** API 基础 URL（不含 /api/v1 后缀） */
export const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/api\/v1$/, '') || ''

/** 统一 API base URL（含 /api/v1 后缀）—— 手动拼接 URL（下载/签名等）共用，避免各处硬编码（P2-5 抽取） */
export function apiBase(): string {
  return import.meta.env.VITE_API_BASE_URL || '/api/v1'
}

/** 统一获取认证 Token（所有 token 访问的唯一入口） */
export function getToken(): string | null {
  return localStorage.getItem('token')
}

/** 后端统一响应包裹 —— {code, message, data}（P1-36：契约从注释级变编译级） */
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

/**
 * 自定义请求客户端类型 —— 覆盖 axios 默认返回 AxiosResponse，
 * 改为返回后端 body（响应拦截器已 `return response.data`，resolve 值即 ApiResponse<T>）。
 * 不用 `declare module 'axios'` 全局增强：axios 的 get 是三泛型 `get<T,R,D>`，
 * module augmentation 追加的重载会被原签名优先匹配而不生效，且会波及裸 axios 调用。
 */
export type ApiClient = Omit<AxiosInstance, 'get' | 'post' | 'put' | 'delete' | 'patch'> & {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>>
}

/** Axios 实例 —— 统一 baseURL、超时、拦截器 */
const BASE = apiBase()
const request: ApiClient = axios.create({
  baseURL: BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
}) as unknown as ApiClient

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

/** 消息去重 —— 相同消息 N 秒内不重复弹出（避免并发请求重复报错） */
const _msgCache = new Map<string, number>()
const MSG_THROTTLE_MS = 3000
const MAX_CACHE_SIZE = 100  // 缓存上限，防内存泄漏

function showErrorOnce(msg: string): void {
  const now = Date.now()
  const last = _msgCache.get(msg)
  if (last && now - last < MSG_THROTTLE_MS) return  // 3 秒内相同消息跳过
  _msgCache.set(msg, now)
  // 定期清理过期缓存 + 容量上限保护（避免 Map 无限增长）
  if (_msgCache.size > 50) {
    for (const [k, t] of _msgCache) {
      if (now - t > MSG_THROTTLE_MS) _msgCache.delete(k)
    }
  }
  // 容量上限兜底：删除最旧的条目
  if (_msgCache.size > MAX_CACHE_SIZE) {
    const oldest = [..._msgCache.entries()].sort((a, b) => a[1] - b[1])[0]
    if (oldest) _msgCache.delete(oldest[0])
  }
  ElMessage.error(msg)
}

// 401 跳转守卫 —— 防止并发 401 响应触发多次跳转
let _isRedirecting = false

/** 构造带 HTTP 状态码的错误对象（P1-34：供组件识别 403 等权限错误，渲染「无权查看」而非误导空态） */
function buildApiError(msg: string, status: number): Error & { status?: number } {
  const err = new Error(msg) as Error & { status?: number }
  err.status = status
  return err
}

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
        if (!isLoginRequest && !_isRedirecting) {
          _isRedirecting = true
          localStorage.removeItem('token')
          // 携带当前页面路径，登录成功后恢复
          const redirect = encodeURIComponent(window.location.pathname + window.location.search)
          window.location.href = `/login?redirect=${redirect}`
        }
        // 用后端返回的中文消息，避免 Axios 英文 error message
        const msg = data?.message || '认证失败'
        return Promise.reject(buildApiError(msg, status))
      }
      // 提取后端返回的中文错误消息
      const msg = data?.message || '请求失败，请稍后重试'
      showErrorOnce(msg)
      return Promise.reject(buildApiError(msg, status))
    }
    // 无响应的网络异常
    showErrorOnce('网络连接异常，请检查网络')
    return Promise.reject(error)
  },
)

export default request
