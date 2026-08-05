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
      <el-table border
        :data="templateList" v-loading="pickerLoading"
        @row-click="handleSelectTemplate" style="cursor:pointer" max-height="280"
        :row-class-name="({ row }: any) => row.id === selectedTplId ? 'is-selected-row' : ''"
      >
        <el-table-column prop="name" label="模板名称" min-width="160" />
        <el-table-column prop="node_count" label="节点数" width="80" />
        <el-table-column prop="instance_count" label="运行项目" width="100" />
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
      <!-- 实例表格（P2-2 共享组件：筛选/搜索/分页/删除，fetch 权留在本页） -->
      <InstanceTable
        ref="instanceTableRef"
        v-model:status-filter="instanceStatusFilter"
        v-model:page="instancePage"
        v-model:page-size="instancePageSize"
        :items="instances"
        :loading="instanceLoading"
        :total="instanceTotal"
        :counts="statusCounts"
        @refresh="fetchInstances"
        @refresh-counts="fetchStatusCounts"
        @row-click="handleRowClick"
      />
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
        @detail="(id: number) => router.push({ name: 'TemplateDetail', params: { id } })"
        @edit="handleEdit"
        @design="(id: number) => router.push({ name: 'FlowDesigner', params: { id } })"
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
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  getTemplateOrganizations,
  getTemplates,
  updateTemplate,
  deleteTemplate,
  checkTemplateName,
  type OrgCardItem,
  type TemplateItem,
} from '@/api/template'
import { getInstances, type InstanceListItem } from '@/api/instance'
import { getProposals } from '@/api/proposal'
import { useUserStore } from '@/stores/user'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import { formatTime } from '@/utils/format'
import TemplateTable from './components/TemplateTable.vue'
import InstanceTable, { type InstanceQuery } from './components/InstanceTable.vue'

const { setBreadcrumb } = useBreadcrumb()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

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
  router.push({ name: 'FlowDesigner', params: { id: selectedTplId.value }, query: Object.fromEntries(params) })
}

// ========== 组织信息 ==========
const orgId = computed(() => Number(route.params.orgId))
const orgName = ref('')
const orgInfo = ref<OrgCardItem | null>(null)

// ========== 实例列表 ==========
// 数据与分页/状态筛选由本页持有（组件内 keyword/高级搜索等状态经 resetFilters 重置）
const instanceLoading = ref(false)
const instances = ref<InstanceListItem[]>([])
const instanceTotal = ref(0)
const instancePage = ref(1)
const instancePageSize = ref(20)
const instanceStatusFilter = ref('all')
/** 各状态实例数量 */
const statusCounts = ref<Record<string, number>>({})
/** 实例表格组件引用（组织切换时重置筛选） */
const instanceTableRef = ref<InstanceType<typeof InstanceTable> | null>(null)

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

watch(activeTab, (tab) => {
  // 同步 Tab 到 URL，方便面包屑/浏览器返回保持状态
  if (route.query.tab !== tab) {
    router.replace({ query: { ...route.query, tab: tab !== 'instance' ? tab : undefined } })
  }
  if (tab === 'template') fetchTemplates()
  else if (tab === 'instance') fetchInstances()
}, { immediate: true })

// P1-41：跨组织切换（route.params.orgId 变化，组件复用、onMounted 不重跑）→ 重置筛选并重新加载
watch(() => route.params.orgId, () => {
  // 切换组织后呈现干净列表：重置分页与筛选，避免带入上一组织的筛选条件/深页码
  instancePage.value = 1
  instanceStatusFilter.value = 'all'
  instanceTableRef.value?.resetFilters()
  tplPage.value = 1
  tplSearch.keyword = ''
  orgName.value = ''
  fetchOrgInfo()
  fetchStatusCounts()
  if (activeTab.value === 'template') fetchTemplates()
  else fetchInstances()
})

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
/** 查询参数（keyword/日期/优先级/发起人）由 InstanceTable 组件经 refresh 事件上抛 */
async function fetchInstances(query?: InstanceQuery) {
  instanceLoading.value = true
  try {
    const data = await getInstances({
      page: instancePage.value,
      page_size: instancePageSize.value,
      status: instanceStatusFilter.value === 'all' ? undefined : instanceStatusFilter.value,
      keyword: query?.keyword,
      organization_id: orgId.value,
      sort_by: instanceStatusFilter.value === 'running' ? 'priority' : undefined,
      priority: query?.priority,
      date_from: query?.date_from,
      date_to: query?.date_to,
      initiator_id: query?.initiator_id ?? undefined,
    })
    instances.value = data.items
    instanceTotal.value = data.total
  } catch { /* 拦截器统一处理 */ }
  finally { instanceLoading.value = false }
}

/** 行点击 → 跳转实例详情 */
function handleRowClick(row: InstanceListItem) {
  router.push({ name: 'InstanceDetail', params: { id: row.id } })
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
      // 新建模板：先检查同组织下是否重名，再跳设计器
      const available = await checkTemplateName(orgId.value, form.name.trim())
      if (!available) {
        ElMessage.error('该组织下已存在同名模板，请更换名称')
        return
      }
      formVisible.value = false
      const params = new URLSearchParams({ new: '1', name: form.name.trim(), org_id: String(orgId.value) })
      if (form.description) params.set('desc', form.description)
      router.push({ name: 'FlowDesigner', params: { id: '0' }, query: Object.fromEntries(params) })
    }
  } finally { saving.value = false }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('删除模板将同时删除模板设计数据，确定删除？', '删除确认', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
    })
  } catch { return }
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

</style>

<style lang="scss">
/* 发起项目弹窗：选中模板行高亮（非 scoped 才能覆盖 el-table 行样式） */
.is-selected-row td { background: var(--el-color-primary-light-9) !important; }
</style>
