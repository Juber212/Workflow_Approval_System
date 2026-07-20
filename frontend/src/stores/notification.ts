import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 通知计数 Store —— 供个人中心页面和侧边栏共享待办/校验/审批数量
 *
 * 个人中心页面 onMounted 时并行请求三个 API 并将 total 写入此 Store，
 * 侧边栏 AppLayout 读取 hasPending 决定是否显示小圆点。
 */
export const useNotificationStore = defineStore('notification', () => {
  /** 我的待办数量 */
  const taskCount = ref(0)
  /** 我的校验数量 */
  const checkCount = ref(0)
  /** 我的审批数量 */
  const approvalCount = ref(0)

  /** 是否有未处理事项（汇总 > 0 即有小圆点） */
  const hasPending = computed(() => taskCount.value + checkCount.value + approvalCount.value > 0)

  /** 待处理总数（红色徽章显示的数字） */
  const totalPending = computed(() => taskCount.value + checkCount.value + approvalCount.value)

  /** 批量设置三个数量 */
  function setCounts(tasks: number, checks: number, approvals: number) {
    taskCount.value = tasks
    checkCount.value = checks
    approvalCount.value = approvals
  }

  /** 退出登录后清空 */
  function clearAll() {
    taskCount.value = 0
    checkCount.value = 0
    approvalCount.value = 0
  }

  return { taskCount, checkCount, approvalCount, hasPending, totalPending, setCounts, clearAll }
})
