<template>
  <!-- 通知铃铛 —— Bell 图标 + 未读红点 + 下拉面板 + 实时气泡 -->
  <div class="notif-bell" ref="bellRef">
    <button class="notif-bell__btn" @click="togglePanel" :title="`通知 (${unreadCount} 条未读)`">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
      <!-- 未读红点 -->
      <span v-if="unreadCount > 0" class="notif-bell__badge">
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </span>
    </button>

    <!-- 实时推送气泡 —— 从铃铛下方弹出，5秒自动消失 -->
    <Transition name="toast-pop">
      <div v-if="popupNotice" class="toast-popup" @click="onPopupClick">
        <span class="toast-popup__icon">{{ typeIcon(popupNotice.type) }}</span>
        <div class="toast-popup__body">
          <div class="toast-popup__title">{{ popupNotice.title }}</div>
          <div class="toast-popup__content">{{ popupNotice.content }}</div>
        </div>
      </div>
    </Transition>

    <!-- 下拉面板 -->
    <Transition name="notif-fade">
      <div v-if="showPanel" class="notif-panel">
        <div class="notif-panel__header">
          <span>通知</span>
          <button
            v-if="unreadCount > 0"
            class="notif-panel__read-all"
            @click="handleReadAll"
          >全部已读</button>
        </div>

        <div class="notif-panel__body">
          <template v-if="loading">
            <div class="notif-panel__loading">加载中...</div>
          </template>
          <template v-else-if="notifications.length === 0">
            <div class="notif-panel__empty">暂无通知</div>
          </template>
          <template v-else>
            <div
              v-for="item in notifications"
              :key="item.id"
              class="notif-item"
              :class="{ 'notif-item--unread': !item.is_read }"
              @click="handleClick(item)"
            >
              <span class="notif-item__icon">{{ typeIcon(item.type) }}</span>
              <div class="notif-item__body">
                <div class="notif-item__title">
                  <span class="notif-item__type">{{ typeLabel(item.type) }}</span>
                  {{ item.title }}
                </div>
                <div class="notif-item__content">{{ item.content }}</div>
                <div class="notif-item__time">{{ formatTime(item.created_at) }}</div>
              </div>
              <span v-if="!item.is_read" class="notif-item__dot" />
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchNotifications, markNotificationRead, markAllNotificationsRead,
  NOTICE_TYPE_LABELS, NOTICE_TYPE_ICONS,
  useNotificationSocket,
  type NotificationItem,
} from '@/api/notification'

const router = useRouter()

// WebSocket 实时推送 —— 自动连接 + 重连 + 未读数更新
const { latestNotice, unreadCount } = useNotificationSocket()

// ---- 实时气泡：收到 WebSocket 推送时从铃铛下方弹出，5 秒自动消失 ----
const popupNotice = ref<NotificationItem | null>(null)
let popupTimer: ReturnType<typeof setTimeout> | null = null

watch(latestNotice, (notice) => {
  if (!notice) return
  // 清除上一个气泡的定时器
  if (popupTimer) clearTimeout(popupTimer)
  popupNotice.value = notice
  popupTimer = setTimeout(() => {
    popupNotice.value = null
  }, 5000)
})

/** 点击气泡 → 跳转并关闭 */
function onPopupClick() {
  if (!popupNotice.value) return
  if (popupNotice.value.link) router.push(popupNotice.value.link)
  popupNotice.value = null
  if (popupTimer) clearTimeout(popupTimer)
}

const showPanel = ref(false)
const loading = ref(false)
const notifications = ref<NotificationItem[]>([])
const bellRef = ref<HTMLElement | null>(null)

/** 切换面板 */
async function togglePanel() {
  showPanel.value = !showPanel.value
  if (showPanel.value) {
    await loadNotifications()
  }
}

/** 加载通知列表 */
async function loadNotifications() {
  loading.value = true
  try {
    const res = await fetchNotifications(1, 20)
    notifications.value = res.items
  } catch {
    // 静默失败
  } finally {
    loading.value = false
  }
}

/** 点击通知 → 跳转 + 标记已读 */
async function handleClick(item: NotificationItem) {
  if (!item.is_read) {
    await markNotificationRead(item.id)
    item.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  }
  if (item.link) {
    router.push(item.link)
  }
  showPanel.value = false
}

/** 全部已读 */
async function handleReadAll() {
  await markAllNotificationsRead()
  notifications.value.forEach(n => { n.is_read = true })
  unreadCount.value = 0
}

/** 通知类型中文 */
function typeLabel(type: string) {
  return NOTICE_TYPE_LABELS[type] || type
}

/** 通知类型图标 */
function typeIcon(type: string) {
  return NOTICE_TYPE_ICONS[type] || '📌'
}

/** 时间格式化 */
function formatTime(dt: string) {
  if (!dt) return ''
  const d = new Date(dt)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`
  return d.toLocaleDateString('zh-CN')
}

/** 点击面板外部关闭 */
function handleClickOutside(e: MouseEvent) {
  if (bellRef.value && !bellRef.value.contains(e.target as Node)) {
    showPanel.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
/* ==================== Bell 按钮 ==================== */
.notif-bell {
  position: relative;
}
.notif-bell__btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--el-text-color-regular);
  cursor: pointer;
  transition: background 0.2s;
}
.notif-bell__btn:hover {
  background: var(--el-fill-color-light);
}
.notif-bell__badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  line-height: 16px;
  text-align: center;
  color: #fff;
  background: var(--el-color-danger);
}

/* ==================== 实时推送气泡 ==================== */
.toast-popup {
  position: absolute;
  top: 44px;
  right: 0;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 320px;
  padding: 12px 16px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
  z-index: 1001;
  cursor: pointer;
  transition: background 0.15s;
}
.toast-popup:hover {
  background: var(--el-fill-color-light);
}
.toast-popup__icon {
  flex-shrink: 0;
  font-size: 20px;
  line-height: 22px;
  margin-top: 1px;
}
.toast-popup__body {
  flex: 1;
  min-width: 0;
}
.toast-popup__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.4;
}
.toast-popup__content {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 气泡进出动画 */
.toast-pop-enter-active { transition: opacity 0.25s, transform 0.25s ease-out; }
.toast-pop-leave-active { transition: opacity 0.2s, transform 0.2s ease-in; }
.toast-pop-enter-from { opacity: 0; transform: translateY(-10px) scale(0.95); }
.toast-pop-leave-to { opacity: 0; transform: translateY(-6px) scale(0.98); }

/* ==================== 下拉面板 ==================== */
.notif-panel {
  position: absolute;
  top: 44px;
  right: 0;
  width: 380px;
  max-height: 480px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.notif-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.notif-panel__read-all {
  font-size: 12px;
  color: var(--el-color-primary);
  border: none;
  background: none;
  cursor: pointer;
}
.notif-panel__read-all:hover {
  text-decoration: underline;
}
.notif-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}
.notif-panel__loading,
.notif-panel__empty {
  padding: 40px 16px;
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}

/* ==================== 通知条目 ==================== */
.notif-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s;
}
.notif-item:hover {
  background: var(--el-fill-color-light);
}
.notif-item--unread {
  background: var(--el-color-primary-light-9);
}
.notif-item__icon {
  flex-shrink: 0;
  font-size: 16px;
  line-height: 20px;
  margin-top: 1px;
}
.notif-item__body {
  flex: 1;
  min-width: 0;
}
.notif-item__title {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  line-height: 1.4;
}
.notif-item__type {
  display: inline-block;
  font-size: 11px;
  padding: 0 6px;
  border-radius: 3px;
  background: var(--el-fill-color);
  margin-right: 6px;
  vertical-align: 1px;
}
.notif-item__content {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.notif-item__time {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-top: 2px;
}
.notif-item__dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-primary);
  margin-top: 7px;
}

/* ==================== 过渡动画 ==================== */
.notif-fade-enter-active,
.notif-fade-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}
.notif-fade-enter-from,
.notif-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
