/** 自定义平滑曲线边 —— 基于 PolylineEdge 实现平滑渲染 + 端点拖拽重连 */
import { h, PolylineEdge, PolylineEdgeModel } from '@logicflow/core'
import type LogicFlow from '@logicflow/core'

// ========== 路径计算 ==========

/** 将 LogicFlow points 字符串解析为坐标数组（格式："x1,y1 x2,y2 x3,y3"） */
function parsePoints(pointsStr: string): Array<{ x: number; y: number }> {
  return pointsStr.split(' ').filter(Boolean).map(p => {
    const [x, y] = p.split(',')
    return { x: Number(x), y: Number(y) }
  })
}

/** 合并共线冗余点 —— 同方向连续线段合并，只保留方向变化处的拐点 */
function simplifyPoints(points: Array<{ x: number; y: number }>): Array<{ x: number; y: number }> {
  if (points.length <= 2) return points

  const result = [points[0]] // 起点保留

  for (let i = 1; i < points.length - 1; i++) {
    const prev = result[result.length - 1]
    const curr = points[i]
    const next = points[i + 1]

    const dx1 = curr.x - prev.x
    const dy1 = curr.y - prev.y
    const dx2 = next.x - curr.x
    const dy2 = next.y - curr.y

    // 两段线段方向相同 → 中间点是冗余的（如连续向右、连续向下）
    const sameDirection =
      (dx1 > 0 && dx2 > 0) || (dx1 < 0 && dx2 < 0) || // 水平同向
      (dy1 > 0 && dy2 > 0) || (dy1 < 0 && dy2 < 0)    // 垂直同向

    if (!sameDirection) {
      result.push(curr) // 方向变化 → 保留拐点
    }
    // 方向相同 → 跳过，合并为一条直线
  }

  result.push(points[points.length - 1]) // 终点保留
  return result
}

/** 将折线点数组转换为平滑贝塞尔曲线路径 d 属性 */
function calcSmoothPath(points: Array<{ x: number; y: number }>): string {
  if (points.length < 2) return ''
  if (points.length === 2) {
    return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`
  }

  // 三及以上点：Catmull-Rom → Cubic Bezier
  let d = `M ${points[0].x} ${points[0].y}`

  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)]
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = points[Math.min(points.length - 1, i + 2)]

    const cp1x = p1.x + (p2.x - p0.x) / 10  // 张力 1/10，曲线紧贴折线
    const cp1y = p1.y + (p2.y - p0.y) / 10
    const cp2x = p2.x - (p3.x - p1.x) / 10
    const cp2y = p2.y - (p3.y - p1.y) / 10

    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`
  }

  return d
}

// ========== Model ==========

/** 平滑曲线边模型 —— 继承 PolylineEdgeModel 保留 adjustEdgeStartAndEnd 能力 */
class SmoothEdgeModel extends PolylineEdgeModel {}

// ========== View ==========

/** 平滑曲线边视图 —— 用 SVG <path> + 贝塞尔 d 替换折线 */
class SmoothEdgeView extends PolylineEdge {
  getEdge() {
    const { model } = this.props
    // LogicFlow 的 model.points 是字符串格式（"x1,y1 x2,y2 ..."），需要先解析
    const rawPoints = (model as any).points
    const points: Array<{ x: number; y: number }> =
      typeof rawPoints === 'string' ? parsePoints(rawPoints) : (rawPoints || [])
    const style = model.getEdgeStyle()
    const { arrowConfig } = model as any

    // 先合并冗余共线点，再计算平滑路径（减少不必要的中间弯曲）
    const simplified = simplifyPoints(points)
    const attr: Record<string, any> = {
      d: calcSmoothPath(simplified),
      ...style,
      ...(arrowConfig || {}),
      fill: 'none',
      strokeLinecap: 'round',
    }

    return h('path', attr)
  }
}

// ========== 注册 ==========

/** 注册平滑曲线边到 LogicFlow */
function registerSmoothEdge(lf: LogicFlow) {
  lf.register('smooth-edge', () => ({
    model: SmoothEdgeModel,
    view: SmoothEdgeView,
  }))
}

export { registerSmoothEdge }
