/** LogicFlow 开始节点 —— 青绿色，不可删除，不可作为连线目标 */
import { HtmlNode, HtmlNodeModel } from '@logicflow/core'
import type LogicFlow from '@logicflow/core'

/** 开始节点模型 */
class StartNodeModel extends HtmlNodeModel {
  setAttributes() {
    this.width = 190
    this.height = 112
    this.radius = 8
    this.textEdit = false // 禁用双击文字编辑
    this.sourceRules = []
    this.targetRules = [
      { message: '开始节点不可作为连线目标', validate: () => false },
    ]
  }

  getNodeStyle() {
    const style = super.getNodeStyle()
    return { ...style, stroke: '#409e7a', strokeWidth: 2, fill: '#eef8f3' }
  }
}

/** 开始节点视图 */
class StartNodeView extends HtmlNode {
  setHtml(rootEl: SVGForeignObjectElement) {
    rootEl.innerHTML = `
      <div style="
        width:190px;height:112px;display:flex;flex-direction:column;
        align-items:center;justify-content:center;box-sizing:border-box;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      ">
        <div style="font-size:15px;font-weight:700;color:#409e7a;line-height:1.4">开始</div>
        <div style="font-size:11px;color:#909399;margin-top:2px">系统默认</div>
      </div>
    `
  }
}

function registerStartNode(lf: LogicFlow) {
  lf.register('start-node', () => ({ model: StartNodeModel, view: StartNodeView }))
}

export { StartNodeModel, StartNodeView, registerStartNode }
