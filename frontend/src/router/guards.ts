/** 全局路由守卫 —— 鉴权 + 角色权限 + Token 过期检测 */
import type { Router } from 'vue-router'
import { useUserStore } from '@/stores/user'

/** 解析 JWT payload 中的 exp 字段（不解码签名，仅解析 payload） */
function getTokenExp(token: string): number {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp || 0
  } catch {
    return 0
  }
}

/** 判断 Token 是否已过期 */
function isTokenExpired(token: string): boolean {
  const exp = getTokenExp(token)
  if (!exp) return false
  // 提前 60 秒判定过期，避免临界状态
  return Date.now() / 1000 > exp - 60
}

/**
 * 安装全局路由守卫
 * - 未登录 → 跳转 /login?redirect=原路径
 * - Token 过期 → 清除登录态 → 跳转 /login
 * - 已登录访问 /login → 跳转 /dashboard
 * - 角色不匹配 → 跳转 /403
 */
export function setupRouterGuards(router: Router) {
  router.beforeEach(async (to, _from, next) => {
    const userStore = useUserStore()

    // ========== 1. Token 过期检测 ==========
    if (userStore.token && isTokenExpired(userStore.token)) {
      userStore.clearToken()
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }

    // ========== 2. 公开页面直接放行 ==========
    const publicPaths = ['/login', '/404', '/403']
    if (publicPaths.includes(to.path)) {
      // 已登录用户访问登录页 → 重定向到 Dashboard
      if (to.path === '/login' && userStore.isLoggedIn) {
        next('/dashboard')
        return
      }
      next()
      return
    }

    // ========== 3. 未登录 → 跳转登录页 ==========
    if (!userStore.isLoggedIn) {
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }

    // ========== 4. 已登录但无用户信息 → 从服务端恢复 ==========
    if (!userStore.userInfo) {
      try {
        await userStore.fetchUserInfo()
      } catch {
        userStore.clearToken()
        next({ path: '/login', query: { redirect: to.fullPath } })
        return
      }
    }

    // ========== 5. 角色权限校验 ==========
    const requiredRoles = to.meta.roles as string[] | undefined
    if (requiredRoles && requiredRoles.length > 0) {
      const userRoles = userStore.userInfo?.roles || []
      const hasRole = requiredRoles.some((r) => userRoles.includes(r))
      if (!hasRole) {
        next('/403')
        return
      }
    }

    next()
  })
}
