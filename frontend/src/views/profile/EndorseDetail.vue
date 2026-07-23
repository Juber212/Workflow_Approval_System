<template>
  <!-- 批准处理页 —— 难度4级时的最终审核 -->
  <div class="endorse-detail" v-loading="loading">
    <el-empty v-if="!loading && !detail" description="批准记录不存在" />

    <template v-if="detail">
      <!-- ===== 顶部摘要条 ===== -->
      <div class="top-summary">
        <h2 class="top-summary__title">
          {{ detail.instance_name }} · {{ detail.node_name }}
          <el-tag type="danger" size="small" style="margin-left:8px;vertical-align:middle">难度{{ detail.difficulty }}级 · 批准</el-tag>
        </h2>
        <div class="top-summary__meta">
          <span>批准人：<b>{{ detail.endorser_name }}</b></span>
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
              <div class="k">难度等级</div>
              <div class="v">
                <span class="diff-badge" :class="'diff--' + detail.difficulty">{{ detail.difficulty }}级</span>
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
            <div class="info-grid__item">
              <div class="k">当前轮次</div>
              <div class="v">#{{ detail.round }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 文件列表 -->
      <div class="card">
        <div class="card__header">节点文件（{{ detail.files.length }}）</div>
        <div class="card__body">
          <div v-if="detail.files.length === 0" class="empty-hint">暂无文件</div>
          <div v-for="f in detail.files" :key="f.id" class="file-row">
            <span>{{ f.original_name }}</span>
            <span class="file-size">{{ formatFileSize(f.file_size) }}</span>
            <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
            <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
          </div>
        </div>
      </div>

      <!-- 校验进度（已完成，只读） -->
      <div class="card" v-if="detail.checks.length > 0">
        <div class="card__header">校验进度</div>
        <div class="card__body">
          <div v-for="c in detail.checks" :key="c.id" class="progress-row">
            <span>校验人 ID:{{ c.checker_id }}</span>
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
            <span>审批人 ID:{{ a.approver_id }}</span>
            <span class="status-tag" :class="approvalStatusClass(a.status)">{{ approvalStatusLabel(a.status) }}</span>
            <el-tag v-if="a.signature_applied" size="small" type="success" effect="plain">已签名</el-tag>
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
      :auth-token="AUTH_TOKEN()"
      :sig-url="detail.current_signature_url"
      :default-x="detail.signature_x"
      :default-y="detail.signature_y"
      :default-page="detail.signature_page"
      @confirm="onSignatureConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getEndorsementDetail, endorse, endorseReject, type EndorsementDetail } from '@/api/endorsement'
import { previewFile, downloadFile } from '@/api/task'
import type { SignatureSlot } from '@/api/signature'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import { useUserStore } from '@/stores/user'
import { formatTime, formatFileSize } from '@/utils/format'
import { priLabel, instStatusClass, instStatusLabel, checkStatusClass, checkStatusLabel, approvalStatusClass, approvalStatusLabel } from '@/utils/labels'
import ProgressBar from '@/views/flows/components/ProgressBar.vue'
import SignaturePreviewDialog from '@/views/flows/components/SignaturePreviewDialog.vue'
const AUTH_TOKEN = () => localStorage.getItem('token') || ''

const { setBreadcrumb } = useBreadcrumb()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const detail = ref<EndorsementDetail | null>(null)
const opinion = ref('')
const endorsing = ref(false)
const rejecting = ref(false)

// 签批预览弹框
const showSignatureDialog = ref(false)
const sigSlots = ref<SignatureSlot[] | null>(null)

/** PDF 文件列表（供签批弹框使用） */
const pdfFiles = computed(() => {
  if (!detail.value) return []
  return (detail.value.files as any[])
    .filter(f => (f.original_name || '').toLowerCase().endsWith('.pdf'))
    .map(f => ({
      file_id: f.id,
      name: f.original_name || '',
      url: `/api/v1/files/${f.id}/download`,
    }))
})

/** PDF 文件预览 URL */
const pdfPreviewUrls = computed(() => pdfFiles.value.map(f => f.url))

onMounted(async () => {
  setBreadcrumb([
    { label: '首页', to: '/dashboard' },
    { label: '个人中心', to: '/profile' },
    { label: '批准处理' },
  ])
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try { detail.value = await getEndorsementDetail(id) } finally { loading.value = false }
})

/** 批准通过 —— 如需签名先弹出签批预览 */
async function handleApprove() {
  if (!detail.value) return
  // 节点要求批准人签批 → 检查签名图片
  if (detail.value.require_endorser_signature) {
    if (detail.value.current_signature_url) {
      sigSlots.value = null
      showSignatureDialog.value = true
      return
    } else {
      try {
        await ElMessageBox.alert('该节点要求批准人签批，但您尚未上传签名图片，请先上传。', '无法签批', {
          confirmButtonText: '前往上传',
          type: 'warning',
        })
        router.push('/profile?tab=signature')
        return
      } catch { return }
    }
  }
  await doEndorse()
}

/** 执行批准通过 */
async function doEndorse() {
  if (!detail.value) return
  endorsing.value = true
  try {
    await endorse(detail.value.id, {
      opinion: opinion.value || null,
      signatures: sigSlots.value || undefined,
    })
    ElMessage.success('批准通过')
    router.push('/profile')
  } finally { endorsing.value = false }
}

/** 签批预览确认回调 */
function onSignatureConfirm(slots: SignatureSlot[]) {
  sigSlots.value = slots
  showSignatureDialog.value = false
  doEndorse()
}

/** 批准驳回 */
async function handleReject() {
  if (!detail.value) return
  if (!opinion.value.trim()) { ElMessage.error('驳回必须填写意见'); return }

  rejecting.value = true
  try {
    await endorseReject(detail.value.id, { opinion: opinion.value })
    ElMessage.success('已驳回')
    router.push('/profile')
  } finally { rejecting.value = false }
}
</script>

<style lang="scss" scoped>
.endorse-detail { /* max-width 由 AppLayout 内容区统一控制 */ }

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
.progress-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.opinion { color: var(--el-text-color-secondary); font-size: 12px; }
.actions-bar { display: flex; gap: 12px; margin-top: 12px; }

.pri-tag {
  font-size: 12px; font-weight: 500; padding: 1px 6px; border-radius: 8px;
  &.pri--urgent { color: #fff; background: var(--el-color-danger); }
  &.pri--high { color: #fff; background: var(--el-color-warning); }
  &.pri--normal { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.pri--low { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}

/* 难度 badge */
.diff-badge {
  font-size: 12px; font-weight: 500; padding: 1px 6px; border-radius: 8px;
  &.diff--4 { color: #fff; background: var(--el-color-danger); }
  &.diff--3 { color: #fff; background: var(--el-color-warning); }
  &.diff--2 { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.diff--1 { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}
</style>
