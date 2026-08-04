<template>
  <!-- 超期预警 —— 系统全部超期项汇总，仅首页卡片入口 -->
  <div class="overdue-page">
    <div class="page-header">
      <h1 class="page-header__title">超期预警</h1>
      <span class="page-header__sub">系统全部超期项</span>
    </div>

    <div class="overdue-summary" v-if="summary">
      <span class="overdue-summary__item overdue-summary__item--task">
        ⚠ 超期待办：{{ summary.tasks.length }} 项
      </span>
      <span class="overdue-summary__item overdue-summary__item--check">
        超期校验：{{ summary.checks.length }} 项
      </span>
      <span class="overdue-summary__item overdue-summary__item--approval">
        超期审批：{{ summary.approvals.length }} 项
      </span>
      <span class="overdue-summary__item overdue-summary__item--endorsement">
        超期批准：{{ summary.endorsements.length }} 项
      </span>
    </div>

    <!-- 超期待办 -->
    <section class="overdue-section" v-if="summary?.tasks.length">
      <h3 class="overdue-section__title">超期待办任务</h3>
      <el-table border :data="summary.tasks" stripe style="width:100%">
        <el-table-column prop="instance_name" label="项目/方案" min-width="160" />
        <el-table-column prop="node_name" label="当前节点" min-width="120" />
        <el-table-column prop="person_name" label="负责人" min-width="80" />
        <el-table-column label="截止时间" min-width="150">
          <template #default="{ row }">
            <span :class="row.is_overdue ? 'text-danger' : 'text-warning'">{{ formatTime(row.deadline) }}</span>
            <el-tag :type="row.is_overdue ? 'danger' : 'warning'" size="small" style="margin-left:6px">{{ row.is_overdue ? '已逾期' : '即将逾期' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="organization_name" label="所属组织" min-width="100" />
        <el-table-column label="优先级" min-width="64">
          <template #default="{ row }">
            <span class="pri-tag" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="100">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="goInstance(row.instance_id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 超期校验 -->
    <section class="overdue-section" v-if="summary?.checks.length">
      <h3 class="overdue-section__title">超期校验</h3>
      <el-table border :data="summary.checks" stripe style="width:100%">
        <el-table-column prop="instance_name" label="项目" min-width="160" />
        <el-table-column prop="node_name" label="当前节点" min-width="120" />
        <el-table-column prop="person_name" label="校验人" min-width="80" />
        <el-table-column label="截止时间" min-width="150">
          <template #default="{ row }">
            <span :class="row.is_overdue ? 'text-danger' : 'text-warning'">{{ formatTime(row.deadline) }}</span>
            <el-tag :type="row.is_overdue ? 'danger' : 'warning'" size="small" style="margin-left:6px">{{ row.is_overdue ? '已逾期' : '即将逾期' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="organization_name" label="所属组织" min-width="100" />
        <el-table-column label="优先级" min-width="64">
          <template #default="{ row }">
            <span class="pri-tag" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="100">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="goInstance(row.instance_id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 超期审批 -->
    <section class="overdue-section" v-if="summary?.approvals.length">
      <h3 class="overdue-section__title">超期审批</h3>
      <el-table border :data="summary.approvals" stripe style="width:100%">
        <el-table-column prop="instance_name" label="项目/方案" min-width="160" />
        <el-table-column prop="node_name" label="当前节点" min-width="120" />
        <el-table-column prop="person_name" label="审批人" min-width="80" />
        <el-table-column label="截止时间" min-width="150">
          <template #default="{ row }">
            <span :class="row.is_overdue ? 'text-danger' : 'text-warning'">{{ formatTime(row.deadline) }}</span>
            <el-tag :type="row.is_overdue ? 'danger' : 'warning'" size="small" style="margin-left:6px">{{ row.is_overdue ? '已逾期' : '即将逾期' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="organization_name" label="所属组织" min-width="100" />
        <el-table-column label="优先级" min-width="64">
          <template #default="{ row }">
            <span class="pri-tag" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="100">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="goInstance(row.instance_id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 超期批准 -->
    <section class="overdue-section" v-if="summary?.endorsements.length">
      <h3 class="overdue-section__title">超期批准</h3>
      <el-table border :data="summary.endorsements" stripe style="width:100%">
        <el-table-column prop="instance_name" label="项目/方案" min-width="160" />
        <el-table-column prop="node_name" label="当前节点" min-width="120" />
        <el-table-column prop="person_name" label="批准人" min-width="80" />
        <el-table-column label="截止时间" min-width="150">
          <template #default="{ row }">
            <span :class="row.is_overdue ? 'text-danger' : 'text-warning'">{{ formatTime(row.deadline) }}</span>
            <el-tag :type="row.is_overdue ? 'danger' : 'warning'" size="small" style="margin-left:6px">{{ row.is_overdue ? '已逾期' : '即将逾期' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="organization_name" label="所属组织" min-width="100" />
        <el-table-column label="优先级" min-width="64">
          <template #default="{ row }">
            <span class="pri-tag" :class="'pri--' + row.priority">{{ priLabel(row.priority) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="100">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="goInstance(row.instance_id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-empty v-if="loading" description="加载中..." :image-size="50" />
    <el-empty v-if="!loading && isEmpty" description="当前没有超期项 🎉" :image-size="60" />
  </div>
</template>

<script setup lang="ts">
/** 超期预警 —— 系统全部超期项汇总，全部用户可见，仅首页卡片入口 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/api/request'
import { formatTime } from '@/utils/format'
import { priLabel } from '@/utils/labels'
import { useBreadcrumb } from '@/composables/useBreadcrumb'

const { setBreadcrumb } = useBreadcrumb()
const router = useRouter()

/** 超期项数据结构 */
interface OverdueItem {
  id: number
  type: string
  instance_id: number
  instance_name: string
  node_name: string
  person_name: string
  person_id: number
  deadline: string | null
  is_overdue: boolean  // true=已逾期 false=即将逾期（2天内到期）
  priority: string
  organization_name: string
}

interface OverdueSummary {
  tasks: OverdueItem[]
  checks: OverdueItem[]
  approvals: OverdueItem[]
  endorsements: OverdueItem[]
}

const summary = ref<OverdueSummary | null>(null)
const loading = ref(true)

/** 是否全部为空 */
const isEmpty = computed(() => {
  if (!summary.value) return true
  const s = summary.value
  return s.tasks.length === 0 && s.checks.length === 0 && s.approvals.length === 0 && s.endorsements.length === 0
})

/**
 * 跳转到实例详情页（项目/方案，组件按 template_type 自动区分文案）
 * P1-34 调整：超期项跳详情而非处理页——非本人的处理页会 403 无权查看，
 * 实例详情对所有登录用户可见，可查看完整流程上下文。
 */
function goInstance(instanceId: number) {
  router.push({ name: 'InstanceDetail', params: { id: instanceId } })
}

onMounted(async () => {
  setBreadcrumb([{ label: '首页', to: '/dashboard' }, { label: '超期预警' }])
  try {
    const { data } = await request.get('/notifications/overdue')
    summary.value = data as OverdueSummary
  } catch { /* 静默 */ }
  finally { loading.value = false }
})
</script>

<style lang="scss" scoped>
.overdue-page {
  padding-bottom: 40px;
}

.page-header {
  margin-bottom: 20px;

  &__title {
    font-size: 20px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  &__sub {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    margin-left: 12px;
  }
}

.overdue-summary {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;

  &__item {
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;

    &--task {
      background: var(--el-color-danger-light-9);
      color: var(--el-color-danger);
    }
    &--check {
      background: var(--el-color-warning-light-9);
      color: var(--el-color-warning);
    }
    &--approval {
      background: var(--el-color-primary-light-9);
      color: var(--el-color-primary);
    }
    &--endorsement {
      background: var(--el-color-info-light-9);
      color: var(--el-color-info);
    }
  }
}

.overdue-section {
  margin-bottom: 28px;

  &__title {
    font-size: 15px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin-bottom: 10px;
    padding-left: 8px;
    border-left: 3px solid var(--el-color-danger);
  }
}

.text-danger {
  color: var(--el-color-danger);
  font-weight: 500;
}

.text-warning {
  color: var(--el-color-warning);
  font-weight: 500;
}

.pri-tag {
  font-size: 12px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 8px;

  &.pri--urgent {
    color: #fff;
    background: var(--el-color-danger);
  }
  &.pri--high {
    color: #fff;
    background: var(--el-color-warning);
  }
  &.pri--normal {
    color: var(--el-text-color-secondary);
    background: var(--el-fill-color);
  }
  &.pri--low {
    color: var(--el-color-info);
    background: var(--el-color-info-light-9);
  }
}
</style>
