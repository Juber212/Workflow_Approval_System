<template>
  <div class="flow-canvas">
    <!-- LogicFlow 画布容器 -->
    <div ref="canvasRef" class="canvas-container" />
    <!-- 缩放工具栏 -->
    <div class="zoom-toolbar">
      <el-button-group>
        <el-button size="small" :icon="ZoomIn" @click="zoomIn" title="放大" />
        <el-button size="small" :icon="ZoomOut" @click="zoomOut" title="缩小" />
        <el-button size="small" @click="fitView" title="适应画布">适应</el-button>
      </el-button-group>
      <span class="zoom-ratio">{{ Math.round(zoomRatio) }}%</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, shallowRef } from 'vue'
import { ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import LogicFlow from '@logicflow/core'
import { Control } from '@logicflow/extension'
import '@logicflow/core/dist/index.css'
import '@logicflow/extension/lib/style/index.css'
import { registerWorkNode } from './nodes/WorkNode'
import { registerStartNode } from './nodes/StartNode'
import { registerEndNode } from './nodes/EndNode'

/** 注册 Control 扩展（缩放/平移控件） */
LogicFlow.use(Control)

/** 事件定义 */
const emit = defineEmits<{
  'node-select': [data: any | null]
}>()

/** 画布配置 */
const DEFAULT_CONFIG = {
  grid: {
    size: 20,
    visible: true,
    type: 'dot' as const,
  },
  keyboard: {
    enabled: true,  // 快捷键（Delete/Ctrl+Z/Y 等）
  },
  background: {
    backgroundColor: '#fafafa',
  },
  history: true,    // 启用撤销/重做
  adjustEdge: true,
  edgeType: 'polyline' as const,
  /** 守卫：拦截非法操作 */
  guards: {
    /** 防止删除系统节点 */
    beforeDelete: (data: any) => {
      if (data?.properties?.is_start || data?.properties?.is_end) {
        return false
      }
      return true
    },
  },
}

const canvasRef = ref<HTMLElement>()
const lf = shallowRef<LogicFlow>()
const zoomRatio = ref(100)

/** 工作节点序号（用于默认名称） */
let workNodeCounter = 1

onMounted(() => {
  if (!canvasRef.value) return

  const logicFlow = new LogicFlow({
    container: canvasRef.value,
    ...DEFAULT_CONFIG,
  })

  // 设置撤销/重做上限 50 步
  logicFlow.history.maxSize = 50

  // 注册三种自定义节点
  registerStartNode(logicFlow)
  registerWorkNode(logicFlow)
  registerEndNode(logicFlow)

  // 基础渲染（空白画布）
  logicFlow.render({ nodes: [], edges: [] })

  // 监听缩放变化
  logicFlow.on('graph:transform', () => {
    const transform = logicFlow.getTransform()
    zoomRatio.value = transform.SCALE_X * 100
  })

  // 监听节点点击 —— 通知属性面板
  logicFlow.on('node:click', ({ data }: any) => {
    emit('node-select', data)
  })

  // 监听画布空白区域点击 —— 取消选中
  logicFlow.on('blank:click', () => {
    emit('node-select', null)
  })

  lf.value = logicFlow
})

onUnmounted(() => {
  lf.value?.destroy()
})

/** 放大 */
function zoomIn() {
  lf.value?.zoom(true)
}

/** 缩小 */
function zoomOut() {
  lf.value?.zoom(false)
}

/** 适应画布 */
function fitView() {
  lf.value?.fitView()
}

/** 添加工作节点（在画布中心或指定位置） */
function addWorkNode(x?: number, y?: number) {
  const instance = lf.value
  if (!instance) return

  // 默认添加到画布可见区域中心附近
  if (x === undefined || y === undefined) {
    const { SCALE_X, TRANSLATE_X, TRANSLATE_Y } = instance.getTransform()
    const container = canvasRef.value!
    const cx = (container.clientWidth / 2 - TRANSLATE_X) / SCALE_X
    const cy = (container.clientHeight / 2 - TRANSLATE_Y) / SCALE_X
    // 加一点随机偏移避免完全重叠
    x = cx + (Math.random() - 0.5) * 100
    y = cy + (Math.random() - 0.5) * 100
  }

  const nodeId = `work-${Date.now()}`
  instance.addNode({
    id: nodeId,
    type: 'work-node',
    x,
    y,
    text: { value: `节点 ${workNodeCounter++}`, x: 80, y: 32 },
    properties: {
      name: `节点 ${workNodeCounter - 1}`,
      is_start: false,
      is_end: false,
      require_file: true,
      approval_strategy: 'all_approve',
      is_optional: false,
      time_limit_days: 3,
    },
  })
}

/** 获取 LogicFlow 实例 */
function getLf() { return lf.value }

defineExpose({ getLf, lf, addWorkNode })
</script>

<style lang="scss" scoped>
.flow-canvas {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.canvas-container {
  width: 100%;
  height: 100%;
}

/* 缩放工具栏 —— 右下角浮动 */
.zoom-toolbar {
  position: absolute;
  bottom: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  padding: 4px 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  z-index: 10;

  .zoom-ratio {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    min-width: 36px;
    text-align: center;
  }
}
</style>
