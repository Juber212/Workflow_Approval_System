/** labels 标签/状态映射单测 */
import { describe, it, expect } from 'vitest'
import {
  priLabel,
  roleLabel,
  instStatusClass,
  instStatusLabel,
  taskStatusLabel,
  checkStatusLabel,
  approvalStatusLabel,
  endorsementStatusLabel,
} from './labels'

describe('priLabel', () => {
  it('优先级映射', () => {
    expect(priLabel('urgent')).toBe('紧急')
    expect(priLabel('high')).toBe('高')
    expect(priLabel('normal')).toBe('普通')
    expect(priLabel('low')).toBe('低')
    expect(priLabel('xxx')).toBe('xxx')  // 未知原样返回
  })
})

describe('roleLabel', () => {
  it('角色映射', () => {
    expect(roleLabel('manager')).toBe('所长')
    expect(roleLabel('user')).toBe('普通用户')
    expect(roleLabel('system_admin')).toBe('系统管理员')
  })
})

describe('instStatus', () => {
  it('类名（大小写不敏感）与文案', () => {
    expect(instStatusClass('RUNNING')).toBe('status-tag--running')
    expect(instStatusLabel('completed')).toBe('已完成')
    expect(instStatusLabel('unknown')).toBe('unknown')
  })
})

describe('任务/校验/审批/批准状态文案', () => {
  it('任务状态', () => {
    expect(taskStatusLabel('waiting_approval')).toBe('待审批')
    expect(taskStatusLabel('overdue')).toBe('已逾期')
  })

  it('校验状态', () => {
    expect(checkStatusLabel('passed')).toBe('已通过')
  })

  it('审批状态', () => {
    expect(approvalStatusLabel('approved')).toBe('已通过')
  })

  it('批准状态', () => {
    expect(endorsementStatusLabel('approved')).toBe('批准通过')
  })
})
