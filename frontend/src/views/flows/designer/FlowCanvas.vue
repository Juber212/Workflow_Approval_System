<template>
  <div class="flow-canvas">
    <!-- LogicFlow 画布容器 -->
    <div ref="canvasRef" class="canvas-container" tabindex="0" />
    <!-- 缩放比例 -->
    <div class="zoom-badge">{{ Math.round(zoomRatio) }}%</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, shallowRef } from 'vue'
import LogicFlow from '@logicflow/core'
import { Control } from '@logicflow/extension'
import '@logicflow/core/dist/index.css'
import '@logicflow/extension/lib/style/index.css'
import { registerWorkNode } from './nodes/WorkNode'
import { registerStartNode } from './nodes/StartNode'
import { registerEndNode } from './nodes/EndNode'

/** 注册 Control 扩展（右上角缩放控件） */
LogicFlow.use(Control)

/** 事件定义 */
const emit = defineEmits<{
  'node-select': [data: any | null]
}>()

/** 画布配置 */
const DEFAULT_CONFIG = {
  grid: { size: 20, visible: true, type: 'dot' as const },
  keyboard: { enabled: true },  // Delete/Ctrl+Z/Y 快捷键
  background: { backgroundColor: '#fafafa' },
  history: true,
  adjustEdge: true,
  edgeType: 'polyline' as const, // 折线连线
  /** 守卫：拦截非法操作 */
  guards: {
    beforeDelete: (data: any) => {
      // 禁止删除开始/结束节点
      if (data?.properties?.is_start || data?.properties?.is_end) return false
      return true
    },
  },
}

/** 当前选中的元素 ID（用于删除按钮） */
let selectedElementId: string | null = null
let selectedElementType: 'node' | 'edge' | null = null

const canvasRef = ref<HTMLElement>()
const lf = shallowRef<LogicFlow>()
const zoomRatio = ref(100)

/** 工作节点序号 */
let workNodeCounter = 1

onMounted(() => {
  if (!canvasRef.value) return

  const logicFlow = new LogicFlow({ container: canvasRef.value, ...DEFAULT_CONFIG })
  logicFlow.history.maxSize = 50

  // 注册自定义节点
  registerStartNode(logicFlow)
  registerWorkNode(logicFlow)
  registerEndNode(logicFlow)

  // 基础渲染
  logicFlow.render({ nodes: [], edges: [] })

  // DnD 支持：dragover/drop
  if (canvasRef.value) {
    canvasRef.value.addEventListener('dragover', (e: DragEvent) => e.preventDefault())
    canvasRef.value.addEventListener('drop', (e: DragEvent) => e.preventDefault())
  }

  // 双击：阻止 LogicFlow 默认文字编辑
  logicFlow.on('node:dbclick', ({ data }: any) => {
    emit('node-select', data)
  })

  // 点击节点 → 选中
  logicFlow.on('node:click', ({ data }: any) => {
    selectedElementId = data.id || null
    selectedElementType = 'node'
    canvasRef.value?.focus() // 让画布获得焦点以接收 Delete 键
    emit('node-select', data)
  })

  // 点击连线 → 可删除
  logicFlow.on('edge:click', ({ data }: any) => {
    selectedElementId = data.id || null
    selectedElementType = 'edge'
    canvasRef.value?.focus()
    emit('node-select', null)
  })

  // 点击空白 → 取消选中
  logicFlow.on('blank:click', () => {
    selectedElementId = null
    selectedElementType = null
    canvasRef.value?.focus()
    emit('node-select', null)
  })

  lf.value = logicFlow

  // 缩放比例更新
  logicFlow.on('graph:transform', () => {
    const t = logicFlow.getTransform()
    zoomRatio.value = t.SCALE_X * 100
  })

  // 初始聚焦
  canvasRef.value.focus()
})

/** 全局键盘监听 —— Delete/Backspace 删除选中元素 */
function onGlobalKeydown(e: KeyboardEvent) {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    // 输入框/文本框/下拉框内不触发删除，避免干扰文字编辑
    const tag = (e.target as HTMLElement)?.tagName
    const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
    const isEditable = (e.target as HTMLElement)?.isContentEditable
    if (isInput || isEditable) return

    if (canvasRef.value && canvasRef.value.offsetParent !== null) {
      e.preventDefault()
      deleteSelected()
    }
  }
}

onMounted(() => { document.addEventListener('keydown', onGlobalKeydown) })

onUnmounted(() => {
  document.removeEventListener('keydown', onGlobalKeydown)
  lf.value?.destroy()
})

/** 添加工作节点（可选预设配置） */
function addWorkNode(x?: number, y?: number, presetProperties?: Record<string, any>) {
  const instance = lf.value
  if (!instance) return

  if (x === undefined || y === undefined) {
    const { SCALE_X, TRANSLATE_X, TRANSLATE_Y } = instance.getTransform()
    const container = canvasRef.value!
    const cx = (container.clientWidth / 2 - TRANSLATE_X) / SCALE_X
    const cy = (container.clientHeight / 2 - TRANSLATE_Y) / SCALE_X
    x = cx + (Math.random() - 0.5) * 100
    y = cy + (Math.random() - 0.5) * 100
  }

  // 默认属性
  const defaults = {
    name: `节点 ${workNodeCounter++}`,
    is_start: false, is_end: false,
    require_file: true,
    approval_strategy: 'all_approve',
    time_limit_days: 3,
  }

  // 合并预设属性（预设优先），preset name 不自动加计数器
  const merged = { ...defaults, ...(presetProperties || {}) }

  instance.addNode({
    id: `work-${Date.now()}`,
    type: 'work-node', x, y,
    properties: merged,
  })
}

/** 删除当前选中元素 */
function deleteSelected() {
  const instance = lf.value
  if (!instance || !selectedElementId || !selectedElementType) return

  if (selectedElementType === 'edge') {
    instance.deleteEdge(selectedElementId)
  } else if (selectedElementType === 'node') {
    instance.deleteNode(selectedElementId)
  }
  selectedElementId = null
  selectedElementType = null
}

function getLf() { return lf.value }

defineExpose({ getLf, lf, addWorkNode, deleteSelected })
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
  outline: none;
}

/* 缩放比例徽章 —— 左下角 */
.zoom-badge {
  position: absolute;
  bottom: 56px;
  left: 16px;
  padding: 4px 10px;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  background: #fff;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
  user-select: none;
  z-index: 5;
}
</style>
