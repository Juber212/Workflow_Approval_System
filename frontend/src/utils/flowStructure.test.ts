/** flowStructure 纯函数单测 —— 拓扑排序 / 人员规范化 / 自然日期限 */
import { describe, it, expect } from 'vitest'
import {
  topoSortNodes,
  normalizePersons,
  calcChainDeadlines,
  countDaysExcludingStart,
  type FlowNodeLike,
} from './flowStructure'

describe('topoSortNodes', () => {
  const nodes = (ids: string[]): FlowNodeLike[] => ids.map(id => ({ id, properties: {} }))

  it('线性链：按连线顺序返回', () => {
    const result = topoSortNodes(nodes(['a', 'b', 'c']), [
      { sourceNodeId: 'a', targetNodeId: 'b' },
      { sourceNodeId: 'b', targetNodeId: 'c' },
    ])
    expect(result.map(n => n.id)).toEqual(['a', 'b', 'c'])
  })

  it('分叉结构：父节点先于子节点，兄弟按输入顺序', () => {
    const result = topoSortNodes(nodes(['a', 'b', 'c']), [
      { sourceNodeId: 'a', targetNodeId: 'b' },
      { sourceNodeId: 'a', targetNodeId: 'c' },
    ])
    const ids = result.map(n => n.id)
    expect(ids[0]).toBe('a')
    expect(ids.indexOf('b')).toBeLessThan(ids.indexOf('c'))
  })

  it('环 / 孤立节点兜底：全部返回不丢', () => {
    const result = topoSortNodes(nodes(['a', 'b', 'c', 'd']), [
      { sourceNodeId: 'a', targetNodeId: 'b' },
      { sourceNodeId: 'b', targetNodeId: 'a' },  // 环
      // c、d 孤立
    ])
    expect(result.map(n => n.id).sort()).toEqual(['a', 'b', 'c', 'd'])
  })

  it('空图返回空数组', () => {
    expect(topoSortNodes([], [])).toEqual([])
  })
})

describe('normalizePersons', () => {
  it('数字数组 [id] → [{user_id}]', () => {
    expect(normalizePersons([1, 2, 3])).toEqual([{ user_id: 1 }, { user_id: 2 }, { user_id: 3 }])
  })

  it('dict 数组 [{user_id}] → 原样', () => {
    expect(normalizePersons([{ user_id: 5 }, { user_id: 6 }])).toEqual([{ user_id: 5 }, { user_id: 6 }])
  })

  it('dict 带 name → 只取 user_id', () => {
    expect(normalizePersons([{ user_id: 7, name: '张三' }])).toEqual([{ user_id: 7 }])
  })

  it('旧格式 {id} → 取 id', () => {
    expect(normalizePersons([{ id: 9 }])).toEqual([{ user_id: 9 }])
  })

  it('字符串 id → 转数字', () => {
    expect(normalizePersons(['12'])).toEqual([{ user_id: 12 }])
  })
})

describe('calcChainDeadlines', () => {
  // 链首 2026-07-06（周一），本地时区
  const start = new Date(2026, 6, 6)

  it('自然日顺排：N 天覆盖 [start, start+N-1]，下一节点衔接截止次日', () => {
    const r = calcChainDeadlines(
      [
        { id: 'a', time_limit_days: 2 },
        { id: 'b', time_limit_days: 1 },
      ],
      start,
    )
    expect(r.a).toEqual({ begin: '2026-07-06', deadline: '2026-07-07' })
    expect(r.b).toEqual({ begin: '2026-07-08', deadline: '2026-07-08' })
  })

  it('time_limit 缺省按 1 天', () => {
    const r = calcChainDeadlines([{ id: 'a' }, { id: 'b', time_limit_days: 2 }], start)
    expect(r.a).toEqual({ begin: '2026-07-06', deadline: '2026-07-06' })
    expect(r.b).toEqual({ begin: '2026-07-07', deadline: '2026-07-08' })
  })

  it('跨月顺排', () => {
    const july30 = new Date(2026, 6, 30)
    const r = calcChainDeadlines([{ id: 'a', time_limit_days: 3 }], july30)
    expect(r.a).toEqual({ begin: '2026-07-30', deadline: '2026-08-01' })
  })
})

describe('countDaysExcludingStart', () => {
  it('正常天数差（含结束日）', () => {
    expect(countDaysExcludingStart('2026-07-06', '2026-07-09')).toBe(3)
  })

  it('同日 → clamp 为 1', () => {
    expect(countDaysExcludingStart('2026-07-06', '2026-07-06')).toBe(1)
  })

  it('反向（end < start）→ clamp 为 1', () => {
    expect(countDaysExcludingStart('2026-07-09', '2026-07-06')).toBe(1)
  })
})
