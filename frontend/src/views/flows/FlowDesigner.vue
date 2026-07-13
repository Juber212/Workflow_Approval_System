<template>
  <div class="flow-designer">
    <!-- 顶部工具栏 -->
    <div class="designer-header">
      <el-page-header @back="$router.push('/flows')" content="流程设计器" />
      <div class="header-actions">
        <span class="template-name" v-if="templateName">{{ templateName }}</span>
        <el-tooltip content="Ctrl+Z 撤销 · Ctrl+Y 重做（上限50步）" placement="bottom">
          <el-button text @click="undo" :disabled="!undoable">↩ 撤销</el-button>
        </el-tooltip>
        <el-tooltip content="Ctrl+Y 重做" placement="bottom">
          <el-button text @click="redo" :disabled="!redoable">↪ 重做</el-button>
        </el-tooltip>
        <el-divider direction="vertical" />
        <el-tooltip content="Ctrl+S 保存草稿到服务器" placement="bottom">
          <el-button type="primary" :disabled="saving" :loading="saving" @click="handleSave">保存</el-button>
        </el-tooltip>
        <el-button
          type="success"
          :disabled="saving || publishing"
          :loading="publishing"
          @click="handlePublish"
        >
          发布
        </el-button>
      </div>
    </div>

    <!-- 主体区域：视图切换 + 节点列表 -->
    <div class="designer-body" v-loading="loading">
      <template v-if="viewMode === 'canvas'">
        <NodePanel :lf="canvasRef?.getLf() ?? null" @add="handleAddNode" />
        <FlowCanvas ref="canvasRef" @node-select="handleNodeSelect" />
        <PropertyPanel :lf="canvasRef?.getLf() ?? null" :node-data="selectedNodeData" />
      </template>
      <template v-else>
        <NodeListView
          :nodes="getCanvasNodes()"
          @select-node="handleListNodeSelect"
        />
      </template>
    </div>

    <!-- 视图切换按钮 -->
    <div class="view-mode-toggle">
      <el-radio-group v-model="viewMode" size="small">
        <el-radio-button value="canvas">画布</el-radio-button>
        <el-radio-button value="list">列表</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 发布对话框 -->
    <PublishDialog
      ref="publishDialogRef"
      v-model="showPublishDialog"
      :lf="canvasRef?.getLf() ?? null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTemplateDetail, publishTemplate, type TemplateDetail } from '@/api/template'
import { saveDesign, type DesignerNode, type DesignerEdge } from '@/api/designer'
import FlowCanvas from './designer/FlowCanvas.vue'
import NodePanel from './designer/NodePanel.vue'
import PropertyPanel from './designer/PropertyPanel.vue'
import NodeListView from './designer/NodeListView.vue'
import PublishDialog from './designer/PublishDialog.vue'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const publishing = ref(false)
const showPublishDialog = ref(false)
const publishDialogRef = ref<InstanceType<typeof PublishDialog>>()
const templateName = ref('')
const canvasRef = ref<InstanceType<typeof FlowCanvas>>()
const undoable = ref(false)
const redoable = ref(false)

/** 视图模式：canvas（画布）/ list（列表） */
const viewMode = ref<'canvas' | 'list'>('canvas')

/** 当前选中节点（LogicFlow 格式） */
const selectedNodeData = ref<any>(null)

/** 节点选中事件回调 —— 从画布传过来 */
function handleNodeSelect(nodeData: any | null) {
  selectedNodeData.value = nodeData
}

/** 从画布提取节点列表数据（供 NodeListView 使用） */
function getCanvasNodes(): any[] {
  const lf = canvasRef.value?.getLf()
  if (!lf) return []
  const graphData = lf.getGraphData()
  return (graphData.nodes || []).map((n: any) => ({
    id: n.id,
    name: n.properties?.name || n.text?.value || '',
    is_start: n.properties?.is_start ?? false,
    is_end: n.properties?.is_end ?? false,
    assignee_id: n.properties?.assignee_id ?? null,
    assignee_name: n.properties?.assignee_name || '',
    checkers: n.properties?.checkers ?? null,
    checkers_names: n.properties?.checkers_names || [],
    approvers: n.properties?.approvers ?? null,
    approvers_names: n.properties?.approvers_names || [],
    time_limit_days: n.properties?.time_limit_days ?? null,
  }))
}

/** 列表视图中点击行 → 切换到画布并选中/居中节点 */
function handleListNodeSelect(nodeId: string | number) {
  viewMode.value = 'canvas'
  const lf = canvasRef.value?.getLf()
  if (!lf) return

  // 选中节点
  lf.selectNodeById(String(nodeId))
  // 居中到节点
  const nodeData = lf.getNodeModelById(String(nodeId))
  if (nodeData) {
    lf.focusOn({ coordinate: { x: nodeData.x, y: nodeData.y } })
  }
}

/** Ctrl+S 快捷键保存 */
function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault()
    handleSave()
  }
}

onMounted(async () => {
  const id = Number(route.params.id)
  if (!id) return

  loading.value = true
  try {
    const detail: TemplateDetail = await getTemplateDetail(id)
    templateName.value = detail.name

    // 加载节点和连线到画布
    const lf = canvasRef.value?.getLf()
    if (lf && (detail.nodes.length > 0 || detail.edges.length > 0)) {
      // 根据节点属性映射到对应类型
      function mapNodeType(n: typeof detail.nodes[number]): string {
        if (n.is_start) return 'start-node'
        if (n.is_end) return 'end-node'
        return 'work-node'
      }

      lf.renderRawData({
        nodes: detail.nodes.map(n => ({
          id: String(n.id),
          type: mapNodeType(n),
          x: n.position_x,
          y: n.position_y,
          properties: {
            name: n.name,
            is_start: n.is_start,
            is_end: n.is_end,
            assignee_id: n.assignee_id,
            time_limit_days: n.time_limit_days,
            require_file: n.require_file,
            approvers: n.approvers,
            checkers: n.checkers,
            approval_strategy: n.approval_strategy,
            is_optional: n.is_optional,
          },
        })),
        edges: detail.edges.map(e => ({
          id: String(e.id),
          type: 'polyline',
          sourceNodeId: String(e.source_node_id),
          targetNodeId: String(e.target_node_id),
        })),
      })

      // 更新撤销/重做状态
      updateUndoRedoState(lf)
    }
  } catch {
    ElMessage.error('加载模板数据失败')
  } finally {
    loading.value = false
  }

  // 注册键盘快捷键
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

/** 更新撤销/重做状态 */
function updateUndoRedoState(lf?: InstanceType<typeof FlowCanvas>['getLf'] extends () => infer R ? R : never) {
  const instance = lf || canvasRef.value?.getLf()
  if (!instance) return
  undoable.value = instance.history.undoAble()
  redoable.value = instance.history.redoAble()
}

/** 从面板添加工作节点 */
function handleAddNode() {
  canvasRef.value?.addWorkNode()
  updateUndoRedoState()
}

/** 撤销 */
function undo() {
  canvasRef.value?.getLf()?.undo()
  updateUndoRedoState()
}

/** 重做 */
function redo() {
  canvasRef.value?.getLf()?.redo()
  updateUndoRedoState()
}

/** 保存 —— 从画布收集节点坐标和连线，批量提交后端 */
async function handleSave() {
  const lf = canvasRef.value?.getLf()
  if (!lf) return

  const templateId = Number(route.params.id)
  if (!templateId) return

  saving.value = true
  try {
    // 获取画布完整数据（含当前坐标）
    const graphData = lf.getGraphData()

    // 映射节点：LogicFlow 格式 → 后端格式
    const nodes: DesignerNode[] = graphData.nodes.map((n: any) => ({
      id: Number(n.id) || null,  // 字符串 ID 还原为数字
      name: n.properties?.name || n.text?.value || n.type,
      is_start: n.properties?.is_start ?? false,
      is_end: n.properties?.is_end ?? false,
      assignee_id: n.properties?.assignee_id ?? null,
      time_limit_days: n.properties?.time_limit_days ?? null,
      require_file: n.properties?.require_file ?? false,
      approvers: n.properties?.approvers ?? null,
      checkers: n.properties?.checkers ?? null,
      approval_strategy: n.properties?.approval_strategy ?? 'all_approve',
      is_optional: n.properties?.is_optional ?? false,
      position_x: Math.round(n.x),   // 当前坐标
      position_y: Math.round(n.y),
      sort_order: n.properties?.sort_order ?? 0,
    }))

    // 映射连线
    const edges: DesignerEdge[] = graphData.edges.map((e: any) => ({
      id: Number(e.id) || null,
      source_node_id: Number(e.sourceNodeId),
      target_node_id: Number(e.targetNodeId),
    }))

    const result = await saveDesign(templateId, { nodes, edges })
    ElMessage.success(result.is_hard_modified
      ? '已发布模板硬修改，版本已递增并回到草稿'
      : `保存成功（${result.node_count} 节点 · ${result.edge_count} 连线）`,
    )
  } catch (err: any) {
    // 网络/权限等底层错误由拦截器处理；此处兜底业务错误
    if (err?.response?.data?.message) {
      ElMessage.error(`保存失败：${err.response.data.message}`)
    }
  } finally {
    saving.value = false
  }
}

/** 发布流程：先保存 → 校验 → 发布 */
async function handlePublish() {
  const templateId = Number(route.params.id)
  if (!templateId) return

  // 先保存，确保提交最新内容
  if (canvasRef.value?.getLf()) {
    saving.value = true
    try {
      const lf = canvasRef.value.getLf()
      const graphData = lf.getGraphData()
      const nodes: DesignerNode[] = graphData.nodes.map((n: any) => ({
        id: Number(n.id) || null,
        name: n.properties?.name || n.text?.value || n.type,
        is_start: n.properties?.is_start ?? false,
        is_end: n.properties?.is_end ?? false,
        assignee_id: n.properties?.assignee_id ?? null,
        time_limit_days: n.properties?.time_limit_days ?? null,
        require_file: n.properties?.require_file ?? false,
        approvers: n.properties?.approvers ?? null,
        checkers: n.properties?.checkers ?? null,
        approval_strategy: n.properties?.approval_strategy ?? 'all_approve',
        is_optional: n.properties?.is_optional ?? false,
        position_x: Math.round(n.x),
        position_y: Math.round(n.y),
        sort_order: n.properties?.sort_order ?? 0,
      }))
      const edges: DesignerEdge[] = graphData.edges.map((e: any) => ({
        id: Number(e.id) || null,
        source_node_id: Number(e.sourceNodeId),
        target_node_id: Number(e.targetNodeId),
      }))
      await saveDesign(templateId, { nodes, edges })
    } catch {
      ElMessage.error('保存失败，无法继续发布')
      return
    } finally {
      saving.value = false
    }
  }

  // 打开发布弹窗
  showPublishDialog.value = true
  publishDialogRef.value?.reset()
  publishDialogRef.value?.setPublishing(true)
  publishing.value = true

  try {
    const result = await publishTemplate(templateId)
    publishDialogRef.value?.setPublishing(false)
    publishDialogRef.value?.setResult(result)
    ElMessage.success(`模板已发布（V${result.version_number}）`)
  } catch (err: any) {
    publishDialogRef.value?.setPublishing(false)
    const errorData = err?.response?.data?.data
    if (errorData?.errors && Array.isArray(errorData.errors)) {
      publishDialogRef.value?.setErrors(errorData.errors)
    } else {
      ElMessage.error(err?.response?.data?.message || '发布失败')
      showPublishDialog.value = false
    }
  } finally {
    publishing.value = false
  }
}
</script>

<style lang="scss" scoped>
.flow-designer {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  position: relative;
}

.designer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light);
  flex-shrink: 0;

  .header-actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .template-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin-right: 12px;
  }
}

.designer-body {
  flex: 1;
  overflow: hidden;
  display: flex;
}

/* 视图切换按钮 —— 左下角浮动 */
.view-mode-toggle {
  position: absolute;
  bottom: 16px;
  left: 16px;
  z-index: 10;
  background: #fff;
  border-radius: 6px;
  padding: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
</style>
