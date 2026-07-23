/** 标签/状态映射工具函数 —— 优先级、实例状态、角色、任务/校验/审批状态等中文映射 */

/** 优先级中文映射 */
export function priLabel(p: string): string {
  const m: Record<string, string> = { urgent: '紧急', high: '高', normal: '普通', low: '低' }
  return m[p] || p
}

/** 角色中文映射 */
export function roleLabel(r: string): string {
  const m: Record<string, string> = { system_admin: '管理员', manager: '所长', user: '用户' }
  return m[r] || r
}

/** 流程实例状态 CSS 类名 */
export function instStatusClass(s: string): string {
  const m: Record<string, string> = { created: 'status-tag--draft', running: 'status-tag--running', completed: 'status-tag--completed', terminated: 'status-tag--terminated' }
  return m[(s || '').toLowerCase()] || ''
}

/** 流程实例状态中文 */
export function instStatusLabel(s: string): string {
  const m: Record<string, string> = { created: '已创建', running: '运行中', completed: '已完成', terminated: '已终止' }
  return m[(s || '').toLowerCase()] || s
}

// ========== 任务状态 ==========

/** 任务状态 CSS 类名 */
export function taskStatusClass(s: string): string {
  const m: Record<string, string> = { pending: 'status-tag--running', processing: 'status-tag--draft', waiting_check: 'status-tag--running', waiting_approval: 'status-tag--running', completed: 'status-tag--completed', overdue: 'status-tag--terminated' }
  return m[s] || ''
}

/** 任务状态中文 */
export function taskStatusLabel(s: string): string {
  const m: Record<string, string> = { pending: '待处理', processing: '处理中', waiting_check: '待校验', waiting_approval: '待审批', completed: '已完成' }
  return m[s] || s
}

// ========== 校验状态 ==========

/** 校验状态 CSS 类名 */
export function checkStatusClass(s: string): string {
  const m: Record<string, string> = { pending: 'status-tag--running', passed: 'status-tag--completed', returned: 'status-tag--terminated', terminated: 'status-tag--terminated' }
  return m[s] || ''
}

/** 校验状态中文 */
export function checkStatusLabel(s: string): string {
  const m: Record<string, string> = { pending: '待校验', passed: '已通过', returned: '已退回', terminated: '已终止' }
  return m[s] || s
}

// ========== 审批状态 ==========

/** 审批状态 CSS 类名 */
export function approvalStatusClass(s: string): string {
  const m: Record<string, string> = { pending: 'status-tag--running', approved: 'status-tag--completed', rejected: 'status-tag--terminated', terminated: 'status-tag--terminated' }
  return m[s] || ''
}

/** 审批状态中文 */
export function approvalStatusLabel(s: string): string {
  const m: Record<string, string> = { pending: '待审批', approved: '已通过', rejected: '已退回', terminated: '已终止' }
  return m[s] || s
}

// ========== 批准状态（Endorsement） ==========

/** 批准状态 CSS 类名 */
export function endorsementStatusClass(s: string): string {
  const m: Record<string, string> = { pending: 'status-tag--running', approved: 'status-tag--completed', rejected: 'status-tag--terminated', terminated: 'status-tag--terminated' }
  return m[s] || ''
}

/** 批准状态中文 */
export function endorsementStatusLabel(s: string): string {
  const m: Record<string, string> = { pending: '待批准', approved: '批准通过', rejected: '批准驳回', terminated: '已终止' }
  return m[s] || s
}

/** 难度等级 CSS 类名 */
export function difficultyClass(d: string): string {
  return `diff--${d || '1'}`
}
