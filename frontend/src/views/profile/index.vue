<template>
  <!-- 个人中心 —— 顶层项目/方案切换 + 各 Tab 分区 -->
  <div class="profile-page">
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">个人中心</h1>
      </div>
    </div>

    <!-- 用户信息卡片 -->
    <div class="user-info-card" v-if="userStore.userInfo">
      <div class="user-info-card__avatar">{{ avatarInitial }}</div>
      <div class="user-info-card__body">
        <div class="user-info-card__name">{{ userStore.userInfo.real_name }}</div>
        <div class="user-info-card__meta">
          {{ userStore.userInfo.username }} · {{ userStore.userInfo.organization_name || '未分配组织' }}
          <el-tag v-for="r in userStore.userInfo.roles" :key="r" size="small" style="margin-left:6px">{{ roleLabel(r) }}</el-tag>
        </div>
      </div>
    </div>

    <!-- 顶层：项目 / 方案 切换 -->
    <div class="view-type-bar">
      <el-radio-group v-model="viewType" size="default" @change="handleViewTypeChange">
        <el-radio-button value="project">
          项目<i class="view-dot" v-if="notifyStore.projectPending > 0"></i>
        </el-radio-button>
        <el-radio-button value="proposal">
          方案<i class="view-dot" v-if="notifyStore.proposalPending > 0"></i>
        </el-radio-button>
      </el-radio-group>
    </div>

    <!-- ==================== 项目视图 ==================== -->
    <template v-if="viewType === 'project'">
      <el-tabs v-model="activeTab" class="profile-tabs">
        <el-tab-pane name="tasks">
          <template #label>
            <span>我的待办<span class="tab-badge" v-if="taskCount > 0">{{ taskCount }}</span></span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="checks">
          <template #label>
            <span>我的校验<span class="tab-badge" v-if="checkCount > 0">{{ checkCount }}</span></span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="approvals">
          <template #label>
            <span>我的审批<span class="tab-badge" v-if="approvalCount > 0">{{ approvalCount }}</span></span>
          </template>
        </el-tab-pane>
        <el-tab-pane v-if="isManager" name="initiated">
          <template #label><span>我发起的流程</span></template>
        </el-tab-pane>
      </el-tabs>

      <!-- 待办列表 -->
      <template v-if="activeTab === 'tasks'">
        <div class="list-toolbar">
          <el-input v-model="taskKeyword" placeholder="搜索项目名称" clearable style="width:220px" @change="fetchTasks" />
          <el-select v-model="taskStatus" placeholder="状态" clearable style="width:140px" @change="fetchTasks">
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="processing" />
          </el-select>
        </div>
        <el-table :data="tasks" stripe v-loading="taskLoading" @row-click="(row: any) => router.push(`/profile/task/${row.id}`)" style="cursor:pointer">
          <el-table-column prop="instance_name" label="项目" min-width="140" />
          <el-table-column prop="node_name" label="当前节点" min-width="100" />
          <el-table-column prop="initiator_name" label="发起人" min-width="72" />
          <el-table-column label="截止时间" min-width="140">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.is_overdue }">{{ formatTime(row.deadline) }}</span>
              <el-tag v-if="row.is_overdue" type="danger" size="small" style="margin-left:6px">已逾期</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="优先级" min-width="64" align="center">
            <template #default="{ row }">
              <span class="pri-tag" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="64" align="center">
            <template #default="{ row }">
              <span class="status-tag" :class="taskStatusClass(row.status)">{{ taskStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push(`/profile/task/${row.id}`)">处理</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!taskLoading && tasks.length === 0" description="暂无待办任务" :image-size="50" />
      </template>

      <!-- 校验列表 -->
      <template v-if="activeTab === 'checks'">
        <div class="list-toolbar">
          <el-input v-model="checkKeyword" placeholder="搜索项目名称" clearable style="width:220px" @change="fetchChecks" />
        </div>
        <el-table :data="checks" stripe v-loading="checkLoading" @row-click="(row: any) => router.push(`/profile/check/${row.id}`)" style="cursor:pointer">
          <el-table-column prop="instance_name" label="项目" min-width="140" />
          <el-table-column prop="node_name" label="节点" min-width="100" />
          <el-table-column prop="submitter_name" label="提交人" min-width="72" />
          <el-table-column prop="created_at" label="提交时间" min-width="140" :formatter="(r: any) => formatTime(r.created_at)" />
          <el-table-column label="轮次" min-width="48" align="center">
            <template #default="{ row }"><span v-if="row.round > 1" class="round-tag">#{{ row.round }}</span></template>
          </el-table-column>
          <el-table-column label="状态" min-width="64" align="center">
            <template #default="{ row }">
              <span class="status-tag" :class="checkStatusClass(row.status)">{{ checkStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push(`/profile/check/${row.id}`)">校验</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!checkLoading && checks.length === 0" description="暂无待校验" :image-size="50" />
      </template>

      <!-- 审批列表 -->
      <template v-if="activeTab === 'approvals'">
        <div class="list-toolbar">
          <el-input v-model="approvalKeyword" placeholder="搜索项目名称" clearable style="width:220px" @change="fetchApprovals" />
        </div>
        <el-table :data="approvals" stripe v-loading="approvalLoading" @row-click="(row: any) => router.push(`/profile/approval/${row.id}`)" style="cursor:pointer">
          <el-table-column prop="instance_name" label="项目" min-width="140" />
          <el-table-column prop="node_name" label="节点" min-width="100">
            <template #default="{ row }">
              {{ row.node_name }}<el-tag v-if="row.is_end_node" size="small" type="warning" effect="plain">终审</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" min-width="140" :formatter="(r: any) => formatTime(r.created_at)" />
          <el-table-column label="轮次" min-width="48" align="center">
            <template #default="{ row }"><span v-if="row.round > 1" class="round-tag">#{{ row.round }}</span></template>
          </el-table-column>
          <el-table-column label="状态" min-width="64" align="center">
            <template #default="{ row }">
              <span class="status-tag" :class="approvalStatusClass(row.status)">{{ approvalStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push(`/profile/approval/${row.id}`)">审批</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!approvalLoading && approvals.length === 0" description="暂无待审批" :image-size="50" />
      </template>

      <!-- 我发起的流程 -->
      <template v-if="activeTab === 'initiated'">
        <el-table :data="initiatedList" stripe v-loading="initiatedLoading" @row-click="(row: any) => router.push(`/flows/instances/${row.id}`)" style="cursor:pointer">
          <el-table-column prop="name" label="项目" min-width="140" />
          <el-table-column label="优先级" min-width="64" align="center">
            <template #default="{ row }"><span class="pri-tag" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span></template>
          </el-table-column>
          <el-table-column label="发起时间" min-width="140">
            <template #default="{ row }">{{ formatTime(row.initiated_at || row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="状态" min-width="64" align="center">
            <template #default="{ row }"><span class="status-tag" :class="instStatusClass(row.status)">{{ instStatusLabel(row.status) }}</span></template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push(`/flows/instances/${row.id}`)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!initiatedLoading && initiatedList.length === 0" description="暂无发起的流程" :image-size="50" />
      </template>
    </template>

    <!-- ==================== 方案视图 ==================== -->
    <template v-if="viewType === 'proposal'">
      <el-tabs v-model="propActiveTab" class="profile-tabs">
        <el-tab-pane name="design">
          <template #label>
            <span>方案设计<span class="tab-badge" v-if="propTaskCount > 0">{{ propTaskCount }}</span></span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="approve">
          <template #label>
            <span>方案审批<span class="tab-badge" v-if="propApprovalCount > 0">{{ propApprovalCount }}</span></span>
          </template>
        </el-tab-pane>
        <el-tab-pane v-if="isManager" name="initiated">
          <template #label><span>我发起的方案</span></template>
        </el-tab-pane>
      </el-tabs>

      <!-- 方案设计（设计人的待办任务） -->
      <template v-if="propActiveTab === 'design'">
        <el-table :data="propTasks" stripe v-loading="propTaskLoading" @row-click="(row: any) => router.push(`/profile/task/${row.id}`)" style="cursor:pointer">
          <el-table-column prop="instance_name" label="方案名称" min-width="160" />
          <el-table-column prop="initiator_name" label="发起人" min-width="72" />
          <el-table-column label="截止时间" min-width="140">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.is_overdue }">{{ formatTime(row.deadline) }}</span>
              <el-tag v-if="row.is_overdue" type="danger" size="small" style="margin-left:6px">已逾期</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="64" align="center">
            <template #default="{ row }">
              <span class="status-tag" :class="taskStatusClass(row.status)">{{ taskStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push(`/profile/task/${row.id}`)">设计</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!propTaskLoading && propTasks.length === 0" description="暂无方案设计任务" :image-size="50" />
      </template>

      <!-- 方案审批 -->
      <template v-if="propActiveTab === 'approve'">
        <el-table :data="propApprovals" stripe v-loading="propApprovalLoading" @row-click="(row: any) => router.push(`/profile/approval/${row.id}`)" style="cursor:pointer">
          <el-table-column prop="instance_name" label="方案名称" min-width="160" />
          <el-table-column prop="created_at" label="创建时间" min-width="140" :formatter="(r: any) => formatTime(r.created_at)" />
          <el-table-column label="状态" min-width="64" align="center">
            <template #default="{ row }">
              <span class="status-tag" :class="approvalStatusClass(row.status)">{{ approvalStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push(`/profile/approval/${row.id}`)">审批</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!propApprovalLoading && propApprovals.length === 0" description="暂无待审批方案" :image-size="50" />
      </template>

      <!-- 我发起的方案 -->
      <template v-if="propActiveTab === 'initiated'">
        <el-table :data="propInitiatedList" stripe v-loading="propInitiatedLoading" @row-click="(row: any) => router.push(`/proposals/instances/${row.id}`)" style="cursor:pointer">
          <el-table-column prop="name" label="方案名称" min-width="140" />
          <el-table-column label="发起时间" min-width="140">
            <template #default="{ row }">{{ formatTime(row.initiated_at || row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="状态" min-width="64" align="center">
            <template #default="{ row }"><span class="status-tag" :class="instStatusClass(row.status)">{{ instStatusLabel(row.status) }}</span></template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push(`/proposals/instances/${row.id}`)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!propInitiatedLoading && propInitiatedList.length === 0" description="暂无发起的方案" :image-size="50" />
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
/** 个人中心 —— 项目/方案 顶层切换 + Tab 分区 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'
import { getTasks, type TaskListItem } from '@/api/task'
import { getChecks, type CheckListItem } from '@/api/check'
import { getApprovals, type ApprovalListItem } from '@/api/approval'
import { getMyInitiated, type MyInitiatedItem } from '@/api/instance'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import { formatTime } from '@/utils/format'
import { priLabel, roleLabel, instStatusClass, instStatusLabel, taskStatusClass, taskStatusLabel, checkStatusClass, checkStatusLabel, approvalStatusClass, approvalStatusLabel } from '@/utils/labels'

const { setBreadcrumb } = useBreadcrumb()
const router = useRouter()
const userStore = useUserStore()
const notifyStore = useNotificationStore()

const isManager = computed(() => userStore.isManager)

/** 顶层视图类型：项目 / 方案 */
const viewType = ref<'project' | 'proposal'>('project')
/** 项目子 Tab */
const activeTab = ref('tasks')
/** 方案子 Tab */
const propActiveTab = ref('design')

const avatarInitial = computed(() => (userStore.userInfo?.real_name || '').charAt(0) || '?')

// ========== 项目：待办 ==========
const tasks = ref<TaskListItem[]>([])
const taskLoading = ref(false)
const taskCount = ref(0)
const taskKeyword = ref('')
const taskStatus = ref('')

async function fetchTasks() {
  taskLoading.value = true
  try {
    const data = await getTasks({ status: taskStatus.value || undefined, keyword: taskKeyword.value || undefined, type: 'project' })
    tasks.value = data.items
    taskCount.value = data.total
  } finally { taskLoading.value = false }
}

// ========== 项目：校验 ==========
const checks = ref<CheckListItem[]>([])
const checkLoading = ref(false)
const checkCount = ref(0)
const checkKeyword = ref('')

async function fetchChecks() {
  checkLoading.value = true
  try {
    const data = await getChecks({ keyword: checkKeyword.value || undefined })
    checks.value = data.items
    checkCount.value = data.total
  } finally { checkLoading.value = false }
}

// ========== 项目：审批 ==========
const approvals = ref<ApprovalListItem[]>([])
const approvalLoading = ref(false)
const approvalCount = ref(0)
const approvalKeyword = ref('')

async function fetchApprovals() {
  approvalLoading.value = true
  try {
    const data = await getApprovals({ keyword: approvalKeyword.value || undefined, type: 'project' })
    approvals.value = data.items
    approvalCount.value = data.total
  } finally { approvalLoading.value = false }
}

// ========== 项目：我发起的 ==========
const initiatedList = ref<MyInitiatedItem[]>([])
const initiatedLoading = ref(false)

async function fetchInitiated() {
  initiatedLoading.value = true
  try {
    const data = await getMyInitiated({ page: 1, page_size: 50, type: 'project' })
    initiatedList.value = data.items
  } finally { initiatedLoading.value = false }
}

// ========== 方案：设计（待办） ==========
const propTasks = ref<TaskListItem[]>([])
const propTaskLoading = ref(false)
const propTaskCount = ref(0)

async function fetchPropTasks() {
  propTaskLoading.value = true
  try {
    const data = await getTasks({ type: 'proposal' })
    propTasks.value = data.items
    propTaskCount.value = data.total
  } finally { propTaskLoading.value = false }
}

// ========== 方案：审批 ==========
const propApprovals = ref<ApprovalListItem[]>([])
const propApprovalLoading = ref(false)
const propApprovalCount = ref(0)

async function fetchPropApprovals() {
  propApprovalLoading.value = true
  try {
    const data = await getApprovals({ type: 'proposal' })
    propApprovals.value = data.items
    propApprovalCount.value = data.total
  } finally { propApprovalLoading.value = false }
}

// ========== 方案：我发起的 ==========
const propInitiatedList = ref<MyInitiatedItem[]>([])
const propInitiatedLoading = ref(false)

async function fetchPropInitiated() {
  propInitiatedLoading.value = true
  try {
    const data = await getMyInitiated({ page: 1, page_size: 50, type: 'proposal' })
    propInitiatedList.value = data.items
  } finally { propInitiatedLoading.value = false }
}

// ========== 生命周期 ==========
onMounted(() => {
  setBreadcrumb([{ label: '首页', to: '/dashboard' }, { label: '个人中心' }])
  fetchTasks()
  fetchChecks()
  fetchApprovals()
})

/** 项目 Tab 切换时按需加载 */
watch(activeTab, (tab) => {
  if (tab === 'checks') fetchChecks()
  else if (tab === 'approvals') fetchApprovals()
  else if (tab === 'initiated') fetchInitiated()
})

/** 方案视图切换时加载对应数据 */
function handleViewTypeChange() {
  if (viewType.value === 'proposal') {
    fetchPropTasks()
    fetchPropApprovals()
    if (isManager.value) fetchPropInitiated()
  }
}

// 方案子 Tab 切换时按需加载
watch(propActiveTab, (tab) => {
  if (tab === 'approve') fetchPropApprovals()
  else if (tab === 'initiated') fetchPropInitiated()
})

// ========== 工具函数 ==========
// 任务/校验/审批状态 —— 统一从 @/utils/labels 导入
</script>

<style lang="scss" scoped>
.profile-page {
  // max-width 由 AppLayout 内容区统一控制
}

.user-info-card {
  display: flex; align-items: center; gap: 16px;
  padding: 20px; background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light); border-radius: 10px; margin-bottom: 20px;

  &__avatar {
    width: 48px; height: 48px; border-radius: 50%;
    background: var(--el-color-primary); color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; font-weight: 600; flex-shrink: 0;
  }
  &__name { font-size: 16px; font-weight: 600; }
  &__meta { font-size: 13px; color: var(--el-text-color-secondary); margin-top: 4px; }
}

/* 顶层 项目/方案 切换 */
.view-type-bar { margin-bottom: 16px; }

.profile-tabs { margin-bottom: 16px; }

.tab-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px; border-radius: 9px;
  background: var(--el-color-danger); color: #fff; font-size: 11px; padding: 0 5px; margin-left: 4px;
}

/* radio-button 内部作为红点定位基准 */
.view-type-bar :deep(.el-radio-button__inner) {
  position: relative;
}

/* 按钮框内右上角小红点 */
.view-dot {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-danger);
  font-style: normal;
}

.list-toolbar { display: flex; gap: 12px; margin-bottom: 16px; }

.text-danger { color: var(--el-color-danger); font-weight: 500; }

.pri-tag {
  font-size: 12px; font-weight: 500; padding: 1px 6px; border-radius: 8px;
  &.pri--urgent { color: #fff; background: var(--el-color-danger); }
  &.pri--high { color: #fff; background: var(--el-color-warning); }
  &.pri--normal { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.pri--low { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}
</style>
