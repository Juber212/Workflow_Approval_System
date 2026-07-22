import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 通知计数 Store —— 供个人中心页面和侧边栏共享待办/校验/审批数量
 *
 * AppLayout onMounted 时并行请求 API 写入此 Store，
 * 侧边栏读取 hasPending 决定是否显示小红点，
 * 个人中心顶部 radio-button 读取 projectPending / proposalPending 显示分类型数字徽章。
 */
export const useNotificationStore = defineStore('notification', () => {
  /** 我的待办数量（项目 + 方案合计） */
  const taskCount = ref(0)
  /** 我的校验数量（仅项目有校验） */
  const checkCount = ref(0)
  /** 我的审批数量（项目 + 方案合计） */
  const approvalCount = ref(0)

  /** 项目待处理总数（任务+校验+审批） */
  const projectPending = ref(0)
  /** 方案待处理总数（任务+审批，方案无校验） */
  const proposalPending = ref(0)

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

  /** 设置分类型待处理数（供项目/方案 radio-button 徽章使用） */
  function setTypedCounts(project: number, proposal: number) {
    projectPending.value = project
    proposalPending.value = proposal
  }

  /** 退出登录后清空 */
  function clearAll() {
    taskCount.value = 0
    checkCount.value = 0
    approvalCount.value = 0
    projectPending.value = 0
    proposalPending.value = 0
  }

  return { taskCount, checkCount, approvalCount, projectPending, proposalPending, hasPending, totalPending, setCounts, setTypedCounts, clearAll }
})
