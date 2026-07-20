<template>
  <!-- 所内方案主页 -->
  <div class="org-proposal-home">
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">{{ orgName }}</h1>
        <p class="page-header__subtitle" v-if="orgInfo">
          方案 {{ orgInfo.proposal_count ?? 0 }} 个 · 运行中 {{ orgInfo.running_count ?? 0 }} 个
        </p>
      </div>
      <div class="page-header__actions" v-if="isManager">
        <el-button type="primary" @click="showCreateDialog = true">发起方案</el-button>
      </div>
    </div>

    <!-- 状态筛选 -->
    <div class="filter-tabs">
      <button
        v-for="f in statusFilters" :key="f.value"
        class="filter-tab" :class="{ 'is-active': statusFilter === f.value }"
        @click="handleStatusFilter(f.value)"
      >
        <span class="filter-label">{{ f.label }}</span>
        <span class="filter-count">{{ statusCounts[f.value] ?? '—' }}</span>
      </button>
      <el-input
        v-model="keyword" placeholder="搜索方案名称" clearable
        :prefix-icon="Search" size="default" style="width: 220px; margin-left: auto"
        @input="handleSearch"
      />
    </div>

    <!-- 方案列表 -->
    <div class="card">
      <div class="card__body" style="padding:0">
        <el-table :data="proposals" stripe v-loading="loading" @row-click="handleRowClick" style="cursor:pointer">
          <el-table-column prop="name" label="方案名称" min-width="160">
            <template #default="{ row }"><span class="inst-name">{{ row.name }}</span></template>
          </el-table-column>
          <el-table-column prop="initiator_name" label="发起人" min-width="80" />
          <el-table-column prop="description" label="说明" min-width="140" show-overflow-tooltip />
          <el-table-column prop="created_at" label="发起时间" min-width="140">
            <template #default="{ row }"><span class="num">{{ fmtTime(row.created_at) }}</span></template>
          </el-table-column>
          <el-table-column label="状态" min-width="80" align="center">
            <template #default="{ row }">
              <span class="status-tag" :class="statusClass(row.status)">{{ statusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="80" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="goDetail(row.id)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="!loading && proposals.length === 0" style="padding:40px 0;text-align:center">
          <span style="color:var(--el-text-color-secondary);font-size:14px">暂无方案</span>
        </div>
      </div>
    </div>

    <div class="list-pagination" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="page" :page-size="pageSize"
        :total="total" layout="prev, pager, next"
        @current-change="fetchList"
      />
    </div>

    <!-- 发起方案弹窗（预先填充当前组织） -->
    <el-dialog v-model="showCreateDialog" title="发起方案" width="520px" :close-on-click-modal="false" @closed="resetForm" @open="loadFormUsers">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="方案名称" prop="name">
          <el-input v-model="form.name" placeholder="输入方案名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="说明" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" maxlength="500" placeholder="可选" />
        </el-form-item>
        <el-form-item label="设计人" prop="designerId">
          <el-select v-model="form.designerId" placeholder="选择设计人" style="width:100%">
            <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="审批人" prop="approverIds">
          <el-select v-model="form.approverIds" multiple placeholder="选择审批人" style="width:100%">
            <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期" prop="deadline">
          <el-date-picker v-model="form.deadline" type="date" placeholder="选择截止日期" style="width:100%" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">确认发起</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/** 所内方案主页 —— 该所方案列表 + 发起方案 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { getProposals, createProposal, type ProposalListItem } from '@/api/proposal'
import { getOrgOptions, searchUsers } from '@/api/admin'
import { useBreadcrumb } from '@/composables/useBreadcrumb'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { setBreadcrumb } = useBreadcrumb()

const orgId = computed(() => Number(route.params.orgId))
const orgName = ref('')
const orgInfo = ref<{ proposal_count: number; running_count: number } | null>(null)

const isManager = computed(() => userStore.userInfo?.roles.includes('manager') ?? false)

const loading = ref(false)
const proposals = ref<ProposalListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('all')
const keyword = ref('')
const statusCounts = ref<Record<string, number>>({})

const statusFilters = [
  { label: '全部', value: 'all' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '已终止', value: 'terminated' },
]

// ========== 发起弹窗 ==========
const showCreateDialog = ref(false)
const creating = ref(false)
const formRef = ref<FormInstance>()
const form = ref({
  name: '', description: '',
  designerId: null as number | null,
  approverIds: [] as number[],
  deadline: null as string | null,
})
const users = ref<{ id: number; real_name: string }[]>([])

const rules: FormRules = {
  name: [{ required: true, message: '请输入方案名称', trigger: 'blur' }],
  designerId: [{ required: true, message: '请选择设计人', trigger: 'change' }],
  approverIds: [{ required: true, message: '请选择审批人', trigger: 'change' }],
}

onMounted(async () => {
  await loadOrgName()
  setBreadcrumb([{ label: '首页', to: '/dashboard' }, { label: '方案管理', to: '/proposals' }, { label: orgName.value }])
  await Promise.all([fetchList(), fetchStatusCounts()])
})

async function loadOrgName() {
  try {
    const orgs = await getOrgOptions()
    const org = orgs.find(o => o.id === orgId.value)
    if (org) orgName.value = org.name
  } catch { orgName.value = `组织 #${orgId.value}` }
}

async function fetchStatusCounts() {
  try {
    const results = await Promise.all([
      getProposals({ page_size: 1, organization_id: orgId.value }),
      getProposals({ page_size: 1, organization_id: orgId.value, status: 'running' }),
      getProposals({ page_size: 1, organization_id: orgId.value, status: 'completed' }),
      getProposals({ page_size: 1, organization_id: orgId.value, status: 'terminated' }),
    ])
    statusCounts.value = {
      all: results[0].total,
      running: results[1].total,
      completed: results[2].total,
      terminated: results[3].total,
    }
    orgInfo.value = { proposal_count: results[0].total, running_count: results[1].total }
  } catch { /* ignore */ }
}

async function fetchList() {
  loading.value = true
  try {
    const data = await getProposals({
      keyword: keyword.value || undefined,
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      organization_id: orgId.value,
      page: page.value,
      page_size: pageSize.value,
    })
    proposals.value = data?.items || []
    total.value = data?.total || 0
  } catch {
    proposals.value = []
    total.value = 0
  } finally { loading.value = false }
}

function handleStatusFilter(status: string) { statusFilter.value = status; page.value = 1; fetchList() }
let searchTimer: ReturnType<typeof setTimeout> | null = null
function handleSearch() { if (searchTimer) clearTimeout(searchTimer); searchTimer = setTimeout(() => { page.value = 1; fetchList() }, 300) }
function handleRowClick(row: ProposalListItem) { goDetail(row.id) }
function goDetail(id: number) { router.push(`/flows/instances/${id}`) }

async function loadFormUsers() { try { users.value = await searchUsers() } catch { /* ignore */ } }

async function handleCreate() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  creating.value = true
  try {
    const result = await createProposal({
      name: form.value.name,
      description: form.value.description || null,
      organization_id: orgId.value,
      designer_id: form.value.designerId!,
      approvers: form.value.approverIds.map(id => ({ user_id: id })),
      deadline: form.value.deadline || null,
    })
    ElMessage.success('方案已发起')
    showCreateDialog.value = false
    router.push(`/flows/instances/${result.id}`)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '发起失败')
  } finally { creating.value = false }
}

function resetForm() {
  form.value = { name: '', description: '', designerId: null, approverIds: [], deadline: null }
  formRef.value?.resetFields()
}

function fmtTime(val: string | null): string { if (!val) return '-'; return val.replace('T', ' ').substring(0, 16) }
function statusClass(s: string): string { const m: Record<string, string> = { running: 'status-tag--running', completed: 'status-tag--completed', terminated: 'status-tag--terminated' }; return m[s] || '' }
function statusLabel(s: string): string { const m: Record<string, string> = { running: '运行中', completed: '已完成', terminated: '已终止' }; return m[s] || s }
</script>

<style lang="scss" scoped>
.org-proposal-home { /* max-width 由 AppLayout 内容区统一控制 */ }
.filter-tabs { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-tab { height: 32px; padding: 0 16px; border: 1px solid var(--el-border-color); background: #fff; border-radius: 6px; font-size: 13px; color: var(--el-text-color-regular); cursor: pointer; display: inline-flex; align-items: center; gap: 6px; line-height: 1; transition: all 0.2s; &:hover { border-color: var(--el-color-primary); color: var(--el-color-primary); } &.is-active { background: var(--el-color-primary); border-color: var(--el-color-primary); color: #fff; } }
.filter-label { display: inline-block; min-width: 3em; }
.filter-count { opacity: 0.7; }
.inst-name { font-weight: 500; color: var(--el-text-color-primary); }
.list-pagination { display: flex; justify-content: center; margin-top: 16px; }
.num { font-variant-numeric: tabular-nums; }
</style>
