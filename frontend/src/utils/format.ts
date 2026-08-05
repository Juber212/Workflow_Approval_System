/** 格式化工具函数 —— 日期、文件大小等 */

/** 格式化 ISO 时间戳为 yyyy-MM-dd HH:mm */
export function formatTime(v: string | null | undefined): string {
  if (!v) return '-'
  return v.replace('T', ' ').substring(0, 16)
}

/** 格式化文件大小为可读字符串 */
export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}

/** 截止时间逾期/临期 + 完成/终止状态 —— el-table 行 CSS 类名（用于 :row-class-name） */
export function deadlineRowClass({ row }: { row: any }): string {
  if (row?.status === 'completed') return 'r--green'
  if (row?.status === 'terminated') return 'r--gray'
  if (row?.is_overdue) return 'r--red'
  if (row?.days_remaining != null && row.days_remaining <= 1) return 'r--yel'
  return ''
}
