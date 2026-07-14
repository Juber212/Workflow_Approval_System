<template>
  <!-- 审批处理页 —— 文件查看 + 审批进度 + 通过/退回/总驳回（PRD §10） -->
  <div class="approval-detail" v-loading="loading">
    <div class="page-breadcrumb">
      <router-link to="/profile">个人中心</router-link><span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-current">审批处理{{ detail ? ' · ' + detail.instance_name : '' }}</span>
    </div>

    <el-empty v-if="!loading && !detail" description="审批记录不存在" />

    <template v-if="detail">
      <div class="info-card">
        <h2>{{ detail.instance_name }} · {{ detail.node_name }}
          <el-tag v-if="detail.is_end_node" type="warning" size="small">终审节点</el-tag>
        </h2>
        <div class="info-grid">
          <div><span class="k">审批人</span><span class="v">{{ detail.approver_name }}</span></div>
          <div><span class="k">节点说明</span><span class="v">{{ detail.node_description || '无' }}</span></div>
        </div>
      </div>

      <!-- 文件 -->
      <div class="card">
        <div class="card__header">节点文件（{{ detail.files.length }}）</div>
        <div class="card__body">
          <div v-if="detail.files.length === 0" class="empty-hint">暂无文件</div>
          <div v-for="f in detail.files" :key="f.id" class="file-row">
            <span>{{ f.original_name }}</span><span class="file-size">{{ formatSize(f.file_size) }}</span>
          </div>
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
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getApprovalDetail, approveApproval, rejectApproval, type ApprovalDetail } from '@/api/approval'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref<ApprovalDetail | null>(null)
const opinion = ref('')
const rejectTargetId = ref<number | null>(null)
const showRejectTarget = ref(false)
const approving = ref(false)
const rejecting = ref(false)

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
function approvalStatusClass(s: string) { return s === 'approved' ? 'status-tag--completed' : s === 'rejected' ? 'status-tag--terminated' : 'status-tag--running' }
function approvalStatusLabel(s: string) { const m: Record<string, string> = { pending: '待审批', approved: '已通过', rejected: '已退回' }; return m[s] || s }
</script>

<style lang="scss" scoped>
.approval-detail { max-width: 900px; margin: 0 auto; }
.info-card { background: var(--el-bg-color); border: 1px solid var(--el-border-color-light); border-radius: 10px; padding: 20px; margin-bottom: 16px; }
.info-card h2 { font-size: 18px; margin: 0 0 8px; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 14px; }
.info-grid .k { color: var(--el-text-color-secondary); margin-right: 8px; }
.file-row { display: flex; align-items: center; gap: 10px; padding: 4px 8px; background: var(--el-bg-color-page); border-radius: 4px; margin-bottom: 4px; font-size: 13px; }
.file-size { color: var(--el-text-color-secondary); font-size: 12px; }
.empty-hint { color: var(--el-text-color-placeholder); font-size: 13px; text-align: center; padding: 12px; }
.progress-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.opinion { color: var(--el-text-color-secondary); font-size: 12px; }
.reject-target { margin: 12px 0; }
.reject-target .label { font-size: 13px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.actions-bar { display: flex; gap: 12px; margin-top: 12px; }
</style>
