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
        <el-tab-pane name="endorsements">
          <template #label>
            <span>我的批准<span class="tab-badge" v-if="endorsementCount > 0">{{ endorsementCount }}</span></span>
          </template>
        </el-tab-pane>
        <el-tab-pane v-if="isManager" name="initiated">
          <template #label><span>我发起的流程</span></template>
        </el-tab-pane>
      </el-tabs>

      <!-- 待办列表 -->
      <template v-if="activeTab === 'tasks'">
        <div class="list-toolbar">
          <el-input v-model="taskKeyword" placeholder="搜索项目名称" clearable style="width:220px" @change="handleTaskSearch" />
          <el-select v-model="taskStatus" placeholder="状态" clearable style="width:140px" @change="handleTaskSearch">
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="processing" />
          </el-select>
        </div>
        <el-table border :data="tasks" stripe v-loading="taskLoading" :row-class-name="(d: any) => deadlineRowClass(d)" @row-click="(row: any) => router.push({ name: 'TaskDetail', params: { id: row.id } })" style="cursor:pointer">
          <el-table-column prop="instance_name" label="项目" min-width="140" />
          <el-table-column prop="node_name" label="当前节点" min-width="100" />
          <el-table-column prop="initiator_name" label="发起人" min-width="72" />
          <el-table-column label="截止时间" min-width="140">
            <template #default="{ row }">
              <span v-if="row.deadline">{{ formatTime(row.deadline) }}</span>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="优先级" min-width="64">
            <template #default="{ row }">
              <span class="pri-badge" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="64">
            <template #default="{ row }">
              <span class="status-tag" :class="taskStatusClass(row.status)">{{ taskStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push({ name: 'TaskDetail', params: { id: row.id } })">处理</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!taskLoading && tasks.length === 0" description="暂无待办任务" :image-size="50" />
        <div class="list-pagination"><el-pagination v-model:current-page="taskPage" v-model:page-size="taskPageSize" :page-sizes="[20,50,100]" :total="taskTotal" layout="total,sizes,prev,pager,next" @current-change="fetchTasks" @size-change="fetchTasks" /></div>
      </template>

      <!-- 校验列表 -->
      <template v-if="activeTab === 'checks'">
        <div class="list-toolbar">
          <el-input v-model="checkKeyword" placeholder="搜索项目名称" clearable style="width:220px" @change="handleCheckSearch" />
        </div>
        <el-table border :data="checks" stripe v-loading="checkLoading" :row-class-name="(d: any) => deadlineRowClass(d)" @row-click="(row: any) => router.push({ name: 'CheckDetail', params: { id: row.id } })" style="cursor:pointer">
          <el-table-column prop="instance_name" label="项目" min-width="140" />
          <el-table-column prop="node_name" label="节点" min-width="100" />
          <el-table-column prop="submitter_name" label="提交人" min-width="72" />
          <el-table-column prop="created_at" label="提交时间" min-width="140" :formatter="(r: any) => formatTime(r.created_at)" />
          <el-table-column label="轮次" min-width="48">
            <template #default="{ row }"><span v-if="row.round > 1" class="round-tag">#{{ row.round }}</span></template>
          </el-table-column>
          <el-table-column label="截止时间" min-width="120">
            <template #default="{ row }">
              <span v-if="row.deadline">{{ formatTime(row.deadline) }}</span>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="64">
            <template #default="{ row }">
              <span class="status-tag" :class="checkStatusClass(row.status)">{{ checkStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push({ name: 'CheckDetail', params: { id: row.id } })">校验</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!checkLoading && checks.length === 0" description="暂无待校验" :image-size="50" />
        <div class="list-pagination"><el-pagination v-model:current-page="checkPage" v-model:page-size="checkPageSize" :page-sizes="[20,50,100]" :total="checkTotal" layout="total,sizes,prev,pager,next" @current-change="fetchChecks" @size-change="fetchChecks" /></div>
      </template>

      <!-- 审批列表 -->
      <template v-if="activeTab === 'approvals'">
        <div class="list-toolbar">
          <el-input v-model="approvalKeyword" placeholder="搜索项目名称" clearable style="width:220px" @change="handleApprovalSearch" />
        </div>
        <el-table border :data="approvals" stripe v-loading="approvalLoading" :row-class-name="(d: any) => deadlineRowClass(d)" @row-click="(row: any) => router.push({ name: 'ApprovalDetail', params: { id: row.id } })" style="cursor:pointer">
          <el-table-column prop="instance_name" label="项目" min-width="140" />
          <el-table-column prop="node_name" label="节点" min-width="100">
            <template #default="{ row }">
              {{ row.node_name }}<el-tag v-if="row.is_end_node" size="small" type="warning" effect="plain" style="margin-left:6px">终审</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" min-width="140" :formatter="(r: any) => formatTime(r.created_at)" />
          <el-table-column label="轮次" min-width="48">
            <template #default="{ row }"><span v-if="row.round > 1" class="round-tag">#{{ row.round }}</span></template>
          </el-table-column>
          <el-table-column label="截止时间" min-width="120">
            <template #default="{ row }">
              <span v-if="row.deadline" >{{ formatTime(row.deadline) }}</span>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="64">
            <template #default="{ row }">
              <span class="status-tag" :class="approvalStatusClass(row.status)">{{ approvalStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push({ name: 'ApprovalDetail', params: { id: row.id } })">审批</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!approvalLoading && approvals.length === 0" description="暂无待审批" :image-size="50" />
        <div class="list-pagination"><el-pagination v-model:current-page="approvalPage" v-model:page-size="approvalPageSize" :page-sizes="[20,50,100]" :total="approvalTotal" layout="total,sizes,prev,pager,next" @current-change="fetchApprovals" @size-change="fetchApprovals" /></div>
      </template>

      <!-- 批准列表 -->
      <template v-if="activeTab === 'endorsements'">
        <div class="list-toolbar">
          <el-input v-model="endorsementKeyword" placeholder="搜索项目名称" clearable style="width:220px" @change="handleEndorsementSearch" />
        </div>
        <el-table border :data="endorsements" stripe v-loading="endorsementLoading" :row-class-name="(d: any) => deadlineRowClass(d)" @row-click="(row: any) => router.push({ name: 'EndorseDetail', params: { id: row.id } })" style="cursor:pointer">
          <el-table-column prop="instance_name" label="项目" min-width="140" />
          <el-table-column prop="node_name" label="节点" min-width="100" />
          <el-table-column prop="created_at" label="创建时间" min-width="140" :formatter="(r: any) => formatTime(r.created_at)" />
          <el-table-column label="轮次" min-width="48">
            <template #default="{ row }"><span v-if="row.round > 1" class="round-tag">#{{ row.round }}</span></template>
          </el-table-column>
          <el-table-column label="截止时间" min-width="120">
            <template #default="{ row }">
              <span v-if="row.deadline">{{ formatTime(row.deadline) }}</span>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="64">
            <template #default="{ row }">
              <span class="status-tag" :class="endorsementStatusClass(row.status)">{{ endorsementStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push({ name: 'EndorseDetail', params: { id: row.id } })">批准</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!endorsementLoading && endorsements.length === 0" description="暂无待批准" :image-size="50" />
        <div class="list-pagination"><el-pagination v-model:current-page="endorsementPage" v-model:page-size="endorsementPageSize" :page-sizes="[20,50,100]" :total="endorsementTotal" layout="total,sizes,prev,pager,next" @current-change="fetchEndorsements" @size-change="fetchEndorsements" /></div>
      </template>

      <!-- 我发起的流程 -->
      <template v-if="activeTab === 'initiated'">
        <div class="list-toolbar">
          <el-input v-model="initiatedKeyword" placeholder="搜索项目名称" clearable style="width:220px" @change="handleInitiatedSearch" />
        </div>
        <el-table border :data="initiatedList" stripe v-loading="initiatedLoading" @row-click="(row: any) => router.push({ name: 'InstanceDetail', params: { id: row.id } })" style="cursor:pointer">
          <el-table-column prop="name" label="项目名称" min-width="140" show-overflow-tooltip />
          <el-table-column label="方案" min-width="100" show-overflow-tooltip>
            <template #default="{ row }">{{ row.proposal_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="进度" min-width="90">
            <template #default="{ row }">
              {{ row.total_nodes > 0 ? Math.round((row.current_node_index / row.total_nodes) * 100) : 0 }}%（{{ row.current_node_index }}/{{ row.total_nodes }}）
            </template>
          </el-table-column>
          <el-table-column prop="current_handlers" label="当前处理人" min-width="90" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ row.current_handlers || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="64">
            <template #default="{ row }"><span class="status-tag" :class="instStatusClass(row.status)">{{ instStatusLabel(row.status) }}</span></template>
          </el-table-column>
          <el-table-column label="优先级" min-width="64">
            <template #default="{ row }"><span class="pri-badge" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span></template>
          </el-table-column>
          <el-table-column label="难度" min-width="64">
            <template #default="{ row }"><span class="diff-badge diff-badge--list" :class="'diff--' + (row.difficulty || '1')">{{ row.difficulty || '1' }}级</span></template>
          </el-table-column>
          <el-table-column label="发起时间" min-width="140">
            <template #default="{ row }">{{ formatTime(row.initiated_at || row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="截止时间" min-width="140">
            <template #default="{ row }">{{ row.flow_deadline ? formatTime(row.flow_deadline) : '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push({ name: 'InstanceDetail', params: { id: row.id } })">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!initiatedLoading && initiatedList.length === 0" description="暂无发起的流程" :image-size="50" />
        <div class="list-pagination"><el-pagination v-model:current-page="initiatedPage" v-model:page-size="initiatedPageSize" :page-sizes="[20,50,100]" :total="initiatedTotal" layout="total,sizes,prev,pager,next" @current-change="fetchInitiated" @size-change="fetchInitiated" /></div>
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
        <el-tab-pane name="propEndorsements">
          <template #label>
            <span>方案批准<span class="tab-badge" v-if="propEndorsementCount > 0">{{ propEndorsementCount }}</span></span>
          </template>
        </el-tab-pane>
        <el-tab-pane v-if="isManager" name="initiated">
          <template #label><span>我发起的方案</span></template>
        </el-tab-pane>
      </el-tabs>

      <!-- 方案设计（设计人的待办任务） -->
      <template v-if="propActiveTab === 'design'">
        <el-table border :data="propTasks" stripe v-loading="propTaskLoading" @row-click="(row: any) => router.push({ name: 'TaskDetail', params: { id: row.id } })" style="cursor:pointer">
          <el-table-column prop="instance_name" label="方案名称" min-width="160" />
          <el-table-column prop="initiator_name" label="发起人" min-width="72" />
          <el-table-column label="截止时间" min-width="140">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.is_overdue }">{{ formatTime(row.deadline) }}</span>
              <el-tag v-if="row.is_overdue" type="danger" size="small" style="margin-left:6px">已逾期</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="64">
            <template #default="{ row }">
              <span class="status-tag" :class="taskStatusClass(row.status)">{{ taskStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push({ name: 'TaskDetail', params: { id: row.id } })">设计</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!propTaskLoading && propTasks.length === 0" description="暂无方案设计任务" :image-size="50" />
        <div class="list-pagination"><el-pagination v-model:current-page="propTaskPage" v-model:page-size="propTaskPageSize" :page-sizes="[20,50,100]" :total="propTaskTotal" layout="total,sizes,prev,pager,next" @current-change="fetchPropTasks" @size-change="fetchPropTasks" /></div>
      </template>

      <!-- 方案审批 -->
      <template v-if="propActiveTab === 'approve'">
        <el-table border :data="propApprovals" stripe v-loading="propApprovalLoading" @row-click="(row: any) => router.push({ name: 'ApprovalDetail', params: { id: row.id } })" style="cursor:pointer">
          <el-table-column prop="instance_name" label="方案名称" min-width="160" />
          <el-table-column prop="created_at" label="创建时间" min-width="140" :formatter="(r: any) => formatTime(r.created_at)" />
          <el-table-column label="状态" min-width="64">
            <template #default="{ row }">
              <span class="status-tag" :class="approvalStatusClass(row.status)">{{ approvalStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push({ name: 'ApprovalDetail', params: { id: row.id } })">审批</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!propApprovalLoading && propApprovals.length === 0" description="暂无待审批方案" :image-size="50" />
        <div class="list-pagination"><el-pagination v-model:current-page="propApprovalPage" v-model:page-size="propApprovalPageSize" :page-sizes="[20,50,100]" :total="propApprovalTotal" layout="total,sizes,prev,pager,next" @current-change="fetchPropApprovals" @size-change="fetchPropApprovals" /></div>
      </template>

      <!-- 方案批准列表 -->
      <template v-if="propActiveTab === 'propEndorsements'">
        <el-table border :data="propEndorsements" stripe v-loading="propEndorsementLoading" @row-click="(row: any) => router.push({ name: 'EndorseDetail', params: { id: row.id } })" style="cursor:pointer">
          <el-table-column prop="instance_name" label="方案名称" min-width="160" />
          <el-table-column prop="created_at" label="创建时间" min-width="140" :formatter="(r: any) => formatTime(r.created_at)" />
          <el-table-column label="状态" min-width="64">
            <template #default="{ row }">
              <span class="status-tag" :class="endorsementStatusClass(row.status)">{{ endorsementStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push({ name: 'EndorseDetail', params: { id: row.id } })">批准</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!propEndorsementLoading && propEndorsements.length === 0" description="暂无待批准方案" :image-size="50" />
        <div class="list-pagination"><el-pagination v-model:current-page="propEndorsementPage" v-model:page-size="propEndorsementPageSize" :page-sizes="[20,50,100]" :total="propEndorsementTotal" layout="total,sizes,prev,pager,next" @current-change="fetchPropEndorsements" @size-change="fetchPropEndorsements" /></div>
      </template>

      <!-- 我发起的方案 -->
      <template v-if="propActiveTab === 'initiated'">
        <div class="list-toolbar">
          <el-input v-model="propInitiatedKeyword" placeholder="搜索方案名称" clearable style="width:220px" @change="handlePropInitiatedSearch" />
        </div>
        <el-table border :data="propInitiatedList" stripe v-loading="propInitiatedLoading" @row-click="(row: any) => router.push({ name: 'ProposalDetail', params: { id: row.id } })" style="cursor:pointer">
          <el-table-column prop="name" label="方案名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="initiator_name" label="发起人" min-width="72" show-overflow-tooltip>
            <template #default="{ row }">{{ row.initiator_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">{{ row.description || '-' }}</template>
          </el-table-column>
          <el-table-column label="发起时间" min-width="140">
            <template #default="{ row }">{{ formatTime(row.initiated_at || row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="截止时间" min-width="140">
            <template #default="{ row }">{{ row.flow_deadline ? formatTime(row.flow_deadline) : '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" min-width="64">
            <template #default="{ row }"><span class="status-tag" :class="instStatusClass(row.status)">{{ instStatusLabel(row.status) }}</span></template>
          </el-table-column>
          <el-table-column label="操作" min-width="60">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click.stop="router.push({ name: 'ProposalDetail', params: { id: row.id } })">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!propInitiatedLoading && propInitiatedList.length === 0" description="暂无发起的方案" :image-size="50" />
        <div class="list-pagination"><el-pagination v-model:current-page="propInitiatedPage" v-model:page-size="propInitiatedPageSize" :page-sizes="[20,50,100]" :total="propInitiatedTotal" layout="total,sizes,prev,pager,next" @current-change="fetchPropInitiated" @size-change="fetchPropInitiated" /></div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
/** 个人中心 —— 项目/方案 顶层切换 + Tab 分区 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useNotificationStore } from '@/stores/notification'
import { getTasks, type TaskListItem } from '@/api/task'
import { getChecks, type CheckListItem } from '@/api/check'
import { getApprovals, type ApprovalListItem } from '@/api/approval'
import { getEndorsements, type EndorsementListItem } from '@/api/endorsement'
import { getInstances, type InstanceListItem } from '@/api/instance'
import { getProposals, type ProposalListItem } from '@/api/proposal'
import { fetchSummaryCounts, type SummaryCounts } from '@/api/notification'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import { formatTime, deadlineRowClass } from '@/utils/format'
import { priLabel, roleLabel, instStatusClass, instStatusLabel, taskStatusClass, taskStatusLabel, checkStatusClass, checkStatusLabel, approvalStatusClass, approvalStatusLabel, endorsementStatusClass, endorsementStatusLabel } from '@/utils/labels'

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
const taskTotal = ref(0)
const taskPage = ref(1)
const taskPageSize = ref(20)
const taskKeyword = ref('')
const taskStatus = ref('')

async function fetchTasks() {
  taskLoading.value = true
  try {
    const data = await getTasks({ status: taskStatus.value || undefined, keyword: taskKeyword.value || undefined, type: 'project', page: taskPage.value, page_size: taskPageSize.value })
    tasks.value = data.items
    taskCount.value = data.total
    taskTotal.value = data.total
  } finally { taskLoading.value = false }
}

// ========== M21：筛选条件变化时先重置到第一页再拉取 ==========
// 原实现：搜索/状态筛选直接 fetchXxx 用旧页码，深页码下筛选大概率空结果
function handleTaskSearch() {
  taskPage.value = 1
  fetchTasks()
}
function handleCheckSearch() {
  checkPage.value = 1
  fetchChecks()
}
function handleApprovalSearch() {
  approvalPage.value = 1
  fetchApprovals()
}
function handleEndorsementSearch() {
  endorsementPage.value = 1
  fetchEndorsements()
}
function handleInitiatedSearch() {
  initiatedPage.value = 1
  fetchInitiated()
}
function handlePropInitiatedSearch() {
  propInitiatedPage.value = 1
  fetchPropInitiated()
}

// ========== 项目：校验 ==========
const checks = ref<CheckListItem[]>([])
const checkLoading = ref(false)
const checkCount = ref(0)
const checkTotal = ref(0)
const checkPage = ref(1)
const checkPageSize = ref(20)
const checkKeyword = ref('')

async function fetchChecks() {
  checkLoading.value = true
  try {
    const data = await getChecks({ keyword: checkKeyword.value || undefined, page: checkPage.value, page_size: checkPageSize.value })
    checks.value = data.items
    checkCount.value = data.total
    checkTotal.value = data.total
  } finally { checkLoading.value = false }
}

// ========== 项目：审批 ==========
const approvals = ref<ApprovalListItem[]>([])
const approvalLoading = ref(false)
const approvalCount = ref(0)
const approvalTotal = ref(0)
const approvalPage = ref(1)
const approvalPageSize = ref(20)
const approvalKeyword = ref('')

async function fetchApprovals() {
  approvalLoading.value = true
  try {
    const data = await getApprovals({ keyword: approvalKeyword.value || undefined, type: 'project', page: approvalPage.value, page_size: approvalPageSize.value })
    approvals.value = data.items
    approvalCount.value = data.total
    approvalTotal.value = data.total
  } finally { approvalLoading.value = false }
}

// ========== 项目：批准 ==========
const endorsements = ref<EndorsementListItem[]>([])
const endorsementLoading = ref(false)
const endorsementCount = ref(0)
const endorsementTotal = ref(0)
const endorsementPage = ref(1)
const endorsementPageSize = ref(20)
const endorsementKeyword = ref('')

async function fetchEndorsements() {
  endorsementLoading.value = true
  try {
    const data = await getEndorsements({ type: 'project', keyword: endorsementKeyword.value || undefined, page: endorsementPage.value, page_size: endorsementPageSize.value })
    endorsements.value = data.items
    endorsementCount.value = data.total
    endorsementTotal.value = data.total
  } finally { endorsementLoading.value = false }
}

// ========== 项目：我发起的 ==========
const initiatedList = ref<InstanceListItem[]>([])
const initiatedLoading = ref(false)
const initiatedTotal = ref(0)
const initiatedPage = ref(1)
const initiatedPageSize = ref(20)
const initiatedKeyword = ref('')

async function fetchInitiated() {
  initiatedLoading.value = true
  try {
    // 复用项目列表接口（initiator_id 过滤 = 我发起的），字段与开工项目完全一致
    const data = await getInstances({ initiator_id: userStore.userInfo?.id, page: initiatedPage.value, page_size: initiatedPageSize.value, keyword: initiatedKeyword.value || undefined })
    initiatedList.value = data.items
    initiatedTotal.value = data.total
  } finally { initiatedLoading.value = false }
}

// ========== 方案：设计（待办） ==========
const propTasks = ref<TaskListItem[]>([])
const propTaskLoading = ref(false)
const propTaskCount = ref(0)
const propTaskTotal = ref(0)
const propTaskPage = ref(1)
const propTaskPageSize = ref(20)

async function fetchPropTasks() {
  propTaskLoading.value = true
  try {
    const data = await getTasks({ type: 'proposal', page: propTaskPage.value, page_size: propTaskPageSize.value })
    propTasks.value = data.items
    propTaskCount.value = data.total
    propTaskTotal.value = data.total
  } finally { propTaskLoading.value = false }
}

// ========== 方案：审批 ==========
const propApprovals = ref<ApprovalListItem[]>([])
const propApprovalLoading = ref(false)
const propApprovalCount = ref(0)
const propApprovalTotal = ref(0)
const propApprovalPage = ref(1)
const propApprovalPageSize = ref(20)

async function fetchPropApprovals() {
  propApprovalLoading.value = true
  try {
    const data = await getApprovals({ type: 'proposal', page: propApprovalPage.value, page_size: propApprovalPageSize.value })
    propApprovals.value = data.items
    propApprovalCount.value = data.total
    propApprovalTotal.value = data.total
  } finally { propApprovalLoading.value = false }
}

// ========== 方案：批准 ==========
const propEndorsements = ref<EndorsementListItem[]>([])
const propEndorsementLoading = ref(false)
const propEndorsementCount = ref(0)
const propEndorsementTotal = ref(0)
const propEndorsementPage = ref(1)
const propEndorsementPageSize = ref(20)

async function fetchPropEndorsements() {
  propEndorsementLoading.value = true
  try {
    const data = await getEndorsements({ type: 'proposal', page: propEndorsementPage.value, page_size: propEndorsementPageSize.value })
    propEndorsements.value = data.items
    propEndorsementCount.value = data.total
    propEndorsementTotal.value = data.total
  } finally { propEndorsementLoading.value = false }
}

// ========== 方案：我发起的 ==========
const propInitiatedList = ref<ProposalListItem[]>([])
const propInitiatedLoading = ref(false)
const propInitiatedTotal = ref(0)
const propInitiatedPage = ref(1)
const propInitiatedPageSize = ref(20)
const propInitiatedKeyword = ref('')

async function fetchPropInitiated() {
  propInitiatedLoading.value = true
  try {
    // 复用方案列表接口（initiator_id 过滤 = 我发起的），字段与方案管理完全一致
    const data = await getProposals({ initiator_id: userStore.userInfo?.id, page: propInitiatedPage.value, page_size: propInitiatedPageSize.value, keyword: propInitiatedKeyword.value || undefined })
    propInitiatedList.value = data.items
    propInitiatedTotal.value = data.total
  } finally { propInitiatedLoading.value = false }
}

// ========== 生命周期 ==========

/** 从 summary 数据刷新所有 Tab 角标（不拉取列表内容，只更新红点数字） */
function applySummaryToTabBadges(summary: SummaryCounts) {
  if (viewType.value === 'project') {
    taskCount.value = summary.project_task_count
    checkCount.value = summary.project_check_count
    approvalCount.value = summary.project_approval_count
    endorsementCount.value = summary.project_endorsement_count
  } else {
    propTaskCount.value = summary.proposal_task_count
    propApprovalCount.value = summary.proposal_approval_count
    propEndorsementCount.value = summary.proposal_endorsement_count
  }
}

/** 静默刷新全部 Tab 角标（不显示 loading） */
let pollTimer: ReturnType<typeof setInterval> | null = null
let countsRefreshedHandler: ((e: Event) => void) | null = null

function startAutoRefresh() {
  // WebSocket 实时推送 → 即时刷新角标
  countsRefreshedHandler = (e: Event) => {
    const summary = (e as CustomEvent).detail as SummaryCounts
    if (summary) applySummaryToTabBadges(summary)
  }
  window.addEventListener('counts-refreshed', countsRefreshedHandler)

  // 30s 轮询兜底（WebSocket 断开等极端情况）
  pollTimer = setInterval(async () => {
    try {
      const summary = await fetchSummaryCounts()
      applySummaryToTabBadges(summary)
      // P1-42：同时更新 notifyStore —— WS 断开时侧边栏角标也能兜底刷新
      notifyStore.setCounts(summary.task_count, summary.check_count, summary.approval_count, summary.endorsement_count)
      notifyStore.setTypedCounts(summary.project_pending, summary.proposal_pending)
    } catch { /* 静默失败 */ }
  }, 30000)
}

function stopAutoRefresh() {
  if (countsRefreshedHandler) {
    window.removeEventListener('counts-refreshed', countsRefreshedHandler)
    countsRefreshedHandler = null
  }
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  setBreadcrumb([{ label: '首页', to: '/dashboard' }, { label: '个人中心' }])
  fetchTasks()
  fetchChecks()
  fetchApprovals()
  fetchEndorsements()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})

/** 项目 Tab 切换时按需加载 */
watch(activeTab, (tab) => {
  if (tab === 'checks') fetchChecks()
  else if (tab === 'approvals') fetchApprovals()
  else if (tab === 'endorsements') fetchEndorsements()
  else if (tab === 'initiated') fetchInitiated()
})

/** 方案视图切换时加载对应数据 */
function handleViewTypeChange() {
  if (viewType.value === 'proposal') {
    fetchPropTasks()
    fetchPropApprovals()
    fetchPropEndorsements()
    if (isManager.value) fetchPropInitiated()
  }
}

// 方案子 Tab 切换时按需加载
watch(propActiveTab, (tab) => {
  if (tab === 'approve') fetchPropApprovals()
  else if (tab === 'propEndorsements') fetchPropEndorsements()
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
.text-muted { color: var(--el-text-color-placeholder); }

.pri-badge { font-size: 12px; font-weight: 500; padding: 1px 8px; border-radius: 10px; &.pri--urgent { background: #fde2e2; color: #c0392b; } &.pri--high { background: #fef5e7; color: #d68910; } &.pri--normal { background: #eaf2f8; color: #2471a3; } &.pri--low { background: #f2f3f5; color: #86909c; } }

/* 分页 */
.list-pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>

<style lang="scss">
/* 逾期/临期行背景色（非 scoped 才能覆盖 el-table 行样式） */
.r--red td { background: #fef0f0 !important; }
.r--yel td { background: #fffaf0 !important; }
</style>
