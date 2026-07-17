/** 标签/状态映射工具函数 —— 优先级、实例状态、角色等中文映射 */

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
  const m: Record<string, string> = { running: 'status-tag--running', completed: 'status-tag--completed', terminated: 'status-tag--terminated' }
  return m[s] || ''
}

/** 流程实例状态中文 */
export function instStatusLabel(s: string): string {
  const m: Record<string, string> = { running: '运行中', completed: '已完成', terminated: '已终止' }
  return m[s] || s
}
