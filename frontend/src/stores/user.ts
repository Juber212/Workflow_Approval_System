import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserInfo } from '@/types/user'
import { loginApi, logoutApi, getMeApi, toUserInfo } from '@/api/auth'

/** 用户状态管理 —— 存储当前登录用户信息与 token */
export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const userInfo = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  /** 当前用户是否为所长 */
  const isManager = computed(() => userInfo.value?.roles?.includes('manager') ?? false)
  /** 当前用户是否为系统管理员 */
  const isAdmin = computed(() => userInfo.value?.roles?.includes('system_admin') ?? false)

  /** 登录：调用 API → 存储 token → 解析用户信息 */
  async function login(username: string, password: string) {
    const data = await loginApi({ username, password })
    token.value = data.token
    userInfo.value = toUserInfo(data)
    localStorage.setItem('token', data.token)
    return data
  }

  /** 从服务端刷新当前用户信息（用于页面刷新后恢复） */
  async function fetchUserInfo() {
    const data = await getMeApi()
    userInfo.value = toUserInfo(data)
  }

  /** 退出登录：调用 API → 清除本地状态 */
  async function logout() {
    try {
      await logoutApi()
    } catch {
      // 即使接口失败也清除本地状态
    }
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  /** 清除登录态（不调 API，用于 Token 过期等场景） */
  function clearToken() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return { token, userInfo, isLoggedIn, isManager, isAdmin, login, fetchUserInfo, logout, clearToken }
})
