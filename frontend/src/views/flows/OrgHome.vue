<template>
  <!-- 所内主页 —— 实例 Tab + 模板 Tab（PRD P04） -->
  <div class="org-home">
    <!-- 页面头部 —— 所信息 + 操作按钮 -->
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">{{ orgName }}</h1>
        <p class="page-header__subtitle" v-if="orgInfo">
          模板 {{ orgInfo.template_count }} 个 · 运行中 {{ orgInfo.running_instance_count }} 个
          <span v-if="orgInfo.latest_update_time"> · 最近更新 {{ formatTime(orgInfo.latest_update_time) }}</span>
        </p>
      </div>
      <div class="page-header__actions" v-if="isOrgManager">
        <el-button type="primary" @click="showTemplatePicker = true">发起项目</el-button>
      </div>
    </div>

    <!-- 选择模板并填写业务信息（发起项目） -->
    <el-dialog v-model="showTemplatePicker" title="发起项目" width="560px" @close="resetPickerForm">
      <el-input v-model="tplKeyword" placeholder="搜索模板名称" clearable style="margin-bottom:12px" />
      <el-table
        :data="templateList" v-loading="pickerLoading"
        @row-click="handleSelectTemplate" style="cursor:pointer" max-height="280"
        :row-class-name="({ row }: any) => row.id === selectedTplId ? 'is-selected-row' : ''"
      >
        <el-table-column prop="name" label="模板名称" min-width="160" />
        <el-table-column prop="node_count" label="节点数" width="80" align="center" />
        <el-table-column prop="instance_count" label="运行项目" width="80" align="center" />
      </el-table>

      <!-- 业务信息表单（选择模板后出现） -->
      <template v-if="selectedTplId">
        <el-divider />
        <el-form :model="pickerForm" label-width="80px" size="default" @submit.prevent>
          <el-form-item label="合同号" required>
            <el-input v-model="pickerForm.contract_no" placeholder="请输入合同号" maxlength="100" />
          </el-form-item>
          <el-form-item label="产品型号" required>
            <el-input v-model="pickerForm.product_model" placeholder="请输入产品型号" maxlength="100" />
          </el-form-item>
          <el-form-item label="销售经理" required>
            <el-input v-model="pickerForm.sales_manager" placeholder="请输入销售经理姓名" maxlength="50" />
          </el-form-item>
          <el-form-item label="关联方案">
            <el-select
              v-model="pickerForm.proposal_id"
              placeholder="选择已完成的方案（可选）"
              style="width: 100%"
              clearable
              filterable
              :disabled="completedProposals.length === 0"
              :no-data-text="completedProposals.length === 0 ? '该组织暂无已完成方案' : '无匹配方案'"
            >
              <el-option
                v-for="p in completedProposals"
                :key="p.id"
                :label="p.name"
                :value="p.id"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </template>

      <template #footer>
        <el-button @click="showTemplatePicker = false">取消</el-button>
        <el-button type="primary" :disabled="!pickerCanConfirm" @click="handleConfirmLaunch">确认发起</el-button>
      </template>
    </el-dialog>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="org-tabs">
      <!-- 默认选中实例 Tab（P04 规范） -->
      <el-tab-pane label="项目" name="instance" />
      <el-tab-pane label="项目模板" name="template" />
    </el-tabs>

    <!-- ========== 项目 Tab ========== -->
    <template v-if="activeTab === 'instance'">
      <!-- 状态筛选标签 -->
      <div class="filter-tabs">
        <button
          v-for="f in instanceFilters"
          :key="f.value"
          class="filter-tab"
          :class="{ 'is-active': instanceStatusFilter === f.value }"
          @click="handleInstanceFilter(f.value)"
        >
          <span class="filter-label">{{ f.label }}</span>
          <span class="filter-count">{{ statusCounts[f.value] ?? '—' }}</span>
        </button>
        <el-input
          v-model="instanceKeyword"
          placeholder="搜索项目名称"
          clearable
          :prefix-icon="Search"
          size="default"
          style="width: 220px; margin-left: auto"
          @input="handleInstanceSearch"
        />
      </div>

      <!-- 实例表格 -->
      <div class="card">
        <div class="card__body" style="padding:0">
          <el-table
            :data="instances" stripe v-loading="instanceLoading"
            :row-class-name="instanceRowClass"
            @row-click="(row: any) => router.push(`/flows/instances/${row.id}`)"
            style="cursor:pointer"
          >
            <!-- ===== 弹性列（按内容自适配） ===== -->
            <!-- 1. 项目名称 -->
            <el-table-column prop="name" label="项目名称" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="inst-name">{{ row.name }}</span>
              </template>
            </el-table-column>
            <!-- 2. 方案 -->
            <el-table-column label="方案" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="inst-meta">{{ row.proposal_name || '-' }}</span>
              </template>
            </el-table-column>
            <!-- 3. 进度（进度条） -->
            <el-table-column label="进度" min-width="120" align="center">
              <template #default="{ row }">
                <div class="bt-progress">
                  <el-progress
                    :percentage="row.total_nodes > 0 ? Math.round((row.current_node_index / row.total_nodes) * 100) : 0"
                    :stroke-width="8"
                    :show-text="false"
                  />
                  <span class="bt-progress__text">
                    {{ row.total_nodes > 0 ? Math.round((row.current_node_index / row.total_nodes) * 100) : 0 }}%（{{ row.current_node_index }}/{{ row.total_nodes }}）
                  </span>
                </div>
              </template>
            </el-table-column>
            <!-- ===== 固定列 ===== -->
            <!-- 4. 当前负责人 -->
            <el-table-column label="当前负责人" width="110" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="inst-meta">{{ row.current_assignee_name || '-' }}</span>
              </template>
            </el-table-column>
            <!-- 5. 状态 -->
            <el-table-column label="状态" width="80" align="center" sortable="false">
              <template #default="{ row }">
                <span class="status-tag" :class="instStatusClass(row.status)">{{ instStatusLabel(row.status) }}</span>
              </template>
            </el-table-column>
            <!-- 6. 优先级 -->
            <el-table-column label="优先级" width="72" align="center">
              <template #default="{ row }">
                <span class="pri-badge" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span>
              </template>
            </el-table-column>
            <!-- 7. 难度 -->
            <el-table-column label="难度" width="64" align="center">
              <template #default="{ row }">
                <span class="diff-badge" :class="'diff--' + (row.difficulty || '1')">{{ row.difficulty || '1' }}级</span>
              </template>
            </el-table-column>
            <!-- 8. 发起时间 -->
            <el-table-column prop="initiated_at" label="发起时间" width="150" align="center">
              <template #default="{ row }">{{ formatTime(row.initiated_at) }}</template>
            </el-table-column>
            <!-- 9. 操作 -->
            <!-- 管理员多一个"删除"按钮，列宽稍大避免换行 -->
            <el-table-column label="操作" :width="isAdmin ? 160 : 140" align="center" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" size="small" @click.stop="router.push(`/flows/instances/${row.id}`)">查看详情</el-button>
                <el-button v-if="isAdmin && row.status === 'terminated'" text type="danger" size="small" @click.stop="handlePermanentDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <div v-if="!instanceLoading && instances.length === 0" style="padding:40px 0;text-align:center">
            <span style="color:var(--el-text-color-secondary);font-size:14px">暂无项目</span>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="list-pagination" v-if="instanceTotal > instancePageSize">
        <el-pagination
          v-model:current-page="instancePage"
          :page-size="instancePageSize"
          :total="instanceTotal"
          layout="prev, pager, next"
          @current-change="fetchInstances"
        />
      </div>
    </template>

    <!-- ========== 项目模板 Tab ========== -->
    <template v-if="activeTab === 'template'">
      <TemplateTable
        :items="templates"
        :loading="tplLoading"
        :total="tplTotal"
        :can-manage="isOrgManager"
        @search="handleTplSearch"
        @create="handleCreate"
        @detail="(id: number) => router.push(`/flows/detail/${id}`)"
        @edit="handleEdit"
        @design="(id: number) => router.push(`/flows/designer/${id}`)"
        @delete="handleDelete"
        @page-change="handleTplPageChange"
      />
    </template>

    <!-- ========== 新建/编辑模板弹窗 ========== -->
    <el-dialog
      v-model="formVisible"
      :title="editingTpl ? '编辑模板' : '新建模板'"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="模板名称" prop="name">
          <el-input v-model="form.name" maxlength="50" placeholder="请输入模板名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/** 所内主页 —— 实例列表 + 模板管理（PRD P04，参考 pages/P04_org_home.html） */
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  getTemplateOrganizations,
  getTemplates,
  updateTemplate,
  deleteTemplate,
  type OrgCardItem,
  type TemplateItem,
} from '@/api/template'
import { getInstances, permanentDeleteInstance, type InstanceListItem } from '@/api/instance'
import { getProposals } from '@/api/proposal'
import { useUserStore } from '@/stores/user'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import { formatTime } from '@/utils/format'
import { priLabel, instStatusClass, instStatusLabel } from '@/utils/labels'
import TemplateTable from './components/TemplateTable.vue'

const { setBreadcrumb } = useBreadcrumb()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isAdmin = computed(() => userStore.isAdmin)
const isManager = computed(() => userStore.isManager)
/** 当前用户是否为本所所长（仅本所 manager 可管理模板和发起流程） */
const isOrgManager = computed(() => {
  if (!isManager.value) return false
  const orgId = Number(route.params.orgId)
  return userStore.userInfo?.organization_id === orgId
})
/** 当前 Tab，与 URL query 同步（route.query.tab） */
const activeTab = ref((route.query.tab as string) || 'instance')

// 浏览器前进/后退时同步 Tab
watch(() => route.query.tab, (tab) => {
  if (tab === 'instance' || tab === 'template') activeTab.value = tab
})

// ========== 发起项目：模板选择 + 业务信息弹窗 ==========
const showTemplatePicker = ref(false)
const pickerLoading = ref(false)
const tplKeyword = ref('')
const templateList = ref<TemplateItem[]>([])
const selectedTplId = ref<number | null>(null)  // 当前选中的模板 ID

/** 业务信息表单 */
const pickerForm = reactive({
  contract_no: '',
  product_model: '',
  sales_manager: '',
  proposal_id: null as number | null,
})

/** 当前组织下已完成的方案（供项目发起时选择关联） */
const completedProposals = ref<{ id: number; name: string }[]>([])

/** 确认按钮是否可用：模板已选 + 三个必填字段已填写 */
const pickerCanConfirm = computed(() =>
  selectedTplId.value !== null &&
  pickerForm.contract_no.trim() !== '' &&
  pickerForm.product_model.trim() !== '' &&
  pickerForm.sales_manager.trim() !== ''
)

watch(showTemplatePicker, (val) => { if (val) { fetchTemplateList(); resetPickerForm() } })

/** 重置弹窗表单 */
function resetPickerForm() {
  selectedTplId.value = null
  pickerForm.contract_no = ''
  pickerForm.product_model = ''
  pickerForm.sales_manager = ''
  pickerForm.proposal_id = null
}

/** 加载模板列表（限定当前所）+ 已完成的方案 */
async function fetchTemplateList() {
  pickerLoading.value = true
  try {
    const res = await getTemplates({ page_size: 100, keyword: tplKeyword.value || undefined, organization_id: orgId.value })
    templateList.value = res.items
  } catch { /* ignore */ }
  finally { pickerLoading.value = false }

  // 加载该组织下已完成的方案
  try {
    const data = await getProposals({ organization_id: orgId.value, status: 'completed', page_size: 100 })
    completedProposals.value = (data.items || []).map(p => ({ id: p.id, name: p.name }))
  } catch {
    completedProposals.value = []
  }
}

/** 点击模板行 → 选中模板，下方显示业务信息表单 */
function handleSelectTemplate(row: TemplateItem) {
  selectedTplId.value = row.id
}

/** 确认发起 → 携带业务信息参数跳设计器 */
function handleConfirmLaunch() {
  if (!pickerCanConfirm.value || !selectedTplId.value) return
  showTemplatePicker.value = false
  const params = new URLSearchParams({
    mode: 'launch',
    contract_no: pickerForm.contract_no.trim(),
    product_model: pickerForm.product_model.trim(),
    sales_manager: pickerForm.sales_manager.trim(),
  })
  if (pickerForm.proposal_id) params.set('proposal_id', String(pickerForm.proposal_id))
  router.push(`/flows/designer/${selectedTplId.value}?${params.toString()}`)
}

// ========== 组织信息 ==========
const orgId = computed(() => Number(route.params.orgId))
const orgName = ref('')
const orgInfo = ref<OrgCardItem | null>(null)

// ========== 实例列表 ==========
const instanceLoading = ref(false)
const instances = ref<InstanceListItem[]>([])
const instanceTotal = ref(0)
const instancePage = ref(1)
const instancePageSize = ref(20)
const instanceStatusFilter = ref('all')
const instanceKeyword = ref('')
/** 各状态实例数量 */
const statusCounts = ref<Record<string, number>>({})

const instanceFilters = [
  { label: '全部', value: 'all' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已终止', value: 'terminated' },
]

// ========== 模板列表 ==========
const templates = ref<TemplateItem[]>([])
const tplLoading = ref(false)
const tplTotal = ref(0)
const tplPage = ref(1)
const tplSearch = reactive({ keyword: '' })

// ========== 模板表单 ==========
const formVisible = ref(false)
const saving = ref(false)
const editingTpl = ref<TemplateItem | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ name: '', description: '' as string | null })
const rules: FormRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
}

// ========== 初始化 ==========
onMounted(async () => {
  await fetchOrgInfo()
  await Promise.all([fetchInstances(), fetchStatusCounts()])
})

onUnmounted(() => {
  if (instanceSearchTimer) clearTimeout(instanceSearchTimer)
})

watch(activeTab, (tab) => {
  // 同步 Tab 到 URL，方便面包屑/浏览器返回保持状态
  if (route.query.tab !== tab) {
    router.replace({ query: { ...route.query, tab: tab !== 'instance' ? tab : undefined } })
  }
  if (tab === 'template') fetchTemplates()
  else if (tab === 'instance') fetchInstances()
}, { immediate: true })

/** 从组织列表中获取当前所信息 */
async function fetchOrgInfo() {
  try {
    const data = await getTemplateOrganizations()
    const org = data.organizations.find(o => o.id === orgId.value)
    if (org) {
      orgInfo.value = org
      orgName.value = org.name
    } else {
      orgName.value = '未知组织'
    }
  } catch {
    orgName.value = '加载失败'
  }
  // 面包屑：首页 > 项目管理 > 当前所
  setBreadcrumb([
    { label: '首页', to: '/dashboard' },
    { label: '项目管理', to: '/flows' },
    { label: orgName.value },
  ])
}

/** 获取该所各状态的实例总数 */
async function fetchStatusCounts() {
  try {
    const results = await Promise.all([
      getInstances({ page_size: 1, organization_id: orgId.value }),
      getInstances({ page_size: 1, organization_id: orgId.value, status: 'running' }),
      getInstances({ page_size: 1, organization_id: orgId.value, status: 'completed' }),
      getInstances({ page_size: 1, organization_id: orgId.value, status: 'terminated' }),
    ])
    statusCounts.value = {
      all: results[0].total,
      running: results[1].total,
      completed: results[2].total,
      terminated: results[3].total,
    }
  } catch { /* ignore */ }
}

// ========== 实例相关 ==========
async function fetchInstances() {
  instanceLoading.value = true
  try {
    const data = await getInstances({
      page: instancePage.value,
      page_size: instancePageSize.value,
      status: instanceStatusFilter.value === 'all' ? undefined : instanceStatusFilter.value,
      keyword: instanceKeyword.value || undefined,
      organization_id: orgId.value,
      sort_by: instanceStatusFilter.value === 'running' ? 'priority' : undefined,
    })
    instances.value = data.items
    instanceTotal.value = data.total
  } catch { /* 拦截器统一处理 */ }
  finally { instanceLoading.value = false }
}

/** 实例表格行高亮：运行中 urgent/high 加背景色 */
function instanceRowClass({ row }: { row: InstanceListItem }) {
  if (row.status !== 'running') return ''
  if (row.priority === 'urgent') return 'row--priority-urgent'
  if (row.priority === 'high') return 'row--priority-high'
  return ''
}

function handleInstanceFilter(status: string) {
  instanceStatusFilter.value = status
  instancePage.value = 1
  fetchInstances()
}

/** 管理员永久删除已终止实例 */
async function handlePermanentDelete(row: InstanceListItem) {
  try {
    await ElMessageBox.confirm(`确认永久删除实例「${row.name}」？此操作不可撤销，所有关联数据将被清除。`, '永久删除', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
  } catch { return }
  try {
    await permanentDeleteInstance(row.id)
    ElMessage.success('项目已永久删除')
    fetchInstances()
    fetchStatusCounts()
  } catch (e: any) { ElMessage.error(e?.response?.data?.message || '删除失败') }
}

let instanceSearchTimer: ReturnType<typeof setTimeout> | null = null
function handleInstanceSearch() {
  if (instanceSearchTimer) clearTimeout(instanceSearchTimer)
  instanceSearchTimer = setTimeout(() => {
    instancePage.value = 1
    fetchInstances()
  }, 300)
}

// ========== 模板相关 ==========
async function fetchTemplates() {
  tplLoading.value = true
  try {
    const data = await getTemplates({
      page: tplPage.value,
      organization_id: orgId.value,
      keyword: tplSearch.keyword || undefined,
    })
    templates.value = data.items
    tplTotal.value = data.total
  } finally { tplLoading.value = false }
}

function handleTplSearch(params: { keyword: string }) {
  tplSearch.keyword = params.keyword
  tplPage.value = 1
  fetchTemplates()
}

function handleTplPageChange(page: number) {
  tplPage.value = page
  fetchTemplates()
}

function handleCreate() {
  editingTpl.value = null
  form.name = ''
  form.description = ''
  formVisible.value = true
}

function handleEdit(row: TemplateItem) {
  editingTpl.value = row
  form.name = row.name
  form.description = row.description
  formVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (editingTpl.value) {
      await updateTemplate(editingTpl.value.id, { name: form.name, description: form.description })
      ElMessage.success('模板信息已更新')
      formVisible.value = false
      fetchTemplates()
    } else {
      // 新建模板：不在此时入库，直接跳设计器；设计器首次保存时才真正创建模板
      formVisible.value = false
      const params = new URLSearchParams({ new: '1', name: form.name, org_id: String(orgId.value) })
      if (form.description) params.set('desc', form.description)
      router.push(`/flows/designer/0?${params.toString()}`)
    }
  } finally { saving.value = false }
}

async function handleDelete(id: number) {
  await deleteTemplate(id)
  ElMessage.success('模板已删除')
  fetchTemplates()
}

// 时间/状态标签 —— 统一从 @/utils 导入
</script>

<style lang="scss" scoped>
.org-home {
  /* 隐藏 Element Plus 表格排序箭头 + cell 伪元素残留 */
  :deep(.caret-wrapper) { display: none; }
  :deep(.el-table__header) .el-icon { display: none !important; }
  :deep(.el-table .cell)::before,
  :deep(.el-table .cell)::after { display: none !important; content: none !important; }
}

.org-tabs {
  margin-top: 4px;
  margin-bottom: 16px;
}

// 筛选标签
.filter-tabs {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 16px; flex-wrap: wrap;
}

.filter-tab {
  height: 32px; padding: 0 16px;
  border: 1px solid var(--el-border-color); background: #fff;
  border-radius: 6px; font-size: 13px; color: var(--el-text-color-regular);
  cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
  line-height: 1; transition: all 0.2s;

  &:hover { border-color: var(--el-color-primary); color: var(--el-color-primary); }
  &.is-active { background: var(--el-color-primary); border-color: var(--el-color-primary); color: #fff; }
}

.filter-label { display: inline-block; min-width: 3em; }
.filter-count { opacity: 0.7; }

// 实例表格
.inst-name { font-weight: 500; color: var(--el-text-color-primary); }
.inst-meta { font-size: 13px; color: var(--el-text-color-secondary); }

/* 进度条（与首页卡点追踪一致） */
.bt-progress {
  display: flex; align-items: center; gap: 8px; padding: 4px 8px;
  :deep(.el-progress) { flex: 1; min-width: 60px; }
  :deep(.el-progress-bar__outer) { border-radius: 4px; }
}
.bt-progress__text { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; flex-shrink: 0; }

.pri-badge {
  font-size: 12px; font-weight: 500; padding: 1px 8px; border-radius: 10px;
  &.pri--urgent { color: #fff; background: var(--el-color-danger); }
  &.pri--high   { color: #fff; background: var(--el-color-warning); }
  &.pri--normal { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.pri--low    { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}

/* 难度等级 badge */
.diff-badge {
  font-size: 12px; font-weight: 500; padding: 1px 8px; border-radius: 10px;
  &.diff--1 { color: #1e8449; background: #eafaf1; }
  &.diff--2 { color: #2471a3; background: #eaf2f8; }
  &.diff--3 { color: #b87333; background: #fef5e7; }
  &.diff--4 { color: #fff; background: var(--el-color-danger); }
}

.list-pagination {
  display: flex; justify-content: center; margin-top: 16px;
}
</style>

<style lang="scss">
/* 发起项目弹窗：选中模板行高亮（非 scoped 才能覆盖 el-table 行样式） */
.is-selected-row td { background: var(--el-color-primary-light-9) !important; }

/* 优先级行高亮（仅运行中实例） */
.row--priority-urgent td { background: #fde8e8 !important; }
.row--priority-high td { background: #fef3e2 !important; }
</style>
