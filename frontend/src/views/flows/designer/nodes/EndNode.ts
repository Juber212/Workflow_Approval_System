/** LogicFlow 结束节点 —— 深蓝色，不可删除，不可作为连线源 */
import { HtmlNode, HtmlNodeModel } from '@logicflow/core'
import type LogicFlow from '@logicflow/core'

/** 结束节点模型 */
class EndNodeModel extends HtmlNodeModel {
  setAttributes() {
    this.width = 190
    this.height = 112
    this.radius = 8
    this.textEdit = false // 禁用双击文字编辑
    this.sourceRules = [
      { message: '结束节点不可作为连线源', validate: () => false },
    ]
    this.targetRules = []
  }

  getNodeStyle() {
    const style = super.getNodeStyle()
    return { ...style, stroke: '#3b6fb5', strokeWidth: 2, fill: '#eaf1fa' }
  }
}

/** 结束节点视图 */
class EndNodeView extends HtmlNode {
  setHtml(rootEl: SVGForeignObjectElement) {
    rootEl.innerHTML = `
      <div style="
        width:190px;height:112px;display:flex;flex-direction:column;
        align-items:center;justify-content:center;box-sizing:border-box;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      ">
        <div style="font-size:15px;font-weight:700;color:#3b6fb5;line-height:1.4">结束（终审）</div>
        <div style="font-size:11px;color:#909399;margin-top:2px">发起人终审</div>
      </div>
    `
  }
}

function registerEndNode(lf: LogicFlow) {
  lf.register('end-node', () => ({ model: EndNodeModel, view: EndNodeView }))
}

export { EndNodeModel, EndNodeView, registerEndNode }
