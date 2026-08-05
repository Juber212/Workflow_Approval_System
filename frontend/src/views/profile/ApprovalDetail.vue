<template>
  <!-- 审批处理页 —— 顶部摘要 + 进度条 + 单栏表单 -->
  <!-- P1-34：非本人审批记录后端返回 403，渲染「无权查看」而非误导的「记录不存在」空态 -->
  <ForbiddenPage v-if="forbidden" />
  <div class="approval-detail" v-if="!forbidden" v-loading="loading">
    <el-empty v-if="!loading && !detail" description="审批记录不存在" />

    <template v-if="detail">
      <!-- ===== 顶部摘要条 ===== -->
      <TopSummary :title="`${detail.instance_name} · ${detail.node_name}`">
        <template #title-extra>
          <el-tag v-if="detail.is_end_node" type="warning" size="small" style="margin-left:8px;vertical-align:middle">终审节点</el-tag>
        </template>
        <span>审批人：<b>{{ detail.approver_name }}</b></span>
        <span v-if="detail.node_description">
          <span class="top-summary__sep">·</span>
          <span>节点说明：{{ detail.node_description }}</span>
        </span>
      </TopSummary>

      <!-- 流程进度 + 节点信息（P2-2 共享组件，终审隐藏时限/截止） -->
      <NodeInfoGrid :detail="detail" :is-end-node="detail.is_end_node" />

      <!-- 本节点文件 + 历史节点文件 + 无文件兜底（终审默认展开历史文件） -->
      <FileListView :current-node-files="detail.node_files" :history-groups="historyFileGroups" :default-expand="detail.is_end_node" />

      <!-- 校验进度 -->
      <div class="card" v-if="detail.check_progress.length > 0">
        <div class="card__header">校验进度</div>
        <div class="card__body">
          <div v-for="c in detail.check_progress" :key="c.id" class="progress-row">
            <span>{{ c.checker_name }}</span>
            <span class="status-tag" :class="checkStatusClass(c.status)">{{ checkStatusLabel(c.status) }}</span>
            <span v-if="c.round > 1" class="round-tag">#{{ c.round }}</span>
            <span v-if="c.opinion" class="opinion">「{{ c.opinion }}」</span>
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
            <span v-if="a.round > 1" class="round-tag">#{{ a.round }}</span>
            <span v-if="a.opinion" class="opinion">「{{ a.opinion }}」</span>
          </div>
        </div>
      </div>

      <!-- 操作区 -->
      <div class="card" v-if="detail.status === 'pending'">
        <div class="card__header">审批决定</div>
        <div class="card__body">
          <el-input v-model="opinion" type="textarea" :rows="2" maxlength="500" show-word-limit :placeholder="'通过可空，退回必填'" />

          <!-- 驳回目标选择（终审必选，中间节点可选） -->
          <div v-if="showRejectTarget && detail.reject_target_nodes.length > 0" class="reject-target">
            <div class="label">{{ detail.is_end_node ? '驳回目标节点（必选）' : '驳回到历史节点（可选）' }}</div>
            <el-select v-model="rejectTargetId" :placeholder="detail.is_end_node ? '选择驳回目标节点' : '可选，默认退回当前节点'" style="width:100%" clearable>
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
        {{ detail.status === 'approved' ? '已审批通过' : '已审批退回' }}
      </el-alert>
    </template>

    <!-- 签名预览弹框 -->
    <SignaturePreviewDialog
      v-if="detail"
      v-model="showSignatureDialog"
      :pdf-files="pdfFiles"
      :pdf-urls="pdfPreviewUrls"
      :auth-token="authToken()"
      :sig-url="detail.current_signature_url"
      :default-x="detail.role_signature?.x ?? detail.signature_x"
      :default-y="detail.role_signature?.y ?? detail.signature_y"
      :default-page="detail.signature_page"
      @confirm="onSignatureConfirm"
    />
  </div>
</template>

<script setup lang="ts">
/** 审批处理页 —— 审批通过/退回（终审含驳回目标选择），签批逻辑复用共享 composable（P2-2 抽取） */
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getApprovalDetail, approveApproval, rejectApproval, type ApprovalDetail } from '@/api/approval'
import { checkStatusClass, checkStatusLabel, approvalStatusClass, approvalStatusLabel } from '@/utils/labels'
import TopSummary from '@/views/flows/components/TopSummary.vue'
import NodeInfoGrid from '@/views/flows/components/NodeInfoGrid.vue'
import FileListView from '@/views/flows/components/FileListView.vue'
import SignaturePreviewDialog from '@/views/flows/components/SignaturePreviewDialog.vue'
import ForbiddenPage from '@/views/error/403.vue'
import { useDetailLoad } from '@/composables/useDetailLoad'
import { useDetailFileGrouping } from '@/composables/useDetailFileGrouping'
import { usePdfFilesForSignature } from '@/composables/usePdfFilesForSignature'
import { useSignatureDialog } from '@/composables/useSignatureDialog'

const router = useRouter()

// 加载 + 403 + 面包屑 + 路由监听（P1-34 403 语义保留）
const { loading, forbidden, detail } = useDetailLoad<ApprovalDetail>({
  loadFn: getApprovalDetail,
  breadcrumbTail: '审批处理',
})

/** 历史节点文件（按节点分组，排除当前节点） */
const { historyFileGroups } = useDetailFileGrouping(
  computed(() => detail.value?.files),
  computed(() => detail.value?.node_id),
)

// 签批弹窗（PDF 文件列表 + 弹窗状态 + 确认回调）
const { pdfFiles, pdfPreviewUrls } = usePdfFilesForSignature(computed(() => detail.value?.node_files))
const { showSignatureDialog, sigSlots, authToken, openSignatureDialog, promptUploadSignature, makeSignatureConfirm } = useSignatureDialog()
const onSignatureConfirm = makeSignatureConfirm(doApprove)

const opinion = ref('')
const rejectTargetId = ref<number | null>(null)
const showRejectTarget = ref(false)
const approving = ref(false)
const rejecting = ref(false)

async function handleApprove() {
  if (!detail.value) return
  // 终审节点无需签批，直接通过（终审只需确认文件齐全）
  // 节点要求审批人签批 → 检查签名图片
  if (detail.value.require_approver_signature && !detail.value.is_end_node) {
    if (detail.value.current_signature_url) {
      openSignatureDialog()
      return
    }
    await promptUploadSignature('该节点要求审批人签批，但您尚未上传签名图片，请先上传。')
    return
  }
  await doApprove()
}

async function doApprove() {
  if (!detail.value) return
  approving.value = true
  try {
    await approveApproval(detail.value.id, opinion.value || null, sigSlots.value)
    ElMessage.success('审批通过')
    router.push({ name: 'Profile' })
  } finally { approving.value = false }
}

/** 第一次点退回：展开驳回目标选择 */
function handleReject() {
  if (!detail.value) return
  if (!showRejectTarget.value && detail.value.reject_target_nodes.length > 0) {
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
    // 中间节点可选驳回目标，终审节点必选
    const targetId = detail.value.is_end_node ? rejectTargetId.value : (rejectTargetId.value || null)
    await rejectApproval(detail.value.id, opinion.value, targetId)
    ElMessage.success('已退回')
    router.push({ name: 'Profile' })
  } finally { rejecting.value = false }
}
</script>

<style lang="scss" scoped>
.approval-detail { /* max-width 由 AppLayout 内容区统一控制 */ }

.progress-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.opinion { color: var(--el-text-color-secondary); font-size: 12px; }
.reject-target { margin: 12px 0; }
.reject-target .label { font-size: 13px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.actions-bar { display: flex; gap: 12px; margin-top: 12px; }
</style>
