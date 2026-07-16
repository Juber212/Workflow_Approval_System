/** 自定义平滑曲线边 —— 基于 PolylineEdge 实现平滑渲染 + 端点拖拽重连 */
import { PolylineEdge, PolylineEdgeModel } from '@logicflow/core'
import type LogicFlow from '@logicflow/core'

/** 将折线点转换为平滑贝塞尔曲线路径 */
function calcSmoothPath(points: Array<{ x: number; y: number }>): string {
  if (points.length < 2) return ''
  if (points.length === 2) {
    // 两个点：直接画直线
    return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`
  }

  // 三个及以上点：用 Catmull-Rom → Bezier 平滑
  let d = `M ${points[0].x} ${points[0].y}`

  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)]
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = points[Math.min(points.length - 1, i + 2)]

    // 控制点：取前后点连线的 1/6 处
    const cp1x = p1.x + (p2.x - p0.x) / 6
    const cp1y = p1.y + (p2.y - p0.y) / 6
    const cp2x = p2.x - (p3.x - p1.x) / 6
    const cp2y = p2.y - (p3.y - p1.y) / 6

    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`
  }

  return d
}

/** 平滑曲线边模型 —— 继承折线模型（保留端点拖拽能力），重写路径 */
class SmoothEdgeModel extends PolylineEdgeModel {
  /** 重写：使用平滑贝塞尔路径替换折线路径 */
  initEdgeData(data: any) {
    super.initEdgeData(data)
    // 自定义类型标识
    data.customEdgeType = 'smooth-polyline'
  }

  /** 获取最终路径点，用于调整端点（adjustEdgeStartAndEnd） */
  getEdgeStyle() {
    const style = super.getEdgeStyle()
    return { ...style }
  }
}

/** 平滑曲线边视图 —— 重写路径 d 属性 */
class SmoothEdgeView extends PolylineEdge {
  /** 核心：把折线点转成平滑路径 */
  getEdge() {
    const { model } = this.props
    const points = model.points || []

    if (points.length < 2) return super.getEdge()

    const smoothD = calcSmoothPath(points)
    const attrs = super.getEdge() as any
    attrs.d = smoothD
    return attrs
  }
}

/** 注册平滑曲线边到 LogicFlow */
function registerSmoothEdge(lf: LogicFlow) {
  lf.register('smooth-edge', () => ({
    model: SmoothEdgeModel,
    view: SmoothEdgeView,
  }))
}

export { registerSmoothEdge }
