<template>
  <!-- 模板详情 —— 单列卡片布局：基础信息 → 节点配置 → 流程预览 -->
  <div class="tpl-detail" v-loading="loading">
    <el-empty v-if="!loading && !detail && !fetchError" description="模板不存在或无权访问" :image-size="60" />
    <el-empty v-if="!loading && fetchError" description="加载失败，请稍后重试" :image-size="60" />

    <template v-if="detail">
      <!-- 基础信息卡片 -->
      <el-card shadow="never" class="tpl-card">
        <template #header>
          <div class="tpl-card__header">
            <span class="tpl-card__title">基础信息</span>
            <el-button v-if="isOrgManager" type="primary" size="default" @click="$router.push(`/flows/designer/${detail.id}`)">
              编辑流程
            </el-button>
          </div>
        </template>
        <el-descriptions :column="2" border size="default">
          <el-descriptions-item label="模板名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="所属组织">{{ detail.organization_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="节点数">{{ detail.node_count }}</el-descriptions-item>
          <el-descriptions-item label="运行中项目">{{ detail.instance_count }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ detail.created_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ detail.description || '暂无描述' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 节点配置卡片 -->
      <el-card v-if="detail.nodes.length" shadow="never" class="tpl-card">
        <template #header>
          <span class="tpl-card__title">节点配置（{{ detail.nodes.length }} 个）</span>
        </template>
        <el-table :data="detail.nodes" stripe size="default" :row-class-name="nodeRowClass">
          <el-table-column prop="name" label="名称" min-width="100" />
          <el-table-column label="类型" width="80" align="center">
            <template #default="{ row }">
              <span class="node-type-dot" :class="nodeTypeClass(row)" />
              {{ nodeTypeLabel(row) }}
            </template>
          </el-table-column>
          <el-table-column label="负责人" min-width="80">
            <template #default="{ row }">
              <template v-if="!row.is_start && !row.is_end">
                {{ row.assignee_name || '未设置' }}
              </template>
              <span v-else class="text--muted">-</span>
            </template>
          </el-table-column>
          <el-table-column label="校验人" min-width="120">
            <template #default="{ row }">
              <template v-if="!row.is_start && !row.is_end && row.checkers_names?.length">
                <el-tag v-for="n in row.checkers_names" :key="n" size="small" style="margin:1px 2px">{{ n }}</el-tag>
              </template>
              <span v-else class="text--muted">{{ row.is_start || row.is_end ? '-' : '未设置' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="审批人" min-width="120">
            <template #default="{ row }">
              <template v-if="!row.is_start && !row.is_end && row.approvers_names?.length">
                <el-tag v-for="n in row.approvers_names" :key="n" size="small" type="warning" style="margin:1px 2px">{{ n }}</el-tag>
              </template>
              <span v-else class="text--muted">{{ row.is_start || row.is_end ? '-' : '未设置' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="时限" width="90" align="center">
            <template #default="{ row }">
              <template v-if="!row.is_start && !row.is_end">
                {{ row.time_limit_days ? row.time_limit_days + ' 工作日' : '不限' }}
              </template>
              <span v-else class="text--muted">-</span>
            </template>
          </el-table-column>
          <el-table-column label="需文件" width="80" align="center">
            <template #default="{ row }">
              <template v-if="!row.is_start && !row.is_end">
                <span :class="row.require_file ? 'text--yes' : 'text--muted'">{{ row.require_file ? '是' : '否' }}</span>
              </template>
              <span v-else class="text--muted">-</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 流程预览卡片 -->
      <el-card v-if="flowChain.length > 1" shadow="never" class="tpl-card">
        <template #header>
          <span class="tpl-card__title">流程预览</span>
        </template>
        <div class="flow-chain">
          <template v-for="(node, idx) in flowChain" :key="node.id">
            <div class="flow-chain__node" :class="{ 'is-start': node.is_start, 'is-end': node.is_end }">
              <span class="flow-chain__dot" />
              <span class="flow-chain__label">{{ node.name }}</span>
            </div>
            <div v-if="idx < flowChain.length - 1" class="flow-chain__arrow">›</div>
          </template>
        </div>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
/** 模板详情页 —— 基础信息 + 节点配置 + 流程预览链 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getTemplateDetail, type TemplateDetail, type TemplateNodeItem } from '@/api/template'
import { useUserStore } from '@/stores/user'
import { useBreadcrumb } from '@/composables/useBreadcrumb'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { setBreadcrumb } = useBreadcrumb()
const loading = ref(false)
const detail = ref<TemplateDetail | null>(null)

/** 当前用户是否为本模板所属组织的所长 */
const isOrgManager = computed(() => {
  if (!detail.value || !userStore.isManager) return false
  return userStore.userInfo?.organization_id === detail.value.organization_id
})

// ========== 流程链：从边数据构建节点有序列表 ==========
const flowChain = computed(() => {
  if (!detail.value) return []
  const { nodes, edges } = detail.value
  if (!edges.length || nodes.length < 2) return []

  // 构建邻接表
  const nextMap = new Map<number, number>()
  for (const e of edges) {
    nextMap.set(e.source_node_id, e.target_node_id)
  }

  // 从开始节点出发，沿链表遍历
  const startNode = nodes.find(n => n.is_start)
  if (!startNode) return []

  const chain: TemplateNodeItem[] = []
  const visited = new Set<number>()
  let currentId: number | undefined = startNode.id

  while (currentId !== undefined && !visited.has(currentId)) {
    visited.add(currentId)
    const node = nodes.find(n => n.id === currentId)
    if (!node) break
    chain.push(node)
    currentId = nextMap.get(currentId)
  }

  return chain
})

// ========== 节点类型辅助 ==========
function nodeTypeLabel(node: TemplateNodeItem): string {
  if (node.is_start) return '开始'
  if (node.is_end) return '结束'
  return '工作'
}

function nodeTypeClass(node: TemplateNodeItem): string {
  if (node.is_start) return 'nd--start'
  if (node.is_end) return 'nd--end'
  return 'nd--work'
}

/** 行样式：开始/结束节点半透明淡化 */
function nodeRowClass({ row }: { row: TemplateNodeItem }): string {
  return row.is_start || row.is_end ? 'row--sys' : ''
}

function formatTime(t: string | null): string {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

// ========== 初始化 ==========
const fetchError = ref(false)

async function fetchDetail() {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  fetchError.value = false
  try {
    detail.value = await getTemplateDetail(id)
    if (detail.value) {
      setBreadcrumb([
        { label: '首页', to: '/dashboard' },
        { label: '项目管理', to: '/flows' },
        { label: detail.value.organization_name || '未知组织', to: `/flows/organization/${detail.value.organization_id}?tab=template` },
        { label: detail.value.name },
      ])
    }
  } catch {
    fetchError.value = true
  } finally { loading.value = false }
}

onMounted(fetchDetail)
</script>

<style lang="scss" scoped>
.tpl-detail {
  /* max-width 由 AppLayout 控制 */
}

.tpl-card {
  margin-bottom: 16px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-light);
}

.tpl-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tpl-card__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

/* ========== 节点类型圆点 ========== */
.node-type-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
  &.nd--start { background: var(--el-color-success); }
  &.nd--end   { background: var(--el-color-warning); }
  &.nd--work  { background: var(--el-color-primary); }
}

/* ========== 系统节点行淡化 ========== */
:deep(.row--sys) {
  background: #fafafa !important;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}

.text--muted { color: var(--el-text-color-placeholder); font-size: 13px; }
.text--yes   { color: var(--el-color-success); font-weight: 500; }

/* ========== 流程预览链 ========== */
.flow-chain {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0;
  padding: 8px 0;
}

.flow-chain__node {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  font-size: 13px; font-weight: 500;
  color: var(--el-text-color-primary);
  transition: background 0.15s;

  &.is-start { background: var(--el-color-success-light-9); color: #1e8449; }
  &.is-end   { background: var(--el-color-warning-light-9); color: #b87333; }
}

.flow-chain__dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--el-color-primary);
  flex-shrink: 0;
  .is-start & { background: var(--el-color-success); }
  .is-end   & { background: var(--el-color-warning); }
}

.flow-chain__arrow {
  font-size: 18px;
  color: var(--el-text-color-placeholder);
  margin: 0 4px;
  font-weight: 300;
  user-select: none;
}
</style>
