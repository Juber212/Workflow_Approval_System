/** 通知 API —— 站内通知列表 + 未读数 + WebSocket 实时推送 */

import { ref, onMounted, onUnmounted, type Ref } from 'vue'
import request, { API_BASE, getToken } from './request'
import { useNotificationStore } from '@/stores/notification'

/** 通知对象（与后端 NotificationOut 对应） */
export interface NotificationItem {
  id: number
  type: string
  title: string
  content: string
  link: string | null
  is_read: boolean
  created_at: string
}

/** 未读数响应 */
export interface UnreadCount {
  count: number
}

// ==================== REST API ====================

/** 获取通知列表（分页） */
export async function fetchNotifications(page = 1, pageSize = 20): Promise<{
  items: NotificationItem[]
  total: number
  page: number
  page_size: number
}> {
  const res = await request.get('/notifications', { params: { page, page_size: pageSize } })
  return res.data
}

/** 待办汇总计数响应 —— 含完整 project/proposal 分类 breakdown */
export interface SummaryCounts {
  // 汇总（侧边栏角标用）
  task_count: number
  check_count: number
  approval_count: number
  endorsement_count: number
  project_pending: number
  proposal_pending: number
  // 分类 breakdown（个人中心 Tab 角标用）
  project_task_count: number
  project_check_count: number
  project_approval_count: number
  project_endorsement_count: number
  proposal_task_count: number
  proposal_approval_count: number
  proposal_endorsement_count: number
}

/** 获取待办/校验/审批汇总计数 —— 一次请求替代 7 次独立分页查询 */
export async function fetchSummaryCounts(): Promise<SummaryCounts> {
  const res = await request.get('/notifications/summary')
  return res.data
}

/** 获取未读通知数量 */
export async function fetchUnreadCount(): Promise<UnreadCount> {
  const res = await request.get('/notifications/unread-count')
  return res.data
}

/** 标记单条通知为已读 */
export async function markNotificationRead(id: number): Promise<void> {
  await request.put(`/notifications/${id}/read`)
}

/** 标记全部通知为已读 */
export async function markAllNotificationsRead(): Promise<void> {
  await request.put('/notifications/read-all')
}

/** 删除单条通知（终局事件通知如「项目已终止」点击后移除） */
export async function deleteNotification(id: number): Promise<void> {
  await request.delete(`/notifications/${id}`)
}

// ==================== WebSocket ====================

/** 通知类型中文映射 */
export const NOTICE_TYPE_LABELS: Record<string, string> = {
  task_assigned: '新任务',
  check_assigned: '待校验',
  approval_assigned: '待审批',
  endorsement_assigned: '待批准',
  check_returned: '校验退回',
  approval_rejected: '审批驳回',
  final_rejected: '终审驳回',
  endorsement_rejected: '批准驳回',
  instance_terminated: '项目已终止',
}

/** 通知类型图标 */
export const NOTICE_TYPE_ICONS: Record<string, string> = {
  task_assigned: '📋',
  check_assigned: '🔍',
  approval_assigned: '✅',
  endorsement_assigned: '⭐',
  check_returned: '↩️',
  approval_rejected: '❌',
  final_rejected: '↩️',
  endorsement_rejected: '❌',
  instance_terminated: '⛔',
}

// ========== M30：WebSocket 全局单例（引用计数） ==========
// AppLayout 面包屑铃铛 + Dashboard 页铃铛各挂载一份 NotificationBell，若各自建连
// 会在进出 Dashboard 时反复 WS 断连/重连。改为模块级单例：首个使用组件建连、
// 最后一个组件卸载时断开，最新通知/未读数全局共享。
const wsState: {
  latestNotice: Ref<NotificationItem | null>
  unreadCount: Ref<number>
  wsConnected: Ref<boolean>
  ws: WebSocket | null
  reconnectTimer: ReturnType<typeof setTimeout> | null
  disposed: boolean      // 所有组件已卸载标记（connect 入口检查，防孤儿连接）
  manualClose: boolean   // 手动关闭标记（onclose 不再触发重连）
  refCount: number       // 当前使用该连接的组件数
} = {
  latestNotice: ref(null),
  unreadCount: ref(0),
  wsConnected: ref(false),
  ws: null,
  reconnectTimer: null,
  disposed: false,
  manualClose: false,
  refCount: 0,
}

/**
 * WebSocket 通知 Hook —— 全局单例连接（M30），暴露最新通知和未读数
 *
 * 用法（在组件 setup 中）：
 *   const { latestNotice, unreadCount, wsConnected } = useNotificationSocket()
 */
export function useNotificationSocket() {
  const { latestNotice, unreadCount, wsConnected } = wsState

  /** 刷新侧边栏红点 + 个人中心角标（notifyStore）并派发事件供 profile 页面更新 Tab 角标 */
  function refreshStoreCounts() {
    const notifyStore = useNotificationStore()
    fetchSummaryCounts().then(summary => {
      // 更新侧边栏角标
      notifyStore.setCounts(summary.task_count, summary.check_count, summary.approval_count, summary.endorsement_count)
      notifyStore.setTypedCounts(summary.project_pending, summary.proposal_pending)
      // 派发事件供个人中心页面刷新 Tab 角标
      window.dispatchEvent(new CustomEvent('counts-refreshed', { detail: summary }))
    }).catch(() => {})
  }

  /** 构建 WebSocket URL（http→ws 协议替换；token 不走 URL，改为首条消息认证） */
  function buildWsUrl(): string {
    const base = API_BASE.replace(/^http/, 'ws') || ''
    return `${base}/api/v1/ws`
  }

  function connect() {
    // P1-30：所有组件已卸载则不再建连（防孤儿连接：卸载后的重连 timer 触发到此直接退出）
    if (wsState.disposed) return
    const token = getToken()
    if (!token) return

    const wsUrl = buildWsUrl()

    let ws: WebSocket
    try {
      ws = new WebSocket(wsUrl)
      wsState.ws = ws
    } catch {
      // WebSocket 不支持时静默降级
      return
    }

    ws.onopen = () => {
      // 连接建立后立即发送认证消息（首条消息，避免 token 出现在日志中）
      ws.send(JSON.stringify({ type: 'auth', token }))
      wsConnected.value = true
      if (wsState.reconnectTimer) { clearTimeout(wsState.reconnectTimer); wsState.reconnectTimer = null }
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'notification' && msg.data) {
          latestNotice.value = msg.data
          // 推送新通知时刷新未读数 + 侧边栏红点 + 个人中心角标
          fetchUnreadCount().then(res => { unreadCount.value = res.count }).catch(() => {})
          refreshStoreCounts()
        } else if (msg.type === 'refresh_count') {
          // 后端 clear_related 后静默刷新铃铛未读数 + 侧边栏红点 + 个人中心角标
          fetchUnreadCount().then(res => { unreadCount.value = res.count }).catch(() => {})
          refreshStoreCounts()
        } else if (msg.type === 'conversion_all_done') {
          // PDF 转换全部完成（50+ 优化）：触发自定义事件，供 TaskDetail 监听
          window.dispatchEvent(new CustomEvent('conversion-all-done', {
            detail: { task_id: msg.task_id, status: msg.status, total: msg.total, ready: msg.ready, failed: msg.failed }
          }))
        }
      } catch {
        // 消息解析失败，静默忽略
      }
    }

    ws.onclose = (event) => {
      wsConnected.value = false
      // 手动关闭（disconnect 发起）不重连
      if (wsState.manualClose) { wsState.manualClose = false; return }
      // 认证失败（4001）不重连，其他情况 5 秒后自动重连（connect 入口会校验 disposed）
      if (event.code !== 4001) {
        wsState.reconnectTimer = setTimeout(connect, 5000)
      }
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect() {
    wsState.disposed = true  // P1-30：所有组件已卸载，任何重连路径不再执行
    if (wsState.reconnectTimer) { clearTimeout(wsState.reconnectTimer); wsState.reconnectTimer = null }
    if (wsState.ws) {
      wsState.manualClose = true   // 手动关闭：onclose 不再重连
      wsState.ws.onclose = null    // 双保险：直接断开回调，避免 close 触发重连
      wsState.ws.close()
      wsState.ws = null
    }
    wsConnected.value = false
  }

  // M30：引用计数——首个组件挂载时建连，最后一个组件卸载时断开
  onMounted(() => {
    // 先拉取当前未读数
    fetchUnreadCount().then(res => { unreadCount.value = res.count }).catch(() => {})
    wsState.refCount += 1
    if (wsState.refCount === 1) {
      wsState.disposed = false  // 重新进入页面：重置卸载标记，允许建连
      connect()
    }
  })

  onUnmounted(() => {
    wsState.refCount -= 1
    if (wsState.refCount <= 0) {
      wsState.refCount = 0
      disconnect()
    }
  })

  return { latestNotice, unreadCount, wsConnected, fetchUnreadCount }
}
