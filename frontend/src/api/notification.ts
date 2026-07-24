/** 通知 API —— 站内通知列表 + 未读数 + WebSocket 实时推送 */

import { ref, onMounted, onUnmounted } from 'vue'
import request, { API_BASE, getToken } from './request'

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
  const { data } = await request.get('/notifications', { params: { page, page_size: pageSize } })
  return data
}

/** 待办汇总计数响应 */
export interface SummaryCounts {
  task_count: number
  check_count: number
  approval_count: number
  project_pending: number
  proposal_pending: number
}

/** 获取待办/校验/审批汇总计数 —— 一次请求替代 7 次独立分页查询 */
export async function fetchSummaryCounts(): Promise<SummaryCounts> {
  const { data } = await request.get('/notifications/summary')
  return data
}

/** 获取未读通知数量 */
export async function fetchUnreadCount(): Promise<UnreadCount> {
  const { data } = await request.get('/notifications/unread-count')
  return data
}

/** 标记单条通知为已读 */
export async function markNotificationRead(id: number): Promise<void> {
  await request.put(`/notifications/${id}/read`)
}

/** 标记全部通知为已读 */
export async function markAllNotificationsRead(): Promise<void> {
  await request.put('/notifications/read-all')
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
}

/**
 * WebSocket 通知 Hook —— 自动连接/重连，暴露最新通知和未读数
 *
 * 用法（在组件 setup 中）：
 *   const { latestNotice, unreadCount, wsConnected } = useNotificationSocket()
 */
export function useNotificationSocket() {
  const latestNotice = ref<NotificationItem | null>(null)
  const unreadCount = ref(0)
  const wsConnected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    const token = getToken()
    if (!token) return

    // 构建 WebSocket URL（token 不再经 URL 传递，改为首条消息认证）
    const base = API_BASE.replace(/^http/, 'ws') || ''
    const wsUrl = `${base}/api/v1/ws`

    try {
      ws = new WebSocket(wsUrl)
    } catch {
      // WebSocket 不支持时静默降级
      return
    }

    ws.onopen = () => {
      // 连接建立后立即发送认证消息（首条消息，避免 token 出现在日志中）
      ws!.send(JSON.stringify({ type: 'auth', token }))
      wsConnected.value = true
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'notification' && msg.data) {
          latestNotice.value = msg.data
          // 推送新通知时刷新未读数
          fetchUnreadCount().then(res => { unreadCount.value = res.count }).catch(() => {})
        } else if (msg.type === 'refresh_count') {
          // 后端 clear_related 后通知前端刷新铃铛未读数（静默，不弹出气泡）
          fetchUnreadCount().then(res => { unreadCount.value = res.count }).catch(() => {})
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
      // 认证失败（4001）不重连，其他情况 5 秒后自动重连
      if (event.code !== 4001) {
        reconnectTimer = setTimeout(connect, 5000)
      }
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect() {
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
    if (ws) { ws.close(); ws = null }
    wsConnected.value = false
  }

  // 组件挂载时连接，卸载时断开
  onMounted(() => {
    // 先拉取当前未读数
    fetchUnreadCount().then(res => { unreadCount.value = res.count }).catch(() => {})
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return { latestNotice, unreadCount, wsConnected, fetchUnreadCount }
}
