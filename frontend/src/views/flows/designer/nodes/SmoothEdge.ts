/** 自定义平滑曲线边 —— 基于 PolylineEdge 实现平滑渲染 + 端点拖拽重连 */
import { h, PolylineEdge, PolylineEdgeModel } from '@logicflow/core'
import type LogicFlow from '@logicflow/core'

// ========== 路径计算 ==========

/** 将折线点转换为平滑贝塞尔曲线路径 d 属性 */
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

    const cp1x = p1.x + (p2.x - p0.x) / 6
    const cp1y = p1.y + (p2.y - p0.y) / 6
    const cp2x = p2.x - (p3.x - p1.x) / 6
    const cp2y = p2.y - (p3.y - p1.y) / 6

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
    const points = (model as any).points as Array<{ x: number; y: number }> || []
    const style = model.getEdgeStyle()
    const { arrowConfig } = model as any

    // 用 <path> + 平滑 d 替换 <polyline>
    const attr: Record<string, any> = {
      d: calcSmoothPath(points),
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
