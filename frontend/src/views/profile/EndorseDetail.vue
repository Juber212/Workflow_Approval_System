<template>
  <!-- 批准处理页 —— 难度4级时的最终审核 -->
  <!-- P1-34：非本人批准记录后端返回 403，渲染「无权查看」而非误导的「记录不存在」空态 -->
  <ForbiddenPage v-if="forbidden" />
  <div class="endorse-detail" v-if="!forbidden" v-loading="loading">
    <el-empty v-if="!loading && !detail" description="批准记录不存在" />

    <template v-if="detail">
      <!-- ===== 顶部摘要条 ===== -->
      <TopSummary :title="`${detail.instance_name} · ${detail.node_name}`">
        <template #title-extra>
          <el-tag type="danger" size="small" style="margin-left:8px;vertical-align:middle">难度{{ detail.difficulty }}级 · 批准</el-tag>
        </template>
        <span>批准人：<b>{{ detail.endorser_name }}</b></span>
      </TopSummary>

      <!-- 流程进度 + 节点信息（P2-2 共享组件） -->
      <NodeInfoGrid :detail="detail" />

      <!-- 流程全部文件（按节点分组，批准人可完整掌握上下文） -->
      <FileListView :current-node-files="detail.node_files" :history-groups="historyFileGroups" empty-title="流程文件" />

      <!-- 校验进度（已完成，只读） -->
      <div class="card" v-if="detail.checks.length > 0">
        <div class="card__header">校验进度</div>
        <div class="card__body">
          <div v-for="c in detail.checks" :key="c.id" class="progress-row">
            <span>{{ c.checker_name }}</span>
            <span class="status-tag" :class="checkStatusClass(c.status)">{{ checkStatusLabel(c.status) }}</span>
            <span v-if="c.opinion" class="opinion">「{{ c.opinion }}」</span>
          </div>
        </div>
      </div>

      <!-- 审批进度（已完成，只读） -->
      <div class="card" v-if="detail.approvals.length > 0">
        <div class="card__header">审批进度</div>
        <div class="card__body">
          <div v-for="a in detail.approvals" :key="a.id" class="progress-row">
            <span>{{ a.approver_name }}</span>
            <span class="status-tag" :class="approvalStatusClass(a.status)">{{ approvalStatusLabel(a.status) }}</span>
            <span v-if="a.opinion" class="opinion">「{{ a.opinion }}」</span>
          </div>
        </div>
      </div>

      <!-- 操作区 —— 批准决定 -->
      <div class="card" v-if="detail.status === 'pending'">
        <div class="card__header">批准决定</div>
        <div class="card__body">
          <el-input v-model="opinion" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="通过可空，驳回必填" />

          <div class="actions-bar">
            <el-button type="success" size="large" :loading="endorsing" @click="handleApprove">批准通过</el-button>
            <el-button type="danger" size="large" :loading="rejecting" @click="handleReject">批准驳回</el-button>
          </div>
        </div>
      </div>
      <el-alert v-else :type="detail.status === 'approved' ? 'success' : 'warning'" :closable="false" show-icon>
        {{ detail.status === 'approved' ? '已批准通过' + (detail.opinion ? '（意见：' + detail.opinion + '）' : '') : '已批准驳回（意见：' + (detail.opinion || '无') + '）' }}
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
/** 批准处理页 —— 难度4终审，签批逻辑复用共享 composable（P2-2 抽取） */
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getEndorsementDetail, endorseApprove, endorseReject, type EndorsementDetail } from '@/api/endorsement'
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
const { loading, forbidden, detail } = useDetailLoad<EndorsementDetail>({
  loadFn: getEndorsementDetail,
  breadcrumbTail: '批准处理',
})

/** 历史节点文件（按节点分组，排除当前节点） */
const { historyFileGroups } = useDetailFileGrouping(
  computed(() => detail.value?.files),
  computed(() => detail.value?.node_id),
)

// 签批弹窗（PDF 文件列表 + 弹窗状态 + 确认回调）
const { pdfFiles, pdfPreviewUrls } = usePdfFilesForSignature(computed(() => detail.value?.node_files))
const { showSignatureDialog, sigSlots, authToken, openSignatureDialog, promptUploadSignature, makeSignatureConfirm } = useSignatureDialog()
const onSignatureConfirm = makeSignatureConfirm(doEndorse)

const opinion = ref('')
const endorsing = ref(false)
const rejecting = ref(false)

/** 批准通过 —— 如需签名先弹出签批预览 */
async function handleApprove() {
  if (!detail.value) return
  // 节点要求批准人签批 → 检查签名图片
  if (detail.value.require_endorser_signature) {
    if (detail.value.current_signature_url) {
      openSignatureDialog()
      return
    }
    await promptUploadSignature('该节点要求批准人签批，但您尚未上传签名图片，请先上传。')
    return
  }
  await doEndorse()
}

/** 执行批准通过 */
async function doEndorse() {
  if (!detail.value) return
  endorsing.value = true
  try {
    await endorseApprove(detail.value.id, opinion.value || null, sigSlots.value || undefined)
    ElMessage.success('批准通过')
    router.push({ name: 'Profile' })
  } finally { endorsing.value = false }
}

/** 批准驳回 */
async function handleReject() {
  if (!detail.value) return
  if (!opinion.value.trim()) { ElMessage.error('驳回必须填写意见'); return }

  rejecting.value = true
  try {
    await endorseReject(detail.value.id, opinion.value)
    ElMessage.success('已驳回')
    router.push({ name: 'Profile' })
  } finally { rejecting.value = false }
}
</script>

<style lang="scss" scoped>
.endorse-detail { /* max-width 由 AppLayout 内容区统一控制 */ }

.progress-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.opinion { color: var(--el-text-color-secondary); font-size: 12px; }
.actions-bar { display: flex; gap: 12px; margin-top: 12px; }
</style>
