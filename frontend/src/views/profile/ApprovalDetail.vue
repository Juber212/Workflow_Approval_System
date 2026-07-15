<template>
  <!-- 审批处理页 —— 两栏：左栏审批表单 / 右栏流程上下文 -->
  <div class="approval-detail" v-loading="loading">
    <div class="page-breadcrumb">
      <router-link to="/profile">个人中心</router-link><span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-current">审批处理{{ detail ? ' · ' + detail.instance_name : '' }}</span>
    </div>

    <el-empty v-if="!loading && !detail" description="审批记录不存在" />

    <template v-if="detail">
      <div class="detail-layout">
        <!-- ===== 左栏：审批处理表单 ===== -->
        <div class="detail-layout__main">
          <div class="info-card">
            <h2>{{ detail.instance_name }} · {{ detail.node_name }}
              <el-tag v-if="detail.is_end_node" type="warning" size="small">终审节点</el-tag>
            </h2>
            <div class="info-grid">
              <div><span class="k">审批人</span><span class="v">{{ detail.approver_name }}</span></div>
              <div><span class="k">节点说明</span><span class="v">{{ detail.node_description || '无' }}</span></div>
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
        </div>

        <!-- ===== 右栏：流程上下文 ===== -->
        <div class="detail-layout__side">
          <div class="side-card">
            <h3 class="side-card__title">流程进度</h3>
            <ProgressBar v-if="detail.nodes.length > 0" :nodes="detail.nodes" />
          </div>

          <div class="side-card">
            <div class="side-info">
              <div class="side-info__row">
                <span class="k">发起人</span>
                <span class="v">{{ detail.initiator_name }}</span>
              </div>
              <div class="side-info__row">
                <span class="k">优先级</span>
                <span class="v">
                  <span class="pri-tag" :class="'pri--' + detail.priority">{{ priLabel(detail.priority) }}</span>
                </span>
              </div>
              <div class="side-info__row">
                <span class="k">状态</span>
                <span class="v">
                  <span class="status-tag" :class="instStatusClass(detail.instance_status)">{{ instStatusLabel(detail.instance_status) }}</span>
                </span>
              </div>
              <div class="side-info__row">
                <span class="k">节点进度</span>
                <span class="v">{{ detail.current_node_index }} / {{ detail.total_nodes }}</span>
              </div>
            </div>
          </div>

          <router-link :to="`/flows/instances/${detail.instance_id}`" class="side-link">
            <el-button type="primary" plain style="width:100%">查看完整流程 →</el-button>
          </router-link>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getApprovalDetail, approveApproval, rejectApproval, type ApprovalDetail } from '@/api/approval'
import { previewFile, downloadFile } from '@/api/task'
import ProgressBar from '@/views/flows/components/ProgressBar.vue'

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
.approval-detail { max-width: 1280px; margin: 0 auto; }

/* 两栏布局 */
.detail-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;

  &__main {
    flex: 0 0 58%;
    min-width: 0;
  }

  &__side {
    flex: 1;
    min-width: 280px;
    position: sticky;
    top: 20px;
  }
}

/* 右侧卡片 */
.side-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 14px;

  &__title {
    font-size: 14px;
    font-weight: 600;
    margin: 0 0 12px;
    color: var(--el-text-color-primary);
  }
}

.side-info {
  &__row {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    font-size: 13px;

    &:last-child { margin-bottom: 0; }

    .k {
      color: var(--el-text-color-secondary);
      width: 60px;
      flex-shrink: 0;
    }
    .v {
      color: var(--el-text-color-primary);
      font-weight: 500;
    }
  }
}

.side-link {
  display: block;
  text-decoration: none;
}

/* 原有样式 */
.info-card { background: var(--el-bg-color); border: 1px solid var(--el-border-color-light); border-radius: 10px; padding: 20px; margin-bottom: 16px; }
.info-card h2 { font-size: 18px; margin: 0 0 8px; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 14px; }
.info-grid .k { color: var(--el-text-color-secondary); margin-right: 8px; }
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
