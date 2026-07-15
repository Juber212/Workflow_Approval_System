<template>
  <!-- 首页看板 —— 全局统计 + 饼图 + 卡点追踪 + 超期预警 + 各所概览（PRD §4） -->
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">首页看板</h1>
        <p class="page-header__subtitle">全局运行概况 · 所有角色内容一致</p>
      </div>
      <div class="page-header__actions">
        <el-button :icon="Refresh" circle @click="fetchData" :loading="loading" />
      </div>
    </div>

    <!-- ====== 统计卡片 ====== -->
    <div class="stats-grid">
      <div class="stat-card" @click="$router.push('/flows')">
        <div class="stat-card__num stat-card__num--primary">{{ data.stats.running_instances }}</div>
        <div class="stat-card__label">进行中项目</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__num stat-card__num--success">{{ data.stats.archived_total }}</div>
        <div class="stat-card__label">已归档项目</div>
      </div>
      <div class="stat-card">
        <div class="stat-card__num stat-card__num--info">{{ data.stats.archived_this_month }}</div>
        <div class="stat-card__label">本月归档</div>
      </div>
      <div class="stat-card" @click="$router.push('/profile')">
        <div class="stat-card__num stat-card__num--danger">{{ data.stats.overdue_warnings }}</div>
        <div class="stat-card__label">超期预警</div>
      </div>
    </div>

    <!-- ====== 饼图 + 卡点追踪 ====== -->
    <div class="dash-row">
      <div class="card dash-pie">
        <div class="card__header"><span class="card__title">任务状态分布</span></div>
        <div class="card__body" style="display:flex;justify-content:center;padding:24px 20px">
          <PieChart :items="data.task_distribution" @click="handlePieClick" />
        </div>
      </div>

      <div class="card dash-bn">
        <div class="card__header">
          <span class="card__title">流程卡点追踪</span>
          <el-select v-model="bottleneckOrgFilter" placeholder="全部组织" clearable size="small" style="width:120px">
            <el-option v-for="o in orgNames" :key="o" :label="o" :value="o" />
          </el-select>
        </div>
        <div class="card__body" style="padding:0">
          <el-table :data="filteredBottleneck" size="small" stripe v-if="filteredBottleneck.length > 0" :row-class-name="tableRowClass">
            <el-table-column prop="instance_name" label="流程实例" min-width="130" show-overflow-tooltip />
            <el-table-column prop="organization_name" label="所属组织" min-width="90" />
            <el-table-column label="节点进度" min-width="250">
              <template #default="{ row }">
                <div class="chain-row">
                  <template v-for="(seg, i) in row.progress_chain" :key="i">
                    <span class="chain-arr" v-if="i > 0">→</span>
                    <span class="chain-seg" :class="{ 'chain-seg--cur': seg.includes('🔵') }">{{ seg }}</span>
                  </template>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="耗时" min-width="55" align="center">
              <template #default="{ row }">{{ row.days_elapsed }}天</template>
            </el-table-column>
            <el-table-column label="状态" min-width="68" align="center">
              <template #default="{ row }">
                <span class="od-tag" :class="odClass(row.overdue_status)">{{ row.overdue_status }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" min-width="55" align="center">
              <template #default="{ row }">
                <el-button text type="primary" size="small" @click="$router.push(`/flows/instances/${row.instance_id}`)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else style="text-align:center;padding:36px 0;color:var(--el-text-color-secondary);font-size:13px">暂无运行中流程</div>
        </div>
      </div>
    </div>

    <!-- ====== 超期预警 ====== -->
    <div class="card">
      <div class="card__header"><span class="card__title">⚠️ 超期预警</span></div>
      <div class="card__body" style="padding:0">
        <el-table :data="data.overdue_list" size="small" stripe v-if="data.overdue_list.length > 0">
          <el-table-column prop="instance_name" label="流程实例" min-width="150" show-overflow-tooltip />
          <el-table-column prop="node_name" label="当前节点" min-width="100" />
          <el-table-column prop="assignee_name" label="负责人" min-width="68" />
          <el-table-column label="截止时间" min-width="96">
            <template #default="{ row }">{{ fmt(row.deadline) }}</template>
          </el-table-column>
          <el-table-column label="剩余天数" min-width="108">
            <template #default="{ row }">
              <span :class="row.is_overdue ? 'c-red' : 'c-ora'">{{ row.days_label }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="55" align="center">
            <template #default="{ row }">
              <el-button text type="primary" size="small" @click="$router.push(`/flows/instances/${row.instance_id}`)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-else style="text-align:center;padding:36px 0;color:var(--el-text-color-secondary);font-size:13px">🎉 暂无超期任务</div>
      </div>
    </div>

    <!-- ====== 各所概览 ====== -->
    <div class="card">
      <div class="card__header"><span class="card__title">各所流程概览</span></div>
      <div class="card__body" style="padding:0">
        <template v-if="data.org_overview.length > 0">
          <el-collapse>
            <el-collapse-item v-for="org in data.org_overview" :key="org.org_id">
              <template #title>
                <span class="ov-title">{{ org.org_name }}</span>
                <el-tag size="small" effect="plain" style="margin-left:8px">运行中 {{ org.running_count }}</el-tag>
              </template>
              <div v-if="org.instances.length === 0" class="ov-empty">暂无运行中实例</div>
              <div v-for="inst in org.instances" :key="inst.id" class="ov-row" @click="$router.push(`/flows/instances/${inst.id}`)">
                <span class="ov-name">{{ inst.name }}</span>
                <span class="pri-sm" :class="'pri--' + inst.priority">{{ pri(inst.priority) }}</span>
                <span class="ov-cur">当前：{{ inst.current_assignee_name || '—' }}</span>
                <span class="ov-go">→</span>
              </div>
            </el-collapse-item>
          </el-collapse>
        </template>
        <div v-else style="text-align:center;padding:36px 0;color:var(--el-text-color-secondary);font-size:13px">暂无组织数据</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { getDashboard, type DashboardData } from '@/api/dashboard'
import PieChart from './components/PieChart.vue'

const loading = ref(false)
const bottleneckOrgFilter = ref('')

const data = reactive<DashboardData>({
  stats: { running_instances: 0, archived_total: 0, archived_this_month: 0, overdue_warnings: 0 },
  task_distribution: [],
  bottleneck: [],
  overdue_list: [],
  org_overview: [],
})

onMounted(() => fetchData())

async function fetchData() {
  loading.value = true
  try { const d = await getDashboard(); Object.assign(data, d) }
  catch { /* ok */ }
  finally { loading.value = false }
}

// ─── computed ───
const orgNames = computed(() => [...new Set(data.bottleneck.map(b => b.organization_name).filter(Boolean))].sort())
const filteredBottleneck = computed(() =>
  bottleneckOrgFilter.value ? data.bottleneck.filter(b => b.organization_name === bottleneckOrgFilter.value) : data.bottleneck
)

// ─── helpers ───
function handlePieClick(_s: string) { window.location.hash = '#/profile' }
function tableRowClass({ row }: any) { return row.overdue_status === '已逾期' ? 'r--red' : row.overdue_status === '即将逾期' ? 'r--yel' : '' }
function odClass(s: string) { return s === '已逾期' ? 'od--r' : s === '即将逾期' ? 'od--y' : 'od--g' }
function fmt(d: string | null) { return d ? d.substring(0, 10) : '—' }
function pri(p: string) { const m: Record<string, string> = { urgent: '紧急', high: '高', normal: '普通', low: '低' }; return m[p] || p }
</script>

<style lang="scss" scoped>
/* ─── 统计卡片 ─── */
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 16px; }

.stat-card {
  background: var(--el-bg-color); border: 1px solid var(--el-border-color-light);
  border-radius: 8px; padding: 20px 16px; text-align: center; cursor: default;
  transition: box-shadow .15s;
  &:hover { box-shadow: 0 2px 10px rgba(0,0,0,.06); }

  &__num { font-size: 32px; font-weight: 700; line-height: 1.2; font-variant-numeric: tabular-nums; }
  &__num--primary { color: var(--el-color-primary); }
  &__num--success { color: var(--el-color-success); }
  &__num--info    { color: #409EFF; }
  &__num--danger  { color: var(--el-color-danger); }

  &__label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 4px; }
}

/* ─── 双栏 ─── */
.dash-row { display: grid; grid-template-columns: 380px 1fr; gap: 16px; margin-bottom: 16px; }
.dash-pie { min-width: 0; }
.dash-bn { min-width: 0; overflow: hidden; }

/* ─── 卡点追踪节点链 ─── */
.chain-row { display: flex; flex-wrap: wrap; align-items: center; gap: 1px 0; font-size: 11px; line-height: 1.6; padding: 2px 0; }
.chain-arr { color: var(--el-text-color-placeholder); margin: 0 2px; flex-shrink: 0; }
.chain-seg { white-space: nowrap; }
.chain-seg--cur { font-weight: 600; color: var(--el-color-primary); }

/* ─── 逾期 --- */
.od-tag { font-size: 11px; padding: 1px 8px; border-radius: 10px; font-weight: 500; }
.od--r { background: #fde2e2; color: #c0392b; }
.od--y { background: #fef5e7; color: #d68910; }
.od--g { background: #eafaf1; color: #1e8449; }

.c-red { color: var(--el-color-danger); font-weight: 500; }
.c-ora { color: var(--el-color-warning); font-weight: 500; }

/* ─── 各所概览 ─── */
.ov-title { font-weight: 500; font-size: 14px; }
.ov-empty { padding: 6px 0; color: var(--el-text-color-secondary); font-size: 12px; }
.ov-row {
  display: flex; align-items: center; gap: 10px; padding: 7px 16px;
  cursor: pointer; border-bottom: 1px solid var(--el-border-color-lighter); font-size: 13px;
  &:hover { background: var(--el-fill-color-light); }
}
.ov-name { font-weight: 500; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ov-cur { color: var(--el-text-color-secondary); font-size: 12px; }
.ov-go { color: var(--el-text-color-placeholder); }

.pri-sm {
  font-size: 11px; padding: 1px 6px; border-radius: 8px; font-weight: 500;
  &.pri--urgent  { color: #fff; background: var(--el-color-danger); }
  &.pri--high    { color: #fff; background: var(--el-color-warning); }
  &.pri--normal  { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.pri--low     { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}
</style>

<style lang="scss">
/* 全局：表格行高亮 */
.r--red td { background: #fef0f0 !important; }
.r--yel td { background: #fffaf0 !important; }
</style>
