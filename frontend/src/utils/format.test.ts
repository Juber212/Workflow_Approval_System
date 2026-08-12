/** format 工具单测 —— 日期格式化 / 文件大小 / 截止行类名 */
import { describe, it, expect } from 'vitest'
import { formatTime, formatFileSize, deadlineRowClass } from './format'

describe('formatTime', () => {
  it('ISO 转 yyyy-MM-dd HH:mm', () => {
    expect(formatTime('2026-07-06T09:30:00')).toBe('2026-07-06 09:30')
  })

  it('空值返回 -', () => {
    expect(formatTime(null)).toBe('-')
    expect(formatTime(undefined)).toBe('-')
  })
})

describe('formatFileSize', () => {
  it('0 / null → 0 B', () => {
    expect(formatFileSize(0)).toBe('0 B')
    expect(formatFileSize(null)).toBe('0 B')
  })

  it('B', () => {
    expect(formatFileSize(512)).toBe('512 B')
  })

  it('KB', () => {
    expect(formatFileSize(2048)).toBe('2.0 KB')
  })

  it('MB', () => {
    expect(formatFileSize(5 * 1024 * 1024)).toBe('5.0 MB')
  })
})

describe('deadlineRowClass', () => {
  it('completed / terminated 状态类', () => {
    expect(deadlineRowClass({ row: { status: 'completed' } })).toBe('r--green')
    expect(deadlineRowClass({ row: { status: 'terminated' } })).toBe('r--gray')
  })

  it('逾期 / 临期', () => {
    expect(deadlineRowClass({ row: { is_overdue: true } })).toBe('r--red')
    expect(deadlineRowClass({ row: { days_remaining: 1 } })).toBe('r--yel')
  })

  it('正常返回空', () => {
    expect(deadlineRowClass({ row: { status: 'running' } })).toBe('')
  })
})
