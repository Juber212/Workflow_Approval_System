<template>
  <!-- 校验处理页 —— 顶部摘要 + 进度条 + 单栏表单 -->
  <!-- P1-34：非本人校验记录后端返回 403，渲染「无权查看」而非误导的「记录不存在」空态 -->
  <ForbiddenPage v-if="forbidden" />
  <div class="check-detail" v-if="!forbidden" v-loading="loading">
    <el-empty v-if="!loading && !detail" description="校验记录不存在" />

    <template v-if="detail">
      <!-- ===== 顶部摘要条 ===== -->
      <TopSummary :title="`${detail.instance_name} · ${detail.node_name}`">
        <span>提交人：<b>{{ detail.submitter_name || '-' }}</b></span>
        <span class="top-summary__sep">·</span>
        <span>状态：<b>{{ checkStatusLabel(detail.status) }}</b></span>
      </TopSummary>

      <!-- 流程进度 + 节点信息（P2-2 共享组件） -->
      <NodeInfoGrid :detail="detail" />

      <!-- 负责人备注 -->
      <div class="card" v-if="detail.assignee_note">
        <div class="card__header">负责人备注</div>
        <div class="card__body">{{ detail.assignee_note }}</div>
      </div>

      <!-- 本节点文件 + 历史节点文件 + 无文件兜底（P2-2 共享组件） -->
      <FileListView :current-node-files="detail.node_files" :history-groups="historyFileGroups" />

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

      <!-- 操作区 -->
      <div class="card" v-if="detail.status === 'pending'">
        <div class="card__header">校验决定</div>
        <div class="card__body">
          <el-input v-model="opinion" type="textarea" :rows="2" maxlength="500" show-word-limit :placeholder="'通过可空，退回必填'" />
          <div class="actions-bar">
            <el-button type="success" size="large" :loading="passing" @click="handlePass">校验通过</el-button>
            <el-button type="danger" size="large" :loading="returning" @click="handleReturn">校验退回</el-button>
          </div>
        </div>
      </div>
      <el-alert v-else :type="detail.status === 'passed' ? 'success' : 'warning'" :title="detail.status === 'passed' ? '已校验通过' : '已校验退回'" :closable="false" show-icon />
    </template>

    <!-- 签名预览弹框 -->
    <SignaturePreviewDialog
      v-if="detail"
      v-model="showSignatureDialog"
      :pdf-files="pdfFiles"
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
/** 校验处理页 —— 校验通过/退回，签批逻辑复用共享 composable（P2-2 抽取） */
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getCheckDetail, passCheck, returnCheck, type CheckDetail } from '@/api/check'
import { checkStatusClass, checkStatusLabel } from '@/utils/labels'
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
const { loading, forbidden, detail } = useDetailLoad<CheckDetail>({
  loadFn: getCheckDetail,
  breadcrumbTail: '校验处理',
})

/** 历史节点文件（按节点分组，排除当前节点） */
const { historyFileGroups } = useDetailFileGrouping(
  computed(() => detail.value?.files),
  computed(() => detail.value?.node_id),
)

// 签批弹窗（PDF 文件列表 + 弹窗状态 + 确认回调）
const { pdfFiles } = usePdfFilesForSignature(computed(() => detail.value?.node_files))
const { showSignatureDialog, sigSlots, authToken, openSignatureDialog, promptUploadSignature, makeSignatureConfirm } = useSignatureDialog()
const onSignatureConfirm = makeSignatureConfirm(doPass)

const opinion = ref('')
const passing = ref(false)
const returning = ref(false)

async function handlePass() {
  if (!detail.value) return
  // 节点要求校验人签批 → 检查签名图片
  if (detail.value.require_checker_signature) {
    if (detail.value.current_signature_url) {
      openSignatureDialog()
      return
    }
    await promptUploadSignature('该节点要求校验人签批，但您尚未上传签名图片，请先上传。')
    return
  }
  await doPass()
}

async function doPass() {
  if (!detail.value) return
  passing.value = true
  try {
    await passCheck(detail.value.id, opinion.value || null, sigSlots.value)
    ElMessage.success('校验通过')
    router.push({ name: 'Profile' })
  } finally { passing.value = false }
}

async function handleReturn() {
  if (!detail.value) return
  if (!opinion.value.trim()) { ElMessage.error('退回必须填写意见'); return }
  returning.value = true
  try {
    await returnCheck(detail.value.id, opinion.value)
    ElMessage.success('已退回')
    router.push({ name: 'Profile' })
  } finally { returning.value = false }
}
</script>

<style lang="scss" scoped>
.check-detail { /* max-width 由 AppLayout 内容区统一控制 */ }

.progress-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.opinion { color: var(--el-text-color-secondary); font-size: 12px; }
.actions-bar { display: flex; gap: 12px; margin-top: 12px; }
</style>
