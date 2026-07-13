/** LogicFlow 结束节点 —— 蓝色样式，不可删除，不可作为连线源 */
import { RectNode, RectNodeModel } from '@logicflow/core'
import type LogicFlow from '@logicflow/core'

/** 结束节点模型 */
class EndNodeModel extends RectNodeModel {
  setAttributes() {
    this.width = 140
    this.height = 50
    this.radius = 8
    // 设置文字
    this.text = {
      value: '结束（终审）',
      x: this.width / 2,
      y: this.height / 2,
    }
    // 不可作为连线源（只能作为目标）
    this.sourceRules = [
      {
        message: '结束节点不可作为连线源',
        validate: () => false,
      },
    ]
    this.targetRules = []
  }

  /** 蓝色边框 + 浅蓝背景 */
  getNodeStyle() {
    const style = super.getNodeStyle()
    return {
      ...style,
      stroke: '#409eff',  // 蓝色边框
      strokeWidth: 2,
      fill: '#ecf5ff',    // 浅蓝背景
    }
  }

  /** 蓝色文字 */
  getTextStyle() {
    return {
      color: '#409eff',
      fontSize: 14,
      fontWeight: 'bold',
    }
  }
}

/** 结束节点视图 —— 使用标准 RectNode 渲染 */
class EndNodeView extends RectNode {}

/** 注册结束节点类型 */
function registerEndNode(lf: LogicFlow) {
  lf.register('end-node', {
    model: EndNodeModel,
    view: EndNodeView,
  })
}

export { EndNodeModel, EndNodeView, registerEndNode }
