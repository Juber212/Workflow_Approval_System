/** LogicFlow 自定义工作节点 —— 使用 HtmlNode 实现多行信息展示和视觉状态区分 */
import { HtmlNode, HtmlNodeModel } from '@logicflow/core'
import type LogicFlow from '@logicflow/core'
import './WorkNode.css'

/** 判定节点配置是否完整（必填字段全部填写） */
function isConfigured(properties: any): boolean {
  return !!(
    properties?.name &&
    properties?.assignee_id &&
    Array.isArray(properties?.checkers) && properties.checkers.length > 0 &&
    Array.isArray(properties?.approvers) && properties.approvers.length > 0 &&
    properties?.time_limit_days && properties.time_limit_days >= 1
  )
}

/** HTML 转义（防止 XSS） */
function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

/** 截断人名列表：最多显示 n 个，超出显示 "+N" */
function formatNameList(names: string[], max = 2): string {
  if (!names || names.length === 0) return '<span class="unset">未设置</span>'
  if (names.length <= max) return names.map(escapeHtml).join('、')
  const shown = names.slice(0, max).map(escapeHtml).join('、')
  return `${shown} <span class="more-tag">+${names.length - max}</span>`
}

/** 构建节点内部 HTML 内容 */
function buildNodeHtml(properties: any): string {
  const configured = isConfigured(properties)
  const name = properties?.name || '未命名节点'
  const assigneeName = properties?.assignee_name || '未设置'
  const timeLimit = properties?.time_limit_days ? `${properties.time_limit_days} 工作日` : '未设置'
  const checkerNames = properties?.checkers_names || []
  const approverNames = properties?.approvers_names || []

  // 未配置的红色圆点
  const dotHtml = configured ? '' : '<span class="unconfig-dot"></span>'

  return `
    <div class="work-node-inner ${configured ? 'configured' : 'unconfigured'}">
      <div class="node-title">
        ${dotHtml}
        <span class="node-name" title="${escapeHtml(name)}">${escapeHtml(name)}</span>
      </div>
      <div class="node-row">
        <span class="row-label">负责人</span>
        <span class="row-value">${escapeHtml(assigneeName)}</span>
      </div>
      <div class="node-row">
        <span class="row-label">时限</span>
        <span class="row-value">${timeLimit}</span>
      </div>
      <div class="node-row">
        <span class="row-label">审批</span>
        <span class="row-value">${formatNameList(approverNames)}</span>
      </div>
      ${!configured ? '<div class="unconfig-badge">⚠ 未配置</div>' : ''}
    </div>
  `
}

/** 工作节点模型 —— 负责尺寸和样式 */
class WorkNodeModel extends HtmlNodeModel {
  setAttributes() {
    this.width = 190
    this.height = 112
    this.radius = 8
    this.textEdit = false // 禁用双击文字编辑
  }

  /** 动态边框样式：已配置 = 实线蓝边框，未配置 = 橙色虚线 */
  getNodeStyle() {
    const style = super.getNodeStyle()
    const configured = isConfigured(this.properties)

    if (configured) {
      return {
        ...style,
        stroke: '#1a6fb5',
        strokeWidth: 2,
        fill: '#ecf5ff',
      }
    }
    // 未配置 → 橙色虚线边框 + 红色圆点背景
    return {
      ...style,
      stroke: '#e6a23c',
      strokeWidth: 2,
      strokeDasharray: '6 3',
      fill: '#fef0e8',
    }
  }
}

/** 工作节点视图 —— 负责渲染 HTML 内容 */
class WorkNodeView extends HtmlNode {
  /** 缓存上次 properties 用于 change 检测 */
  private cachedProps: string = ''

  /** 注入自定义 HTML 到 foreignObject */
  setHtml(rootEl: SVGForeignObjectElement) {
    const { properties } = this.props.model
    rootEl.innerHTML = buildNodeHtml(properties)
    rootEl.setAttribute('class', 'work-node-wrapper')
  }

  /** 只在 properties 发生变化时重新渲染 */
  shouldUpdate(): boolean {
    const { properties } = this.props.model
    const current = JSON.stringify(properties)
    if (current !== this.cachedProps) {
      this.cachedProps = current
      return true
    }
    return false
  }
}

/** 注册工作节点到 LogicFlow 实例 */
function registerWorkNode(lf: LogicFlow) {
  lf.register('work-node', () => ({
    model: WorkNodeModel,
    view: WorkNodeView,
  }))
}

export { WorkNodeModel, WorkNodeView, registerWorkNode, isConfigured }
