/** LogicFlow 开始节点 —— 绿色样式，不可删除，不可作为连线目标 */
import { RectNode, RectNodeModel, type BaseNodeModel } from '@logicflow/core'
import type LogicFlow from '@logicflow/core'

/** 开始节点模型 */
class StartNodeModel extends RectNodeModel {
  setAttributes() {
    this.width = 130
    this.height = 50
    this.radius = 8
    // 设置文字
    this.text = {
      value: '开始',
      x: this.width / 2,
      y: this.height / 2,
    }
    // 不可作为连线目标（只能作为源）
    this.sourceRules = []
    this.targetRules = [
      {
        message: '开始节点不可作为连线目标',
        validate: () => false,
      },
    ]
  }

  /** 绿色边框 + 浅绿背景 */
  getNodeStyle() {
    const style = super.getNodeStyle()
    return {
      ...style,
      stroke: '#67c23a',  // 绿色边框
      strokeWidth: 2,
      fill: '#f0f9eb',    // 浅绿背景
    }
  }

  /** 绿色文字 */
  getTextStyle() {
    return {
      color: '#67c23a',
      fontSize: 14,
      fontWeight: 'bold',
    }
  }
}

/** 开始节点视图 —— 使用标准 RectNode 渲染 */
class StartNodeView extends RectNode {}

/** 注册开始节点类型 */
function registerStartNode(lf: LogicFlow) {
  lf.register('start-node', {
    model: StartNodeModel,
    view: StartNodeView,
  })
}

export { StartNodeModel, StartNodeView, registerStartNode }
