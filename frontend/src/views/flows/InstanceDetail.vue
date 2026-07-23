<template>
  <!-- 实例详情页 —— 基本信息 + 进度条 + 节点卡片 + 操作日志（项目/方案共用） -->
  <div class="instance-detail" v-loading="loading">
    <!-- 空数据 -->
    <el-empty v-if="!loading && !detail" :description="`${typeLabel}不存在或无权访问`" :image-size="60" />

    <template v-if="detail">
      <!-- 粘性头部：基本信息 + 进度 + 操作 -->
      <InstanceInfo
        :detail="detail"
        :is-initiator="isInitiator"
        @supplement="handleSupplement"
        @change-priority="handleChangePriority"
        @terminate="handleTerminate"
      />

      <!-- ===== 方案：卡片平铺布局 ===== -->
      <template v-if="isProposal">
        <div class="card">
          <div class="card__header">
            <h3 class="card__title">方案内容</h3>
          </div>
          <div class="card__body">
            <div v-for="node in displayNodes" :key="node.id" class="proposal-node">
              <!-- 文件（按文件夹分组） -->
              <div class="proposal-block">
                <template v-if="getNodeFolderGroups(node).length > 0">
                  <div v-for="group in getNodeFolderGroups(node)" :key="group.name" class="proposal-folder">
                    <div class="proposal-folder__name">📁 {{ group.name }}（{{ group.files.length }}）</div>
                    <div v-if="group.files.length === 0" class="proposal-empty">暂未上传文件</div>
                    <div v-else class="proposal-file-list">
                      <div v-for="f in group.files" :key="f.id" class="proposal-file-row">
                        <el-icon :size="14"><Document /></el-icon>
                        <span class="proposal-file-name" :title="f.original_name">{{ f.original_name }}</span>
                        <span v-if="f.round > 1" class="proposal-file-round">第{{ f.round }}轮</span>
                        <span class="proposal-file-meta">{{ f.uploader_name }} · {{ formatFileSize(f.file_size) }}</span>
                        <el-button text type="primary" size="small" @click="handlePreview(f.id)">查看</el-button>
                        <el-button text type="primary" size="small" @click="handleDownload(f.id)">下载</el-button>
                      </div>
                    </div>
                  </div>
                </template>
                <div v-else class="proposal-empty">暂未上传文件</div>
              </div>

              <!-- 审批记录 -->
              <div class="proposal-block">
                <div class="proposal-block__title">📝 审批记录（{{ node.approvals.length }}）</div>
                <div v-if="node.approvals.length === 0" class="proposal-empty">暂无</div>
                <div v-else class="proposal-record-list">
                  <div
                    v-for="a in node.approvals"
                    :key="a.id"
                    class="proposal-record"
                    :class="'proposal-record--' + (a.status || '').toLowerCase()"
                  >
                    <span class="proposal-record-user">{{ a.approver_name }}</span>
                    <span class="proposal-record-status" :class="a.status === 'approved' ? 'text-success' : 'text-danger'">
                      {{ a.status === 'approved' ? '已通过' : a.status === 'rejected' ? '已驳回' : a.status }}
                    </span>
                    <span v-if="a.round > 1" class="proposal-record-round">#{{ a.round }}</span>
                    <el-tag v-if="a.signature_applied" size="small" type="success" effect="plain">已签名</el-tag>
                    <span v-if="a.opinion" class="proposal-record-opinion">「{{ a.opinion }}」</span>
                    <span v-if="a.decided_at" class="proposal-record-time">{{ formatTime(a.decided_at) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="section-header">
          <h3 class="section-title">流程节点</h3>
          <el-button text size="small" @click="toggleExpandAll">{{ expandLabel }}</el-button>
        </div>
        <NodeCard
          v-for="node in displayNodes"
          :key="node.id"
          :node="node"
          :is-initiator="isInitiator"
          :instance-status="detail.status"
          :force-expand="expandAll"
          @change-personnel="handleChangePersonnel"
          @supplement="handleSupplement"
        />
      </template>

      <!-- 实例补充说明 -->
      <div class="card" v-if="detail.description">
        <div class="card__header">
          <h3 class="card__title">补充说明</h3>
        </div>
        <div class="card__body">
          <p class="desc-text">{{ detail.description }}</p>
        </div>
      </div>

      <!-- 操作日志时间线 -->
      <OperationTimeline
        :logs="detail.logs?.items || []"
        :total="detail.logs?.total || 0"
        :is-proposal="isProposal"
      />

      <!-- 终止流程确认弹窗 -->
      <TerminateDialog
        v-if="detail"
        v-model="showTerminateDialog"
        :instance-id="detail.id"
        :instance-name="detail.name"
        :instance-status="detail.status"
        :is-proposal="isProposal"
        @terminated="handleTerminated"
      />

      <!-- 优先级修改弹窗 -->
      <PriorityEditDialog
        v-if="detail"
        v-model="showPriorityDialog"
        :instance-id="detail.id"
        :current-priority="detail.priority"
        @changed="handlePriorityChanged"
      />

      <!-- 修改人员弹窗 -->
      <ChangePersonnelDialog
        v-if="detail"
        v-model="showPersonnelDialog"
        :instance-id="detail.id"
        :node="selectedNode"
        @success="handlePersonnelChanged"
      />

      <!-- 补交文件弹窗 -->
      <SupplementFileDialog
        v-if="detail"
        v-model="showSupplementDialog"
        :instance-id="detail.id"
        :nodes="detail.nodes"
        :preselected-node-id="supplementPreselectedNodeId"
        @success="handleSupplementSuccess"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
/** 实例详情页 —— 项目/方案共用，根据 template_type 切换面包屑和文案 */
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getInstanceDetail, type InstanceDetailResponse, type DetailNodeInfo, type NodeFileBrief } from '@/api/instance'
import { previewFile, downloadFile } from '@/api/task'
import { useUserStore } from '@/stores/user'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import { formatTime, formatFileSize } from '@/utils/format'
import { Document } from '@element-plus/icons-vue'
import InstanceInfo from './components/InstanceInfo.vue'
import NodeCard from './components/NodeCard.vue'
import OperationTimeline from './components/OperationTimeline.vue'
import TerminateDialog from './components/TerminateDialog.vue'
import PriorityEditDialog from './components/PriorityEditDialog.vue'
import ChangePersonnelDialog from './components/ChangePersonnelDialog.vue'
import SupplementFileDialog from './components/SupplementFileDialog.vue'

const route = useRoute()
const userStore = useUserStore()
const { setBreadcrumb } = useBreadcrumb()

// ========== 状态 ==========
const loading = ref(false)
const detail = ref<InstanceDetailResponse | null>(null)
/** 全局展开控制：null=默认，true=全部展开，false=全部折叠 */
const expandAll = ref<boolean | null>(null)
/** 按钮文字 */
const expandLabel = computed(() => expandAll.value === true ? '折叠全部' : '展开全部')
const showTerminateDialog = ref(false)
const showPriorityDialog = ref(false)
const showPersonnelDialog = ref(false)
const showSupplementDialog = ref(false)
const supplementPreselectedNodeId = ref<number | undefined>(undefined)
const selectedNode = ref<DetailNodeInfo | null>(null)

/** 当前用户是否为发起人 */
const isInitiator = computed(() => {
  if (!detail.value || !userStore.userInfo) return false
  return detail.value.initiator_id === userStore.userInfo.id
})

/** 是否为方案实例 */
const isProposal = computed(() => detail.value?.template_type === 'proposal')
/** 类型中文标签 */
const typeLabel = computed(() => isProposal.value ? '方案' : '项目')
/** 显示的节点列表：方案排除开始/结束节点，项目显示全部 */
const displayNodes = computed(() => {
  if (!detail.value) return []
  if (isProposal.value) {
    return detail.value.nodes.filter(n => !n.is_start && !n.is_end)
  }
  return detail.value.nodes
})

// ========== 生命周期 ==========
onMounted(() => {
  fetchDetail()
})

// ========== 数据加载 ==========
async function fetchDetail() {
  const id = Number(route.params.id)
  if (!id) return

  loading.value = true
  try {
    detail.value = await getInstanceDetail(id)
    // 方案详情默认全部展开
    if (isProposal.value) {
      expandAll.value = true
    }
    // 面包屑：根据模板类型区分项目/方案
    if (detail.value) {
      if (isProposal.value) {
        setBreadcrumb([
          { label: '首页', to: '/dashboard' },
          { label: '方案管理', to: '/proposals' },
          { label: detail.value.organization_name, to: `/proposals/organization/${detail.value.organization_id}` },
          { label: detail.value.name },
        ])
      } else {
        setBreadcrumb([
          { label: '首页', to: '/dashboard' },
          { label: '项目管理', to: '/flows' },
          { label: detail.value.organization_name, to: `/flows/organization/${detail.value.organization_id}` },
          { label: detail.value.name },
        ])
      }
    }
  } catch (err: any) {
    const msg = err?.response?.data?.message || err?.message || '加载实例详情失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

// ========== 操作处理 ==========
/** 一键展开/折叠所有节点 */
function toggleExpandAll() {
  if (expandAll.value === true) {
    expandAll.value = false  // 当前全部展开 → 全部折叠
  } else {
    expandAll.value = true   // 当前默认或全部折叠 → 全部展开
  }
}

/** 打开补交文件弹窗：全局入口不传 nodeId，节点卡片入口传入 nodeId */
function handleSupplement(nodeId?: number) {
  supplementPreselectedNodeId.value = nodeId
  showSupplementDialog.value = true
}

/** 补交成功后刷新详情 */
function handleSupplementSuccess() {
  fetchDetail()
}

/** 打开优先级修改弹窗 */
function handleChangePriority() {
  showPriorityDialog.value = true
}

/** 优先级修改成功后刷新 */
function handlePriorityChanged() {
  fetchDetail()
}

/** 打开终止确认弹窗 */
function handleTerminate() {
  showTerminateDialog.value = true
}

/** 终止成功后刷新详情 */
function handleTerminated() {
  fetchDetail()
}

/** 打开修改人员弹窗 */
function handleChangePersonnel(nodeId: number) {
  if (!detail.value) return
  const node = detail.value.nodes.find(n => n.id === nodeId)
  if (node) {
    selectedNode.value = node
    showPersonnelDialog.value = true
  }
}

/** 人员修改成功后刷新详情 */
function handlePersonnelChanged() {
  fetchDetail()
}

// ========== 方案平铺视图辅助 ==========
/** 获取节点的普通文件（排除补交） */
function getNodeNormalFiles(node: DetailNodeInfo): NodeFileBrief[] {
  return node.files.filter(f => (f.upload_type || '').toLowerCase() !== 'supplement')
}

/** 按文件夹分组节点文件 */
function getNodeFolderGroups(node: DetailNodeInfo): { name: string; files: NodeFileBrief[] }[] {
  const normalFiles = getNodeNormalFiles(node)
  if (normalFiles.length === 0) return []
  const groups: { name: string; files: NodeFileBrief[] }[] = []
  const seen = new Map<string, number>()
  for (const f of normalFiles) {
    const key = f.folder_name || '方案'
    if (seen.has(key)) {
      groups[seen.get(key)!].files.push(f)
    } else {
      seen.set(key, groups.length)
      groups.push({ name: key, files: [f] })
    }
  }
  groups.sort((a, b) => {
    if (a.name === '方案') return 1
    if (b.name === '方案') return -1
    return 0
  })
  return groups
}

// 时间/文件大小 —— 统一从 @/utils/format 导入

function handlePreview(fileId: number) {
  previewFile(fileId)
}

function handleDownload(fileId: number) {
  downloadFile(fileId)
}
</script>

<style lang="scss" scoped>
.instance-detail {
  /* max-width 由 AppLayout 内容区统一控制 */
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0;
}

.desc-text {
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.7;
  margin: 0;
  white-space: pre-wrap;
}

// ========== 方案平铺布局 ==========
.proposal-node {
  margin-bottom: 24px;

  &__name {
    font-size: 15px;
    font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--el-border-color-light);
  }
}

.proposal-block {
  margin-bottom: 14px;

  &__title {
    font-size: 12px;
    font-weight: 600;
    color: var(--el-text-color-secondary);
    margin-bottom: 6px;
  }
}

.proposal-folder {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;

  &__name {
    font-size: 12px;
    font-weight: 600;
    color: var(--el-text-color-secondary);
    margin-bottom: 6px;
  }
}

.proposal-file-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.proposal-file-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px;
  border-radius: 4px;
  font-size: 13px;

  &:hover { background: var(--el-fill-color-light); }
}

.proposal-file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.proposal-file-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}

.proposal-file-round {
  font-size: 11px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  padding: 0 5px;
  border-radius: 999px;
  flex-shrink: 0;
}

.proposal-empty {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  padding: 8px 0;
}

.proposal-record-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.proposal-record {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 13px;
  border-left: 3px solid var(--el-border-color);

  &--approved { border-left-color: var(--el-color-success); background: var(--el-color-success-light-9); }
  &--rejected { border-left-color: var(--el-color-danger); background: var(--el-color-danger-light-9); }

  &-user { font-weight: 500; color: var(--el-text-color-primary); }
  &-status {
    font-size: 12px;
    font-weight: 500;
    &.text-success { color: var(--el-color-success); }
    &.text-danger { color: var(--el-color-danger); }
  }
  &-round {
    font-size: 11px;
    color: var(--el-text-color-placeholder);
    background: var(--el-fill-color);
    padding: 0 5px;
    border-radius: 999px;
  }
  &-opinion { font-size: 12px; color: var(--el-text-color-secondary); }
  &-time { font-size: 11px; color: var(--el-text-color-placeholder); margin-left: auto; }
}
</style>
