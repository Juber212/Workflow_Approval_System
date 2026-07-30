<template>
  <div class="flow-designer">
    <!-- 顶部工具栏 -->
    <div class="designer-header">
      <el-page-header @back="handleBack">
        <template #content>
          <span v-if="isLaunchMode">发起项目 · {{ templateName }}</span>
          <span v-else>项目设计器 · {{ templateName }}</span>
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
          <!-- 文件模板管理按钮（新建/编辑均可用，新建时需先保存） -->
          <el-button v-if="!isLaunchMode" text @click="showDocDialog = true" :disabled="isNewTemplate && !currentTemplateId()" :title="isNewTemplate && !currentTemplateId() ? '请先保存模板' : ''">📄 文件模板</el-button>
          <el-tooltip content="Ctrl+S 保存" placement="bottom">
            <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
          </el-tooltip>
        </template>
        <!-- 发起模式工具栏 -->
        <template v-else>
          <el-button @click="handleCancelLaunch">取消</el-button>
          <el-button type="primary" :loading="launching" @click="showLaunchDialog = true">发起项目</el-button>
        </template>
      </div>
    </div>

    <!-- 发起模式：业务信息卡片 -->
    <div v-if="isLaunchMode && hasBizInfo" class="biz-info-card">
      <div class="biz-info-card__item">
        <span class="biz-info-card__label">合同号</span>
        <span class="biz-info-card__value">{{ bizInfo.contract_no }}</span>
      </div>
      <div class="biz-info-card__item">
        <span class="biz-info-card__label">产品型号</span>
        <span class="biz-info-card__value">{{ bizInfo.product_model }}</span>
      </div>
      <div class="biz-info-card__item">
        <span class="biz-info-card__label">销售经理</span>
        <span class="biz-info-card__value">{{ bizInfo.sales_manager }}</span>
      </div>
    </div>

    <!-- 主体区域：画布 + 面板 -->
    <div class="designer-body" v-loading="loading">
      <div v-show="viewMode === 'canvas'" style="display:flex;flex:1;overflow:hidden;min-height:0">
        <NodePanel :lf="canvasRef?.getLf() ?? null" :presets="presets" @add="handleAddNode" @edit-preset="handleEditPreset" @delete-preset="handleDeletePreset" />
        <FlowCanvas ref="canvasRef" @node-select="handleNodeSelect" />
        <PropertyPanel :lf="canvasRef?.getLf() ?? null" :node-data="selectedNodeData" :launch-mode="isLaunchMode" @save-as-preset="handleSaveAsPreset" />
      </div>
      <NodeListView v-show="viewMode === 'list'" :nodes="getCanvasNodes()" @select-node="handleListNodeSelect" />
    </div>

    <!-- 视图切换 -->
    <div v-if="!isLaunchMode" class="view-mode-toggle">
      <el-radio-group v-model="viewMode" size="small">
        <el-radio-button value="canvas">画布</el-radio-button>
        <el-radio-button value="list">列表</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 发起项目弹窗 -->
    <el-dialog v-model="showLaunchDialog" title="发起项目" width="480px" @close="launchFormRef?.resetFields()">
      <el-form ref="launchFormRef" :model="launchForm" :rules="launchRules" label-width="80px" @submit.prevent>
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="launchForm.name" placeholder="请输入项目名称" maxlength="100" :disabled="isLaunchMode" />
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-select v-model="launchForm.priority" style="width:100%">
            <el-option label="普通" value="normal" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度" prop="difficulty">
          <el-select v-model="launchForm.difficulty" style="width:100%">
            <el-option label="1级 - 简单" value="1" />
            <el-option label="2级 - 一般" value="2" />
            <el-option label="3级 - 较难" value="3" />
            <el-option label="4级 - 困难（启用批准人）" value="4" />
          </el-select>
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="launchForm.description" type="textarea" :rows="3" placeholder="可选" maxlength="500" />
        </el-form-item>

        <!-- 文件模板选择 —— 继承模板关联，可临时调整 -->
        <el-form-item label="模板包" v-if="launchLinkedCategories.length > 0">
          <div class="launch-doc-list">
            <div v-for="c in launchLinkedCategories" :key="'lcat-' + c.id" class="launch-doc-item">
              <span>
                <el-tag size="small" type="warning" effect="plain">📦 包</el-tag>
                {{ c.name }}
                <span class="launch-doc-orig">({{ c.document_count }} 个模板)</span>
              </span>
              <span class="launch-doc-hint">发起后在项目详情页可一键下载 ZIP</span>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="文件模板" v-if="launchDocTemplates.length > 0">
          <div class="launch-doc-list">
            <el-checkbox-group v-model="launchDocSelected">
              <div v-for="d in launchDocTemplates" :key="d.id" class="launch-doc-item">
                <el-checkbox :label="d.id" :value="d.id">
                  <el-tag :type="d.file_type === 'xlsx' ? 'success' : ''" size="small" effect="plain">.{{ d.file_type }}</el-tag>
                  {{ d.name }}
                  <span class="launch-doc-orig">({{ d.original_name }})</span>
                </el-checkbox>
              </div>
            </el-checkbox-group>
            <div class="launch-doc-hint">继承自模板，可取消不需要的；如需新增请返回编辑模式关联</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showLaunchDialog = false">取消</el-button>
        <el-button type="primary" :loading="launching" @click="handleLaunch">确认发起</el-button>
      </template>
    </el-dialog>

    <!-- 预设编辑弹窗 -->
    <PresetEditor
      v-model="presetEditorVisible"
      :initial="editingPreset ? editPresetToFormData(editingPreset) : pendingPresetData"
      :editing-id="editingPreset?.id"
      @saved="onPresetSaved"
    />

    <!-- 文件模板管理弹窗 -->
    <el-dialog
      v-model="showDocDialog"
      title="关联文件模板"
      width="680px"
      @open="handleDocDialogOpen"
      destroy-on-close
    >
      <!-- 可用变量参考 -->
      <div class="doc-var-section">
        <h4>可用变量 <span class="doc-var-hint">（在模板中使用下列占位符，下载时自动替换为实际值）</span></h4>
        <div class="doc-var-tags">
          <el-tag v-for="v in docVariables" :key="v" size="small" type="info" class="doc-var-tag">{{ v }}</el-tag>
        </div>
      </div>

      <!-- 已关联项 —— 分类和模板合并为一个列表 -->
      <div v-if="linkedTotal > 0" class="doc-section">
        <h4 class="doc-section__title">已关联（{{ linkedTotal }}）</h4>
        <template v-for="item in linkedList" :key="item.key">
          <div class="doc-item" :class="{ 'doc-item--expanded': item.isCategory && expandedCats.has(item.catId) }">
            <span class="doc-item__info" @click="item.isCategory && toggleCatExpand(item.catId)" :style="item.isCategory ? 'cursor:pointer' : ''">
              <el-tag size="small" :type="item.tagType" effect="plain">{{ item.tagLabel }}</el-tag>
              <span class="doc-item__name">{{ item.name }}</span>
              <span class="doc-item__orig">{{ item.subtitle }}</span>
              <span v-if="item.isCategory" class="doc-item__expand-icon">{{ expandedCats.has(item.catId) ? '▾' : '▸' }}</span>
            </span>
            <el-button link type="danger" size="small" @click="item.isCategory ? handleUnlinkCategory(item.raw as TemplateCategorySummary) : handleUnlinkDoc(item.raw as DocTemplateItem)">移除</el-button>
          </div>
          <!-- 展开的包内模板 -->
          <div v-if="item.isCategory && expandedCats.has(item.catId)" class="doc-sub-list">
            <div v-for="sub in catDocsMap[item.catId]" :key="'sub-' + sub.id" class="doc-sub-item">
              <span class="doc-sub-item__info">
                <el-tag :type="sub.file_type === 'xlsx' ? 'success' : ''" size="small" effect="plain">.{{ sub.file_type }}</el-tag>
                <span>{{ sub.name }}</span>
              </span>
              <span class="doc-sub-item__size">{{ formatFileSize(sub.file_size) }}</span>
            </div>
            <div v-if="!catDocsMap[item.catId]?.length" class="doc-sub-empty">暂无模板</div>
          </div>
        </template>
      </div>

      <!-- 可关联项 —— 合并列表 -->
      <div v-if="availableList.length > 0" class="doc-section">
        <h4 class="doc-section__title">可关联（{{ availableList.length }}）</h4>
        <template v-for="item in availableList" :key="item.key">
          <div class="doc-item" :class="{ 'doc-item--expanded': item.isCategory && expandedCats.has(item.catId) }">
            <span class="doc-item__info" @click="item.isCategory && toggleCatExpand(item.catId)" :style="item.isCategory ? 'cursor:pointer' : ''">
              <el-tag size="small" :type="item.tagType" effect="plain">{{ item.tagLabel }}</el-tag>
              <span class="doc-item__name">{{ item.name }}</span>
              <span class="doc-item__orig">{{ item.subtitle }}</span>
              <span v-if="item.isCategory" class="doc-item__expand-icon">{{ expandedCats.has(item.catId) ? '▾' : '▸' }}</span>
            </span>
            <el-button link type="primary" size="small" @click="item.isCategory ? handleLinkCategory(item.raw as TemplateCategorySummary) : handleLinkDoc(item.raw as DocTemplateItem)">关联</el-button>
          </div>
          <!-- 展开的包内模板 -->
          <div v-if="item.isCategory && expandedCats.has(item.catId)" class="doc-sub-list">
            <div v-for="sub in catDocsMap[item.catId]" :key="'sub-' + sub.id" class="doc-sub-item">
              <span class="doc-sub-item__info">
                <el-tag :type="sub.file_type === 'xlsx' ? 'success' : ''" size="small" effect="plain">.{{ sub.file_type }}</el-tag>
                <span>{{ sub.name }}</span>
              </span>
              <span class="doc-sub-item__size">{{ formatFileSize(sub.file_size) }}</span>
            </div>
            <div v-if="!catDocsMap[item.catId]?.length" class="doc-sub-empty">暂无模板</div>
          </div>
        </template>
      </div>

      <el-empty v-if="linkedTotal === 0 && availableList.length === 0" description="暂无可用文件模板，请联系管理员上传" :image-size="60" />

      <template #footer><el-button @click="showDocDialog = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { createTemplate, getTemplateDetail, getDocTemplates, linkDocTemplates, unlinkDocTemplate, downloadTemplatesZip, type TemplateDetail, type DocTemplateItem, type TemplateCategorySummary } from '@/api/template'
import request from '@/api/request'
import { saveDesign, type DesignerNode, type DesignerEdge } from '@/api/designer'
import { createInstance, calculateDeadlines } from '@/api/instance'
import FlowCanvas from './designer/FlowCanvas.vue'
import NodePanel from './designer/NodePanel.vue'
import PropertyPanel from './designer/PropertyPanel.vue'
import PresetEditor from './designer/PresetEditor.vue'
import NodeListView from './designer/NodeListView.vue'
import { getPresets, deletePreset, type PresetItem, type PresetFormData } from '@/api/presets'
import { formatFileSize } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const launching = ref(false)
const showLaunchDialog = ref(false)
// ─── 发起弹窗文件模板 ────────────────────────────────────
const launchDocTemplates = ref<DocTemplateItem[]>([])
const launchDocSelected = ref<number[]>([])
const launchLinkedCategories = ref<TemplateCategorySummary[]>([])

const launchFormRef = ref<FormInstance>()
const templateName = ref('')
const canvasRef = ref<InstanceType<typeof FlowCanvas>>()
const undoable = ref(false)
const redoable = ref(false)
const viewMode = ref<'canvas' | 'list'>('canvas')
const selectedNodeData = ref<any>(null)

/** 预设列表 */
const presets = ref<PresetItem[]>([])
/** 预设编辑弹窗状态 */
const presetEditorVisible = ref(false)
const editingPreset = ref<PresetItem | null>(null)  // null = 新建，有值 = 编辑
/** 待传递给 PresetEditor 的预填数据 */
const pendingPresetData = ref<PresetFormData | null>(null)

// ─── 文件模板 ───────────────────────────────────────────
const showDocDialog = ref(false)
const linkedDocTemplates = ref<DocTemplateItem[]>([])
const linkedCategories = ref<TemplateCategorySummary[]>([])
const availableDocTemplates = ref<DocTemplateItem[]>([])
const availableCategories = ref<TemplateCategorySummary[]>([])
const docVariables = ref<string[]>([])

/** 包内模板明细缓存：categoryId → 模板列表 */
const catDocsMap = reactive<Record<number, DocTemplateItem[]>>({})
/** 弹窗中展开的包 ID 集合 */
const expandedCats = reactive<Set<number>>(new Set())

/** 弹窗打开时刷新列表 */
async function handleDocDialogOpen() {
  await loadDocTemplates()
}

/** 切换包展开/折叠 */
function toggleCatExpand(catId: number) {
  if (expandedCats.has(catId)) {
    expandedCats.delete(catId)
  } else {
    expandedCats.add(catId)
  }
}

/** 加载文件模板列表 */
async function loadDocTemplates() {
  const templateId = currentTemplateId()
  if (!templateId) return
  try {
    const data = await getDocTemplates(templateId)
    linkedDocTemplates.value = data.linked
    linkedCategories.value = (data as any).linked_categories || []
    availableDocTemplates.value = data.available
    availableCategories.value = (data as any).available_categories || []
    docVariables.value = data.available_variables

    // 并行拉所有包的模板明细（用公开接口，不限管理员）
    const allCats = [...linkedCategories.value, ...availableCategories.value]
    if (allCats.length === 0) return
    const details = await Promise.allSettled(
      allCats.map(c => request.get(`/template-categories/${c.id}`).then(r => r.data))
    )
    details.forEach((r, i) => {
      if (r.status === 'fulfilled' && allCats[i]) {
        catDocsMap[allCats[i].id] = r.value.documents as any as DocTemplateItem[]
      }
    })
  } catch (e) {
    console.error('加载文件模板列表失败:', e)
  }
}

/** 获取当前模板 ID（编辑模式） */
function currentTemplateId(): number | null {
  const id = route.params.id
  if (!id) return null
  const n = Number(id)
  return Number.isNaN(n) ? null : n
}

/** 关联单个模板到当前流程 */
async function handleLinkDoc(doc: DocTemplateItem) {
  const templateId = currentTemplateId()
  if (!templateId) return
  try {
    await linkDocTemplates(templateId, [doc.id])
    ElMessage.success(`已关联「${doc.name}」`)
    await loadDocTemplates()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '关联失败')
  }
}

/** 关联分类（模板包）到当前流程 */
async function handleLinkCategory(cat: TemplateCategorySummary) {
  const templateId = currentTemplateId()
  if (!templateId) return
  try {
    await linkDocTemplates(templateId, undefined, [cat.id])
    ElMessage.success(`已关联分类「${cat.name}」`)
    await loadDocTemplates()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '关联失败')
  }
}

/** 取消关联 */
async function handleUnlinkDoc(doc: DocTemplateItem) {
  const templateId = currentTemplateId()
  if (!templateId) return
  try {
    await ElMessageBox.confirm(`确定移除「${doc.name}」？`, '取消关联', { type: 'warning' })
    await unlinkDocTemplate(templateId, 'document', doc.id)
    ElMessage.success('已移除')
    await loadDocTemplates()
  } catch {
    // 用户取消
  }
}

/** 取消分类关联 */
async function handleUnlinkCategory(cat: TemplateCategorySummary) {
  const templateId = currentTemplateId()
  if (!templateId) return
  try {
    await ElMessageBox.confirm(`确定移除分类「${cat.name}」？`, '取消关联', { type: 'warning' })
    await unlinkDocTemplate(templateId, 'category', cat.id)
    ElMessage.success('已移除')
    await loadDocTemplates()
  } catch {
    // 用户取消
  }
}

/** 发起弹窗打开时加载模板关联的文件模板 */
async function loadLaunchDocTemplates() {
  const templateId = currentTemplateId()
  if (!templateId) return
  try {
    const data = await getDocTemplates(templateId)
    launchDocTemplates.value = data.linked
    launchDocSelected.value = data.linked.map(d => d.id)  // 默认全选单个模板
    launchLinkedCategories.value = (data as any).linked_categories || []
  } catch {
    launchDocTemplates.value = []
    launchLinkedCategories.value = []
  }
}

// ─── 合并列表（分类 + 模板，统一渲染）───

interface DocListItem {
  key: string
  name: string
  subtitle: string
  tagLabel: string
  tagType: '' | 'success' | 'warning' | 'info' | 'danger'
  isCategory: boolean
  catId: number  // 分类 ID，单个模板为 0
  raw: DocTemplateItem | TemplateCategorySummary
}

function _makeItems(
  cats: TemplateCategorySummary[],
  docs: DocTemplateItem[],
  keyPrefix: string,
): DocListItem[] {
  return [
    ...cats.map(c => ({
      key: `${keyPrefix}-cat-${c.id}`, name: c.name,
      subtitle: `${c.document_count} 个模板`,
      tagLabel: '📦 包', tagType: 'warning' as const,
      isCategory: true, catId: c.id, raw: c,
    })),
    ...docs.map(d => ({
      key: `${keyPrefix}-doc-${d.id}`, name: d.name,
      subtitle: d.original_name,
      tagLabel: `.${d.file_type}`, tagType: (d.file_type === 'xlsx' ? 'success' : '') as const,
      isCategory: false, catId: 0, raw: d,
    })),
  ]
}

/** 已关联总数 */
const linkedTotal = computed(() => linkedDocTemplates.value.length + linkedCategories.value.length)

/** 已关联——合并为一个列表，分类在前 */
const linkedList = computed<DocListItem[]>(() => _makeItems(linkedCategories.value, linkedDocTemplates.value, 'linked'))

/** 可关联——合并列表 */
const availableList = computed<DocListItem[]>(() => _makeItems(availableCategories.value, availableDocTemplates.value, 'avail'))

// 监听发起弹窗打开 → 加载文件模板
watch(showLaunchDialog, (val) => {
  if (val) loadLaunchDocTemplates()
})

/** 是否为发起项目模式（路由参数 mode=launch） */
const isLaunchMode = computed(() => route.query.mode === 'launch')
/** 是否为新建模板模式（还未入库，首次保存时才创建） */
const isNewTemplate = computed(() => route.query.new === '1')

/** 发起模式下的业务信息（从路由 query 读取） */
const bizInfo = computed(() => ({
  contract_no: (route.query.contract_no as string) || '',
  product_model: (route.query.product_model as string) || '',
  sales_manager: (route.query.sales_manager as string) || '',
}))
/** 关联方案 ID（从路由 query 读取，传后端用数字） */
const proposalIdFromQuery = computed(() => {
  const v = route.query.proposal_id
  return v ? Number(v) : null
})
/** 是否有业务信息可展示 */
const hasBizInfo = computed(() =>
  bizInfo.value.contract_no !== '' || bizInfo.value.product_model !== '' || bizInfo.value.sales_manager !== ''
)

/** 发起项目表单 */
const launchForm = ref({ name: '', priority: 'normal' as string, difficulty: '1' as string, description: '' })
const launchRules: FormRules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }, { min: 2, max: 100, message: '2-100字符', trigger: 'blur' }],
}

/** 发起模式下自动生成项目名称：合同号(产品型号) */
const autoLaunchName = computed(() => {
  const cn = bizInfo.value.contract_no
  const pm = bizInfo.value.product_model
  if (!cn && !pm) return ''
  return cn ? `${cn}(${pm})` : pm
})

/** 发起弹窗打开时，自动填入名称（发起模式下不可编辑） */
watch(showLaunchDialog, (val) => {
  if (val && isLaunchMode.value && autoLaunchName.value) {
    launchForm.value.name = autoLaunchName.value
  }
})

/** 系统节点的数据库 ID（保存时用于替换 LogicFlow UUID） */
const systemNodeDbIds = ref<{ start?: number; end?: number }>({})

/** 将 points 字符串（"x1,y1 x2,y2"）转为 LogicFlow pickEdgeConfig 需要的 pointsList 数组 */
function pointsStrToList(pts: string | null | undefined): Array<{ x: number; y: number }> | undefined {
  if (!pts) return undefined
  return pts.split(' ').filter(Boolean).map(p => {
    const [x, y] = p.split(',')
    return { x: Number(x), y: Number(y) }
  })
}

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
  fetchPresets() // 加载预设列表

  if (isNewTemplate.value) {
    // 新建模板：从 query 读取名称，画布预置开始+结束节点
    templateName.value = (route.query.name as string) || '新建模板'
    const lf = canvasRef.value?.getLf()
    if (lf) {
      // 等待 LogicFlow 初始化完成
      await new Promise(r => setTimeout(r, 100))
      lf.addNode({ id: 'start', type: 'start-node', x: 100, y: 300, properties: { db_id: null, name: '开始', is_start: true, is_end: false, require_file: false, approval_strategy: 'all_approve' } })
      lf.addNode({ id: 'end', type: 'end-node', x: 700, y: 300, properties: { db_id: null, name: '结束', is_start: false, is_end: true, require_file: false, approval_strategy: 'all_approve' } })
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
        nodes: detail.nodes.map(n => ({ id: String(n.id), type: mapNodeType(n), x: n.position_x, y: n.position_y, properties: { db_id: n.id, name: n.name, is_start: n.is_start, is_end: n.is_end, assignee_id: n.assignee_id, assignee_name: n.assignee_name, time_limit_days: n.time_limit_days, require_file: n.require_file, file_folders: n.file_folders, approvers: n.approvers, approvers_names: n.approvers_names, checkers: n.checkers, checkers_names: n.checkers_names, approval_strategy: n.approval_strategy, require_assignee_signature: n.require_assignee_signature, require_checker_signature: n.require_checker_signature, require_approver_signature: n.require_approver_signature, signature_x: n.signature_x, signature_y: n.signature_y, signature_page: n.signature_page } })),
        edges: detail.edges.map(e => {
          const ptsList = pointsStrToList(e.points)
          return ptsList
            ? { id: String(e.id), type: 'bezier', sourceNodeId: String(e.source_node_id), targetNodeId: String(e.target_node_id), points: e.points, pointsList: ptsList }
            : { id: String(e.id), type: 'bezier', sourceNodeId: String(e.source_node_id), targetNodeId: String(e.target_node_id) }
        }),
      })
      updateUndoRedoState(lf)

      // 发起模式：预计算每个工作节点的截止日期并写入 lf 节点属性
      if (isLaunchMode.value) {
        const workNodes = detail.nodes
          .filter(n => !n.is_start && !n.is_end)
          .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
        if (workNodes.length > 0) {
          const today = new Date().toISOString().slice(0, 10)
          try {
            const results = await calculateDeadlines(
              today,
              workNodes.map(n => ({ node_id: n.id, time_limit_days: n.time_limit_days })),
            )
            for (const r of results) {
              if (r.begin && r.deadline) {
                lf.setProperties(String(r.node_id), {
                  plan_begin: r.begin,
                  deadline: r.deadline,
                })
              }
            }
          } catch (err) {
            console.warn('预填截止日期失败（后端 /utils/calculate-deadlines 可能未部署）:', err)
          }
        }
      }
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

/** 处理 NodePanel 的 add 事件 —— 普通节点 / 预设节点 */
function handleAddNode(preset?: PresetItem) {
  if (!preset) {
    // 空白工作节点
    canvasRef.value?.addWorkNode()
  } else {
    // 预设节点：构建 properties
    const props = buildPresetProperties(preset)
    // 人员失效检测
    validatePresetUsers(preset)
    canvasRef.value?.addWorkNode(undefined, undefined, props)
  }
  updateUndoRedoState()
}

function handleDelete() { canvasRef.value?.deleteSelected(); updateUndoRedoState() }
function undo() { canvasRef.value?.getLf()?.undo(); updateUndoRedoState() }
function redo() { canvasRef.value?.getLf()?.redo(); updateUndoRedoState() }

/** 返回 —— 编辑模式回到上一页，发起模式直接回项目管理 */
function handleBack() {
  if (isLaunchMode.value) router.push({ name: 'Flows' })
  else router.back()
}

function handleCancelLaunch() { router.push({ name: 'Flows' }) }

// ==================== 预设相关 ====================

/** 加载当前用户的预设列表 */
async function fetchPresets() {
  try {
    const res = await getPresets()
    presets.value = res.items || []
  } catch (e) { /* 静默失败，预设列表为空 */ console.error('加载预设列表失败:', e) }
}

/** 从 PresetItem 构建节点 properties */
function buildPresetProperties(preset: PresetItem): Record<string, any> {
  return {
    name: preset.node_name,
    is_start: false, is_end: false,
    assignee_id: preset.assignee_id ?? null,
    assignee_name: preset.assignee_name || null,
    checkers: preset.checkers?.map(c => c.user_id) || null,
    checkers_names: preset.checkers_names || null,
    approvers: preset.approvers?.map(a => a.user_id) || null,
    approvers_names: preset.approvers_names || null,
    time_limit_days: preset.time_limit_days ?? null,
    require_file: preset.require_file ?? true,
    approval_strategy: 'all_approve',
  }
}

/** 检测预设中的人员是否在当前系统中有效 */
function validatePresetUsers(preset: PresetItem) {
  // 从 UserSelector 缓存中检查（简单方案：根据 *_name 是否为空判断）
  const missing: string[] = []
  if (preset.assignee_id && !preset.assignee_name) {
    missing.push(`负责人(ID:${preset.assignee_id})`)
  }
  // 校验人检测
  if (preset.checkers) {
    for (let i = 0; i < preset.checkers.length; i++) {
      const name = preset.checkers_names?.[i]
      if (!name) missing.push(`校验人(ID:${preset.checkers[i].user_id})`)
    }
  }
  // 审批人检测
  if (preset.approvers) {
    for (let i = 0; i < preset.approvers.length; i++) {
      const name = preset.approvers_names?.[i]
      if (!name) missing.push(`审批人(ID:${preset.approvers[i].user_id})`)
    }
  }
  // toast 提示
  if (missing.length > 0) {
    ElMessage.warning(`预设「${preset.name}」中的以下人员已不可用：${missing.join('、')}`)
  }
}

/** 打开预设编辑弹窗（新建 / 编辑） */
function handleEditPreset(preset?: PresetItem) {
  editingPreset.value = preset || null
  presetEditorVisible.value = true
}

/** 删除预设 */
async function handleDeletePreset(preset: PresetItem) {
  try {
    await ElMessageBox.confirm(`确定删除预设「${preset.name}」？`, '删除确认', { type: 'warning' })
  } catch {
    /* 用户取消或关闭弹窗 */
    return
  }
  try {
    await deletePreset(preset.id)
    ElMessage.success('预设已删除')
    await fetchPresets()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '删除失败')
  }
}

/** PropertyPanel "保存为预设"事件 */
function handleSaveAsPreset(formData: any) {
  editingPreset.value = null  // 新建模式
  presetEditorVisible.value = true
  // 将 formData 暂存，PresetEditor 打开时预填
  pendingPresetData.value = {
    name: formData.name || '',
    node_name: formData.name || '',
    assignee_id: formData.assignee_id,
    assignee_name: formData.assignee_name || null,
    checkers: formData.checkers?.map((id: number) => ({ user_id: id })) || null,
    checkers_names: formData.checkers_names || null,
    approvers: formData.approvers?.map((id: number) => ({ user_id: id })) || null,
    approvers_names: formData.approvers_names || null,
    time_limit_days: formData.time_limit_days,
    require_file: formData.require_file,
  }
}

/** PresetEditor 保存成功回调 */
async function onPresetSaved() {
  await fetchPresets()
  pendingPresetData.value = null
}

/** 将 PresetItem 转为 PresetFormData（编辑场景） */
function editPresetToFormData(preset: PresetItem): PresetFormData {
  return {
    name: preset.name,
    node_name: preset.node_name,
    assignee_id: preset.assignee_id,
    assignee_name: preset.assignee_name,       // 传递姓名，避免 UserSelector 空白
    checkers: preset.checkers,
    checkers_names: preset.checkers_names,       // 传递姓名
    approvers: preset.approvers,
    approvers_names: preset.approvers_names,     // 传递姓名
    time_limit_days: preset.time_limit_days,
    require_file: preset.require_file,
  }
}

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
      file_folders: n.properties?.file_folders ?? null,  // 文件提交文件夹配置
      checkers: n.properties?.checkers ?? null, approval_strategy: n.properties?.approval_strategy ?? 'all_approve',
      require_assignee_signature: n.properties?.require_assignee_signature ?? true,
      require_checker_signature: n.properties?.require_checker_signature ?? true,
      require_approver_signature: n.properties?.require_approver_signature ?? true,
      endorser_id: n.properties?.endorser_id ?? null,
      require_endorser_signature: n.properties?.require_endorser_signature ?? true,
      signature_x: n.properties?.signature_x ?? 400,
      signature_y: n.properties?.signature_y ?? 100,
      signature_page: n.properties?.signature_page ?? -1,
      position_x: Math.round(n.x), position_y: Math.round(n.y),
      sort_order: n.properties?.sort_order ?? 0,
    }))
    const edges: DesignerEdge[] = graphData.edges
      .filter((e: any) => e.sourceNodeId && e.targetNodeId)
      .map((e: any) => {
        // getGraphData() 不包含 points，需从 Model 实例直接读取
        const edgeModel = lf.getEdgeModelById(e.id) as any
        return { id: Number(e.id) || null, source_node_id: resolveNodeId(e.sourceNodeId, idMapping) ?? String(e.sourceNodeId), target_node_id: resolveNodeId(e.targetNodeId, idMapping) ?? String(e.targetNodeId), points: edgeModel?.points || null }
      })

    let templateId = Number(route.params.id)
    if (isNewTemplate.value) {
      // 新建模板：先创建模板（入库），再保存设计数据
      const name = (route.query.name as string) || '新建模板'
      const orgId = Number(route.query.org_id) || 0
      const desc = (route.query.desc as string) || undefined
      const tpl = await createTemplate({ name, description: desc, organization_id: orgId })
      templateId = tpl.id
      // 更新 URL 为真实模板 ID，后续保存即为更新模式
      router.replace({ name: 'FlowDesigner', params: { id: templateId }, query: { mode: route.query.mode as string } })
      // 新建后刷新文件模板列表（按钮变为可用）
      await loadDocTemplates()
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
      file_folders: n.properties?.file_folders ?? null,  // 文件提交文件夹配置
      checkers: n.properties?.checkers ?? null, approval_strategy: n.properties?.approval_strategy ?? 'all_approve',
      require_assignee_signature: n.properties?.require_assignee_signature ?? true,
      require_checker_signature: n.properties?.require_checker_signature ?? true,
      require_approver_signature: n.properties?.require_approver_signature ?? true,
      endorser_id: n.properties?.endorser_id ?? null,
      require_endorser_signature: n.properties?.require_endorser_signature ?? true,
      signature_x: n.properties?.signature_x ?? 400,
      signature_y: n.properties?.signature_y ?? 100,
      signature_page: n.properties?.signature_page ?? -1,
      position_x: Math.round(n.x), position_y: Math.round(n.y),
      sort_order: n.properties?.sort_order ?? 0,
    }))
    const edges: DesignerEdge[] = graphData.edges
      .filter((e: any) => e.sourceNodeId && e.targetNodeId)
      .map((e: any) => {
        // getGraphData() 不包含 points，需从 Model 实例直接读取
        const edgeModel = lf.getEdgeModelById(e.id) as any
        return { id: Number(e.id) || null, source_node_id: resolveNodeId(e.sourceNodeId, idMapping) ?? String(e.sourceNodeId), target_node_id: resolveNodeId(e.targetNodeId, idMapping) ?? String(e.targetNodeId), points: edgeModel?.points || null }
      })
    await saveDesign(templateId, { nodes, edges })

    // 2. 收集节点覆盖配置（截止日期 + 人员调整）
    const nodeOverrides: { node_id: number; deadline?: string; assignee_id?: number; checkers?: { user_id: number }[]; approvers?: { user_id: number }[] }[] = []
    for (const n of graphData.nodes) {
      // 只处理工作节点（有 db_id 的）且存在 deadline 属性
      const dbId = n.properties?.db_id
      if (dbId == null) continue
      if (n.properties?.is_start || n.properties?.is_end) continue
      const override: any = { node_id: Number(dbId) }
      let hasOverride = false
      // 截止日期覆盖（从节点 deadline 属性取截止日）
      if (n.properties?.deadline) {
        override.deadline = n.properties.deadline
        hasOverride = true
      }
      // 人员变更覆盖（与模板不同时才传）
      if (n.properties?.assignee_id != null) {
        override.assignee_id = n.properties.assignee_id
        hasOverride = true
      }
      if (n.properties?.endorser_id != null) {
        (override as any).endorser_id = n.properties.endorser_id
        hasOverride = true
      }
      if (hasOverride) nodeOverrides.push(override)
    }

    // 3. 发起项目
    const result = await createInstance({
      template_id: templateId,
      name: launchForm.value.name.trim(),
      priority: launchForm.value.priority,
      difficulty: launchForm.value.difficulty,
      description: launchForm.value.description || undefined,
      contract_no: bizInfo.value.contract_no || undefined,
      product_model: bizInfo.value.product_model || undefined,
      sales_manager: bizInfo.value.sales_manager || undefined,
      proposal_id: proposalIdFromQuery.value || undefined,
      node_overrides: nodeOverrides.length > 0 ? nodeOverrides : undefined,
      doc_template_ids: launchDocSelected.value.length > 0 ? launchDocSelected.value : undefined,
    })
    ElMessage.success('流程发起成功')
    showLaunchDialog.value = false
    router.push({ name: 'InstanceDetail', params: { id: result.id } })
  } catch (err: any) {
    if (err?.response?.data?.message) ElMessage.error(err.response.data.message)
    else ElMessage.error('发起项目失败')
  } finally { launching.value = false }
}
</script>

<style lang="scss" scoped>
.flow-designer { display: flex; flex-direction: column; height: 100%; position: relative; }
.designer-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: #fff; border-bottom: 1px solid var(--el-border-color-light); flex-shrink: 0; .header-actions { display: flex; align-items: center; gap: 4px; } }
.designer-body { flex: 1; overflow: hidden; display: flex; }
.view-mode-toggle { position: absolute; bottom: 16px; left: 16px; z-index: 10; background: #fff; border-radius: 6px; padding: 4px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08); }

/* ─── 发起模式：业务信息卡片 ─── */
.biz-info-card {
  display: flex; align-items: center; gap: 32px;
  padding: 10px 24px; background: #f5f7fa; border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
  &__item { display: flex; align-items: center; gap: 8px; }
  &__label { font-size: 12px; color: var(--el-text-color-secondary); }
  &__value { font-size: 13px; font-weight: 500; color: var(--el-text-color-primary); }
}

/* ─── 文件模板弹窗 ─── */
.doc-var-section {
  margin-bottom: 16px; padding: 10px 14px; background: #f5f7fa; border-radius: 6px;
  h4 { margin: 0 0 8px; font-size: 13px; font-weight: 500; }
  .doc-var-hint { font-size: 12px; color: var(--el-text-color-secondary); font-weight: 400; }
}
.doc-var-tags { display: flex; flex-wrap: wrap; gap: 6px; .doc-var-tag { font-family: monospace; font-size: 12px; } }

/* 文件模板选择弹窗 */
.doc-section {
  margin-bottom: 16px;
  &__title { font-size: 13px; font-weight: 600; margin: 0 0 8px; color: var(--el-text-color-primary); }
  &__hint { font-size: 12px; color: var(--el-text-color-secondary); font-weight: 400; margin-left: 8px; }
}
.doc-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px;
  margin-bottom: 6px; transition: background .15s;
  &:hover { background: var(--el-fill-color-light); }
  &--expanded { border-color: var(--el-color-primary-light-5); border-radius: 6px 6px 0 0; margin-bottom: 0; }
  &__info { display: flex; align-items: center; gap: 8px; min-width: 0; }
  &__name { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  &__orig { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  &__size { font-size: 11px; color: var(--el-text-color-placeholder); white-space: nowrap; }
  &__expand-icon { font-size: 11px; color: var(--el-text-color-secondary); margin-left: auto; }
}

/* 包内子模板列表 */
.doc-sub-list {
  border: 1px solid var(--el-color-primary-light-5); border-top: none;
  border-radius: 0 0 6px 6px;
  margin-top: -1px; margin-bottom: 6px;
  background: var(--el-color-primary-light-9);
}
.doc-sub-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 12px 5px 28px;
  &:not(:last-child) { border-bottom: 1px solid var(--el-color-primary-light-7); }
  &__info { display: flex; align-items: center; gap: 6px; font-size: 12px; }
  &__size { font-size: 11px; color: var(--el-text-color-placeholder); }
}
.doc-sub-empty {
  padding: 8px 28px; font-size: 12px; color: var(--el-text-color-placeholder);
}

.doc-upload-row {
  display: flex; align-items: center; gap: 12px; margin-bottom: 16px;
  .doc-upload-hint { font-size: 12px; color: var(--el-text-color-secondary); }
}
.doc-table { width: 100%; }

/* ─── 发起弹窗文件模板选择列表 ─── */
.launch-doc-list {
  max-height: 160px; overflow-y: auto;
  .launch-doc-item {
    padding: 2px 0;
    .el-checkbox { display: flex; align-items: center; }
  }
  .launch-doc-orig { font-size: 11px; color: var(--el-text-color-placeholder); margin-left: 4px; }
  .launch-doc-hint { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 4px; }
}
</style>
