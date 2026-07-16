<template>
  <!-- 审批处理页 —— 顶部摘要 + 进度条 + 单栏表单 -->
  <div class="approval-detail" v-loading="loading">
    <el-empty v-if="!loading && !detail" description="审批记录不存在" />

    <template v-if="detail">
      <!-- ===== 顶部摘要条 ===== -->
      <div class="top-summary">
        <h2 class="top-summary__title">
          {{ detail.instance_name }} · {{ detail.node_name }}
          <el-tag v-if="detail.is_end_node" type="warning" size="small" style="margin-left:8px;vertical-align:middle">终审节点</el-tag>
        </h2>
        <div class="top-summary__meta">
          <span>审批人：<b>{{ detail.approver_name }}</b></span>
          <span class="top-summary__sep">·</span>
          <span v-if="detail.node_description">节点说明：{{ detail.node_description }}</span>
        </div>
      </div>

      <!-- ===== 流程进度条 ===== -->
      <div class="card">
        <div class="card__header">
          <span class="card__title">流程进度</span>
          <router-link :to="`/flows/instances/${detail.instance_id}`" class="view-flow-link">查看完整流程 →</router-link>
        </div>
        <div class="card__body" style="padding:16px 20px">
          <ProgressBar v-if="detail.nodes.length > 0" :nodes="detail.nodes" />
          <div v-else class="empty-hint">暂无节点数据</div>
        </div>
      </div>

      <!-- 节点信息 -->
      <div class="card">
        <div class="card__header">节点信息</div>
        <div class="card__body">
          <div class="info-grid">
            <div class="info-grid__item">
              <div class="k">发起人</div>
              <div class="v">{{ detail.initiator_name }}</div>
            </div>
            <div class="info-grid__item">
              <div class="k">优先级</div>
              <div class="v">
                <span class="pri-tag" :class="'pri--' + detail.priority">{{ priLabel(detail.priority) }}</span>
              </div>
            </div>
            <div class="info-grid__item">
              <div class="k">流程状态</div>
              <div class="v">
                <span class="status-tag" :class="instStatusClass(detail.instance_status)">{{ instStatusLabel(detail.instance_status) }}</span>
              </div>
            </div>
            <div class="info-grid__item">
              <div class="k">节点进度</div>
              <div class="v">{{ detail.current_node_index }} / {{ detail.total_nodes }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 文件（按节点分组） -->
      <div class="card">
        <div class="card__header">{{ detail.is_end_node ? '流程全部文件' : '节点文件' }}（{{ detail.files.length }}）</div>
        <div class="card__body">
          <div v-if="detail.files.length === 0" class="empty-hint">暂无文件</div>
          <template v-else>
            <!-- 终审按节点分组；普通审批直接列 -->
            <template v-if="detail.is_end_node">
              <div v-for="group in fileGroups" :key="group.nodeKey" class="file-group">
                <div class="file-group__title">{{ group.nodeName }}</div>
                <div v-for="f in group.files" :key="f.id" class="file-row">
                  <span>{{ f.original_name }}</span><span class="file-size">{{ formatSize(f.file_size) }}</span>
                  <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
                  <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
                </div>
              </div>
            </template>
            <template v-else>
              <div v-for="f in detail.files" :key="f.id" class="file-row">
                <span>{{ f.original_name }}</span><span class="file-size">{{ formatSize(f.file_size) }}</span>
                <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
                <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
              </div>
            </template>
          </template>
        </div>
      </div>

      <!-- 校验进度 -->
      <div class="card" v-if="detail.check_progress.length > 0">
        <div class="card__header">校验进度</div>
        <div class="card__body">
          <div v-for="c in detail.check_progress" :key="c.id" class="progress-row">
            <span>{{ c.checker_name }}</span>
            <span class="status-tag" :class="c.status === 'passed' ? 'status-tag--completed' : ''">{{ c.status }}</span>
          </div>
        </div>
      </div>

      <!-- 审批进度 -->
      <div class="card" v-if="detail.approval_progress.length > 0">
        <div class="card__header">审批进度</div>
        <div class="card__body">
          <div v-for="a in detail.approval_progress" :key="a.id" class="progress-row">
            <span>{{ a.approver_name }}</span>
            <span class="status-tag" :class="approvalStatusClass(a.status)">{{ approvalStatusLabel(a.status) }}</span>
            <el-tag v-if="a.signature_applied" size="small" type="success" effect="plain">已签名</el-tag>
            <span v-if="a.opinion" class="opinion">「{{ a.opinion }}」</span>
          </div>
        </div>
      </div>

      <!-- 操作区 -->
      <div class="card" v-if="detail.status === 'pending'">
        <div class="card__header">审批决定</div>
        <div class="card__body">
          <el-input v-model="opinion" type="textarea" :rows="2" maxlength="500" show-word-limit :placeholder="'通过可空，退回必填'" />

          <!-- 终审总驳回目标选择 -->
          <div v-if="detail.is_end_node && showRejectTarget" class="reject-target">
            <div class="label">驳回目标节点（必选）</div>
            <el-select v-model="rejectTargetId" placeholder="选择驳回目标节点" style="width:100%">
              <el-option v-for="n in detail.reject_target_nodes" :key="n.id" :label="`${n.name}（排序${n.sort_order}）`" :value="n.id" />
            </el-select>
          </div>

          <div class="actions-bar">
            <el-button type="success" size="large" :loading="approving" @click="handleApprove">审批通过</el-button>
            <el-button type="danger" size="large" :loading="rejecting" @click="handleReject">审批退回</el-button>
          </div>
        </div>
      </div>
      <el-alert v-else :type="detail.status === 'approved' ? 'success' : 'warning'" :closable="false" show-icon>
        {{ detail.status === 'approved' ? '已审批通过' + (detail.signature_applied ? '（已签名）' : '') : '已审批退回' }}
      </el-alert>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getApprovalDetail, approveApproval, rejectApproval, type ApprovalDetail } from '@/api/approval'
import { previewFile, downloadFile } from '@/api/task'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import ProgressBar from '@/views/flows/components/ProgressBar.vue'

const { setBreadcrumb } = useBreadcrumb()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref<ApprovalDetail | null>(null)
const opinion = ref('')
const rejectTargetId = ref<number | null>(null)
const showRejectTarget = ref(false)
const approving = ref(false)
const rejecting = ref(false)

/** 终审：按节点分组文件 */
interface FileItem { id: number; node_id: number | null; node_name: string; original_name: string; file_size: number | null }
const fileGroups = computed(() => {
  if (!detail.value) return []
  const map = new Map<string, { nodeKey: string; nodeName: string; files: FileItem[] }>()
  for (const f of detail.value.files as FileItem[]) {
    const key = f.node_id ? String(f.node_id) : '__none__'
    const name = f.node_name || '未关联节点'
    if (!map.has(key)) map.set(key, { nodeKey: key, nodeName: name, files: [] })
    map.get(key)!.files.push(f)
  }
  return [...map.values()]
})

onMounted(async () => {
  setBreadcrumb([
    { label: '首页', to: '/dashboard' },
    { label: '个人中心', to: '/profile' },
    { label: '审批处理' },
  ])
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try { detail.value = await getApprovalDetail(id) } finally { loading.value = false }
})

async function handleApprove() {
  if (!detail.value) return
  approving.value = true
  try {
    await approveApproval(detail.value.id, opinion.value || null)
    ElMessage.success('审批通过')
    router.push('/profile')
  } finally { approving.value = false }
}

/** 第一次点退回：如果是终审节点则弹出目标选择 */
function handleReject() {
  if (!detail.value) return
  if (detail.value.is_end_node && !showRejectTarget.value) {
    showRejectTarget.value = true
    return
  }
  doReject()
}

async function doReject() {
  if (!detail.value) return
  if (!opinion.value.trim()) { ElMessage.error('退回必须填写意见'); return }
  if (detail.value.is_end_node && !rejectTargetId.value) { ElMessage.error('请选择驳回目标节点'); return }

  rejecting.value = true
  try {
    await rejectApproval(detail.value.id, opinion.value, detail.value.is_end_node ? rejectTargetId.value : null)
    ElMessage.success('已退回')
    router.push('/profile')
  } finally { rejecting.value = false }
}

function formatSize(b: number | null) { if (!b) return ''; return b < 1024 ? b + 'B' : b < 1048576 ? (b / 1024).toFixed(1) + 'KB' : (b / 1048576).toFixed(1) + 'MB' }
function priLabel(p: string) { const m: Record<string, string> = { urgent: '紧急', high: '高', normal: '普通', low: '低' }; return m[p] || p }
function instStatusClass(s: string) { const m: Record<string, string> = { running: 'status-tag--running', completed: 'status-tag--completed', terminated: 'status-tag--terminated' }; return m[s] || '' }
function instStatusLabel(s: string) { const m: Record<string, string> = { running: '运行中', completed: '已完成', terminated: '已终止' }; return m[s] || s }
function approvalStatusClass(s: string) { return s === 'approved' ? 'status-tag--completed' : s === 'rejected' ? 'status-tag--terminated' : 'status-tag--running' }
function approvalStatusLabel(s: string) { const m: Record<string, string> = { pending: '待审批', approved: '已通过', rejected: '已退回' }; return m[s] || s }
</script>

<style lang="scss" scoped>
.approval-detail { /* max-width 由 AppLayout 内容区统一控制 */ }

/* ===== 顶部摘要条 ===== */
.top-summary {
  background: #fff;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 16px;

  &__title {
    font-size: 20px; font-weight: 600;
    color: var(--el-text-color-primary);
    margin: 0 0 8px;
  }

  &__meta {
    display: flex; align-items: center; gap: 4px;
    font-size: 13px; color: var(--el-text-color-secondary);
    flex-wrap: wrap;
    b { color: var(--el-text-color-primary); }
  }

  &__sep {
    color: var(--el-text-color-placeholder);
    margin: 0 4px;
  }
}

.view-flow-link {
  font-size: 13px; color: var(--el-color-primary); text-decoration: none;
  font-weight: 400;
  &:hover { text-decoration: underline; }
}

.info-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 14px;
  .k { color: var(--el-text-color-secondary); margin-bottom: 2px; font-size: 12px; }
  .v { color: var(--el-text-color-primary); font-weight: 500; }
}

.file-row { display: flex; align-items: center; gap: 10px; padding: 4px 8px; background: var(--el-bg-color-page); border-radius: 4px; margin-bottom: 4px; font-size: 13px; }
.file-size { color: var(--el-text-color-secondary); font-size: 12px; }
.empty-hint { color: var(--el-text-color-placeholder); font-size: 13px; text-align: center; padding: 12px; }
.file-group { margin-bottom: 12px; }
.file-group__title { font-size: 12px; font-weight: 600; color: var(--el-text-color-secondary); padding: 4px 8px; background: var(--el-fill-color); border-radius: 4px; margin-bottom: 4px; }
.file-group .file-row { padding-left: 8px; }
.progress-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.opinion { color: var(--el-text-color-secondary); font-size: 12px; }
.reject-target { margin: 12px 0; }
.reject-target .label { font-size: 13px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.actions-bar { display: flex; gap: 12px; margin-top: 12px; }

.pri-tag {
  font-size: 12px; font-weight: 500; padding: 1px 6px; border-radius: 8px;
  &.pri--urgent { color: #fff; background: var(--el-color-danger); }
  &.pri--high { color: #fff; background: var(--el-color-warning); }
  &.pri--normal { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.pri--low { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}
</style>
