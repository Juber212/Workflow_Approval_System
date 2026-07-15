<template>
  <div class="flow-designer">
    <!-- 顶部工具栏 -->
    <div class="designer-header">
      <el-page-header @back="handleBack">
        <template #content>
          <span v-if="isLaunchMode">发起流程 · {{ templateName }}</span>
          <span v-else>流程设计器 · {{ templateName }}</span>
        </template>
      </el-page-header>
      <div class="header-actions">
        <!-- 编辑模式工具栏 -->
        <template v-if="!isLaunchMode">
          <el-tooltip content="Ctrl+Z 撤销" placement="bottom">
            <el-button text @click="undo" :disabled="!undoable">↩ 撤销</el-button>
          </el-tooltip>
          <el-tooltip content="Ctrl+Y 重做" placement="bottom">
            <el-button text @click="redo" :disabled="!redoable">↪ 重做</el-button>
          </el-tooltip>
          <el-tooltip content="Delete 键删除选中" placement="bottom">
            <el-button text type="danger" @click="handleDelete">🗑 删除</el-button>
          </el-tooltip>
          <el-divider direction="vertical" />
          <el-tooltip content="Ctrl+S 保存" placement="bottom">
            <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
          </el-tooltip>
        </template>
        <!-- 发起模式工具栏 -->
        <template v-else>
          <el-button @click="handleCancelLaunch">取消</el-button>
          <el-button type="primary" :loading="launching" @click="showLaunchDialog = true">发起流程</el-button>
        </template>
      </div>
    </div>

    <!-- 主体区域：画布 + 面板 -->
    <div class="designer-body" v-loading="loading">
      <div v-show="viewMode === 'canvas'" style="display:flex;flex:1;overflow:hidden;min-height:0">
        <NodePanel :lf="canvasRef?.getLf() ?? null" @add="handleAddNode" @add-optional="handleAddOptionalNode" />
        <FlowCanvas ref="canvasRef" @node-select="handleNodeSelect" />
        <PropertyPanel :lf="canvasRef?.getLf() ?? null" :node-data="selectedNodeData" />
      </div>
      <NodeListView v-show="viewMode === 'list'" :nodes="getCanvasNodes()" @select-node="handleListNodeSelect" />
    </div>

    <div class="view-mode-toggle">
      <el-radio-group v-model="viewMode" size="small">
        <el-radio-button value="canvas">画布</el-radio-button>
        <el-radio-button value="list">列表</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 发起流程弹窗 -->
    <el-dialog v-model="showLaunchDialog" title="发起流程实例" width="480px" @close="launchFormRef?.resetFields()">
      <el-form ref="launchFormRef" :model="launchForm" :rules="launchRules" label-width="80px" @submit.prevent>
        <el-form-item label="实例名称" prop="name">
          <el-input v-model="launchForm.name" placeholder="请输入流程实例名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-select v-model="launchForm.priority" style="width:100%">
            <el-option label="普通" value="normal" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="launchForm.description" type="textarea" :rows="3" placeholder="可选" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showLaunchDialog = false">取消</el-button>
        <el-button type="primary" :loading="launching" @click="handleLaunch">确认发起</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { createTemplate, getTemplateDetail, type TemplateDetail } from '@/api/template'
import { saveDesign, type DesignerNode, type DesignerEdge } from '@/api/designer'
import { createInstance } from '@/api/instance'
import FlowCanvas from './designer/FlowCanvas.vue'
import NodePanel from './designer/NodePanel.vue'
import PropertyPanel from './designer/PropertyPanel.vue'
import NodeListView from './designer/NodeListView.vue'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const launching = ref(false)
const showLaunchDialog = ref(false)
const launchFormRef = ref<FormInstance>()
const templateName = ref('')
const canvasRef = ref<InstanceType<typeof FlowCanvas>>()
const undoable = ref(false)
const redoable = ref(false)
const viewMode = ref<'canvas' | 'list'>('canvas')
const selectedNodeData = ref<any>(null)

/** 是否为发起流程模式（路由参数 mode=launch） */
const isLaunchMode = computed(() => route.query.mode === 'launch')
/** 是否为新建模板模式（还未入库，首次保存时才创建） */
const isNewTemplate = computed(() => route.query.new === '1')

/** 发起流程表单 */
const launchForm = ref({ name: '', priority: 'normal' as string, description: '' })
const launchRules: FormRules = {
  name: [{ required: true, message: '请输入实例名称', trigger: 'blur' }, { min: 2, max: 100, message: '2-100字符', trigger: 'blur' }],
}

/** 系统节点的数据库 ID（保存时用于替换 LogicFlow UUID） */
const systemNodeDbIds = ref<{ start?: number; end?: number }>({})

/** 构建节点 LF UUID → 数据库 ID 的映射（通过 properties.db_id） */
function buildSystemIdMapping(graphData: { nodes: any[]; edges: any[] }): Record<string, number> {
  const mapping: Record<string, number> = {}
  for (const n of graphData.nodes) {
    if (n.properties?.db_id != null) {
      mapping[String(n.id)] = Number(n.properties.db_id)
    }
  }
  return mapping
}

function resolveNodeId(lfId: string | number, mapping: Record<string, number>): number | string | null {
  if (mapping[String(lfId)] !== undefined) return mapping[String(lfId)]
  const num = Number(lfId)
  // 能转数字 → 返回数字（DB ID）；否则返回原始字符串（新节点临时 ID，由后端 new_node_id_map 解析）
  return Number.isNaN(num) ? String(lfId) : num
}

function handleNodeSelect(nodeData: any | null) { selectedNodeData.value = nodeData }
function getCanvasNodes(): any[] {
  const lf = canvasRef.value?.getLf()
  if (!lf) return []
  const nodes = (lf.getGraphData().nodes || []).map((n: any) => ({
    id: n.id, name: n.properties?.name || n.text?.value || '',
    is_start: n.properties?.is_start ?? false, is_end: n.properties?.is_end ?? false,
    assignee_id: n.properties?.assignee_id ?? null, assignee_name: n.properties?.assignee_name || '',
    checkers: n.properties?.checkers ?? null, checkers_names: n.properties?.checkers_names || null,
    approvers: n.properties?.approvers ?? null, approvers_names: n.properties?.approvers_names || null,
    time_limit_days: n.properties?.time_limit_days ?? null,
    sort_order: n.properties?.sort_order ?? 0,
  }))
  // 按 sort_order 排序，并行同级节点保持稳定序
  nodes.sort((a: any, b: any) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
  return nodes
}

function handleListNodeSelect(nodeId: string | number) {
  viewMode.value = 'canvas'
  const lf = canvasRef.value?.getLf()
  if (!lf) return
  lf.selectNodeById(String(nodeId))
  const nd = lf.getNodeModelById(String(nodeId))
  if (nd) lf.focusOn({ coordinate: { x: nd.x, y: nd.y } })
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); handleSave() }
}

onMounted(async () => {
  window.addEventListener('keydown', handleKeydown)

  if (isNewTemplate.value) {
    // 新建模板：从 query 读取名称，画布预置开始+结束节点
    templateName.value = (route.query.name as string) || '新建模板'
    const lf = canvasRef.value?.getLf()
    if (lf) {
      // 等待 LogicFlow 初始化完成
      await new Promise(r => setTimeout(r, 100))
      lf.addNode({ id: 'start', type: 'start-node', x: 100, y: 300, properties: { db_id: null, name: '开始', is_start: true, is_end: false, require_file: false, approval_strategy: 'all_approve', is_optional: false } })
      lf.addNode({ id: 'end', type: 'end-node', x: 700, y: 300, properties: { db_id: null, name: '结束', is_start: false, is_end: true, require_file: false, approval_strategy: 'all_approve', is_optional: false } })
      updateUndoRedoState(lf)
    }
    loading.value = false
    return
  }

  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    const detail: TemplateDetail = await getTemplateDetail(id)
    templateName.value = detail.name
    const startNode = detail.nodes.find(n => n.is_start)
    const endNode = detail.nodes.find(n => n.is_end)
    systemNodeDbIds.value = { start: startNode?.id, end: endNode?.id }

    const lf = canvasRef.value?.getLf()
    if (lf && detail.nodes.length > 0) {
      function mapNodeType(n: typeof detail.nodes[number]): string {
        if (n.is_start) return 'start-node'
        if (n.is_end) return 'end-node'
        return 'work-node'
      }
      lf.renderRawData({
        nodes: detail.nodes.map(n => ({ id: String(n.id), type: mapNodeType(n), x: n.position_x, y: n.position_y, properties: { db_id: n.id, name: n.name, is_start: n.is_start, is_end: n.is_end, assignee_id: n.assignee_id, assignee_name: n.assignee_name, time_limit_days: n.time_limit_days, require_file: n.require_file, approvers: n.approvers, approvers_names: n.approvers_names, checkers: n.checkers, checkers_names: n.checkers_names, approval_strategy: n.approval_strategy, is_optional: n.is_optional } })),
        edges: detail.edges.map(e => ({ id: String(e.id), type: 'polyline', sourceNodeId: String(e.source_node_id), targetNodeId: String(e.target_node_id) })),
      })
      updateUndoRedoState(lf)
    }
  } catch { ElMessage.error('加载模板数据失败') }
  finally { loading.value = false }
})

onUnmounted(() => { window.removeEventListener('keydown', handleKeydown) })

function updateUndoRedoState(lf?: any) {
  const instance = lf || canvasRef.value?.getLf()
  if (!instance) return
  undoable.value = instance.history.undoAble()
  redoable.value = instance.history.redoAble()
}

function handleAddNode() { canvasRef.value?.addWorkNode(); updateUndoRedoState() }
function handleAddOptionalNode() { canvasRef.value?.addOptionalNode(); updateUndoRedoState() }
function handleDelete() { canvasRef.value?.deleteSelected(); updateUndoRedoState() }
function undo() { canvasRef.value?.getLf()?.undo(); updateUndoRedoState() }
function redo() { canvasRef.value?.getLf()?.redo(); updateUndoRedoState() }

/** 返回 —— 编辑模式回到上一页，发起模式直接回流程管理 */
function handleBack() {
  if (isLaunchMode.value) router.push('/flows')
  else router.back()
}

function handleCancelLaunch() { router.push('/flows') }

/** 保存模板设计 */
async function handleSave() {
  const lf = canvasRef.value?.getLf()
  if (!lf) return
  saving.value = true
  try {
    const graphData = lf.getGraphData()
    const idMapping = buildSystemIdMapping(graphData)
    const nodes: DesignerNode[] = graphData.nodes.map((n: any) => ({
      id: resolveNodeId(n.id, idMapping), name: n.properties?.name || n.text?.value || n.type,
      is_start: n.properties?.is_start ?? false, is_end: n.properties?.is_end ?? false,
      assignee_id: n.properties?.assignee_id ?? null, time_limit_days: n.properties?.time_limit_days ?? null,
      require_file: n.properties?.require_file ?? false, approvers: n.properties?.approvers ?? null,
      checkers: n.properties?.checkers ?? null, approval_strategy: n.properties?.approval_strategy ?? 'all_approve',
      is_optional: n.properties?.is_optional ?? false, position_x: Math.round(n.x), position_y: Math.round(n.y),
      sort_order: n.properties?.sort_order ?? 0,
    }))
    const edges: DesignerEdge[] = graphData.edges
      .filter((e: any) => e.sourceNodeId && e.targetNodeId)
      .map((e: any) => ({ id: Number(e.id) || null, source_node_id: resolveNodeId(e.sourceNodeId, idMapping) ?? String(e.sourceNodeId), target_node_id: resolveNodeId(e.targetNodeId, idMapping) ?? String(e.targetNodeId) }))

    let templateId = Number(route.params.id)
    if (isNewTemplate.value) {
      // 新建模板：先创建模板（入库），再保存设计数据
      const name = (route.query.name as string) || '新建模板'
      const orgId = Number(route.query.org_id) || 0
      const desc = (route.query.desc as string) || undefined
      const tpl = await createTemplate({ name, description: desc, organization_id: orgId })
      templateId = tpl.id
      // 更新 URL 为真实模板 ID，后续保存即为更新模式
      router.replace({ path: `/flows/designer/${templateId}`, query: { mode: route.query.mode as string } })
    }

    await saveDesign(templateId, { nodes, edges })
    ElMessage.success(`保存成功（${nodes.length} 节点 · ${edges.length} 连线）`)
  } catch (err: any) {
    if (err?.response?.data?.message) ElMessage.error(`保存失败：${err.response.data.message}`)
  } finally { saving.value = false }
}

/** 发起模式：先保存模板，再创建实例，跳转详情页 */
async function handleLaunch() {
  const valid = await launchFormRef.value?.validate().catch(() => false)
  if (!valid) return

  const lf = canvasRef.value?.getLf()
  if (!lf) return
  const templateId = Number(route.params.id)
  if (!templateId) return

  launching.value = true
  try {
    // 1. 先保存模板最新设计
    const graphData = lf.getGraphData()
    const idMapping = buildSystemIdMapping(graphData)
    const nodes: DesignerNode[] = graphData.nodes.map((n: any) => ({
      id: resolveNodeId(n.id, idMapping), name: n.properties?.name || n.text?.value || n.type,
      is_start: n.properties?.is_start ?? false, is_end: n.properties?.is_end ?? false,
      assignee_id: n.properties?.assignee_id ?? null, time_limit_days: n.properties?.time_limit_days ?? null,
      require_file: n.properties?.require_file ?? false, approvers: n.properties?.approvers ?? null,
      checkers: n.properties?.checkers ?? null, approval_strategy: n.properties?.approval_strategy ?? 'all_approve',
      is_optional: n.properties?.is_optional ?? false, position_x: Math.round(n.x), position_y: Math.round(n.y),
      sort_order: n.properties?.sort_order ?? 0,
    }))
    const edges: DesignerEdge[] = graphData.edges
      .filter((e: any) => e.sourceNodeId && e.targetNodeId)
      .map((e: any) => ({ id: Number(e.id) || null, source_node_id: resolveNodeId(e.sourceNodeId, idMapping) ?? String(e.sourceNodeId), target_node_id: resolveNodeId(e.targetNodeId, idMapping) ?? String(e.targetNodeId) }))
    await saveDesign(templateId, { nodes, edges })

    // 2. 发起流程实例
    const result = await createInstance({
      template_id: templateId,
      name: launchForm.value.name.trim(),
      priority: launchForm.value.priority,
      description: launchForm.value.description || undefined,
    })
    ElMessage.success('流程发起成功')
    showLaunchDialog.value = false
    router.push(`/flows/instances/${result.id}`)
  } catch (err: any) {
    if (err?.response?.data?.message) ElMessage.error(err.response.data.message)
    else ElMessage.error('发起流程失败')
  } finally { launching.value = false }
}
</script>

<style lang="scss" scoped>
.flow-designer { display: flex; flex-direction: column; height: 100%; position: relative; }
.designer-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: #fff; border-bottom: 1px solid var(--el-border-color-light); flex-shrink: 0; .header-actions { display: flex; align-items: center; gap: 4px; } }
.designer-body { flex: 1; overflow: hidden; display: flex; }
.view-mode-toggle { position: absolute; bottom: 16px; left: 16px; z-index: 10; background: #fff; border-radius: 6px; padding: 4px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08); }
</style>
