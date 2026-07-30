<template>
  <!-- 校验处理页 —— 顶部摘要 + 进度条 + 单栏表单 -->
  <div class="check-detail" v-loading="loading">
    <el-empty v-if="!loading && !detail" description="校验记录不存在" />

    <template v-if="detail">
      <!-- ===== 顶部摘要条 ===== -->
      <div class="top-summary">
        <h2 class="top-summary__title">{{ detail.instance_name }} · {{ detail.node_name }}</h2>
        <div class="top-summary__meta">
          <span>提交人：<b>{{ detail.submitter_name || '-' }}</b></span>
          <span class="top-summary__sep">·</span>
          <span>状态：<b>{{ checkStatusLabel(detail.status) }}</b></span>
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

      <!-- 节点信息 —— 4 栏紧凑布局 -->
      <div class="card">
        <div class="card__header">节点信息</div>
        <div class="card__body">
          <div v-if="detail.node_description" class="node-desc">{{ detail.node_description }}</div>
          <div class="info-grid">
            <div class="info-grid__item">
              <div class="k">完成时限</div>
              <div class="v">{{ detail.time_limit_days ? detail.time_limit_days + '工作日' : '未设置' }}</div>
            </div>
            <div class="info-grid__item">
              <div class="k">截止时间</div>
              <div class="v">{{ formatTime(detail.deadline) || '—' }}</div>
            </div>
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

      <!-- 负责人备注 -->
      <div class="card" v-if="detail.assignee_note">
        <div class="card__header">负责人备注</div>
        <div class="card__body">{{ detail.assignee_note }}</div>
      </div>

      <!-- 本节点文件 -->
      <div class="card" v-if="currentNodeFiles.length > 0">
        <div class="card__header">本节点文件（{{ currentNodeFiles.length }}）<el-tag size="small" type="primary" effect="plain" style="margin-left:6px">当前节点</el-tag></div>
        <div class="card__body">
          <div v-for="f in currentNodeFiles" :key="f.id" class="file-row">
            <span>{{ f.original_name }}</span>
            <span class="file-size">{{ formatFileSize(f.file_size) }}</span>
            <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
            <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
          </div>
        </div>
      </div>

      <!-- 历史节点文件（默认折叠） -->
      <div class="card" v-if="historyFileGroups.length > 0">
        <div class="card__header" style="cursor:pointer" @click="showHistoryFiles = !showHistoryFiles">
          <span style="display:flex;align-items:center;gap:6px">
            历史节点文件（{{ historyFileTotal }}）
            <el-icon :size="14" style="transition:transform 0.2s" :style="{ transform: showHistoryFiles ? 'rotate(90deg)' : 'rotate(0deg)' }"><ArrowRight /></el-icon>
          </span>
        </div>
        <div class="card__body" v-show="showHistoryFiles">
          <div v-for="group in historyFileGroups" :key="group.nodeName" class="file-group">
            <div class="file-group__header">
              <span class="file-group__node-name">{{ group.nodeName }}</span>
              <span class="file-group__count">{{ group.files.length }} 个文件</span>
            </div>
            <div v-for="f in group.files" :key="f.id" class="file-row">
              <span>{{ f.original_name }}</span>
              <span class="file-size">{{ formatFileSize(f.file_size) }}</span>
              <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
              <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 无文件兜底 -->
      <div class="card" v-if="detail.files.length === 0">
        <div class="card__header">节点文件</div>
        <div class="card__body"><div class="empty-hint">暂无文件</div></div>
      </div>

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
      :auth-token="AUTH_TOKEN()"
      :sig-url="detail.current_signature_url"
      :default-x="detail.role_signature?.x ?? detail.signature_x"
      :default-y="detail.role_signature?.y ?? detail.signature_y"
      :default-page="detail.signature_page"
      @confirm="onSignatureConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'
import { getToken } from '@/api/request'
import { getCheckDetail, passCheck, returnCheck, type CheckDetail } from '@/api/check'
import { previewFile, downloadFile } from '@/api/task'
import type { SignatureSlot } from '@/api/signature'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import { formatTime, formatFileSize } from '@/utils/format'
import { priLabel, instStatusClass, instStatusLabel, checkStatusClass, checkStatusLabel } from '@/utils/labels'
import ProgressBar from '@/views/flows/components/ProgressBar.vue'
import SignaturePreviewDialog from '@/views/flows/components/SignaturePreviewDialog.vue'

const { setBreadcrumb } = useBreadcrumb()
const route = useRoute()
const router = useRouter()
const AUTH_TOKEN = () => getToken() || ''

const loading = ref(false)
const detail = ref<CheckDetail | null>(null)
const opinion = ref('')
const passing = ref(false)
const returning = ref(false)
const showHistoryFiles = ref(false)

/** 本节点文件（后端 node_files 已过滤，直接使用） */
const currentNodeFiles = computed(() => {
  if (!detail.value) return []
  return detail.value.node_files as CheckDetail['files']
})

/** 历史节点文件（按节点分组） */
const historyFileGroups = computed(() => {
  if (!detail.value) return []
  const map = new Map<string, { nodeName: string; files: CheckDetail['files'] }>()
  for (const f of detail.value.files) {
    if (f.node_id === detail.value!.node_id) continue
    const key = f.node_id ? String(f.node_id) : '_unknown'
    if (!map.has(key)) map.set(key, { nodeName: (f as any).node_name || '未知节点', files: [] })
    map.get(key)!.files.push(f)
  }
  return [...map.values()]
})
const historyFileTotal = computed(() => historyFileGroups.value.reduce((s, g) => s + g.files.length, 0))

// 签批弹框
const showSignatureDialog = ref(false)
const sigSlots = ref<SignatureSlot[] | null>(null)

/** PDF 文件列表（供签批弹框使用）

优先用 mime_type 判断是否为 PDF，兜底用文件名后缀。
校验时文件已由负责人提交时转换为 PDF。 */
const pdfFiles = computed(() => {
  if (!detail.value) return []
  return (detail.value.node_files as any[])
    .filter(f => f.mime_type === 'application/pdf' || (f.original_name || '').toLowerCase().endsWith('.pdf'))
    .map(f => ({
      file_id: (f as any).id,
      name: (f as any).original_name || '',
      url: `/api/v1/files/${(f as any).id}/download`,
    }))
})

/** 加载校验详情数据 */
async function loadCheckData() {
  setBreadcrumb([
    { label: '首页', to: '/dashboard' },
    { label: '个人中心', to: '/profile' },
    { label: '校验处理' },
  ])
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try { detail.value = await getCheckDetail(id) } finally { loading.value = false }
}

onMounted(loadCheckData)
watch(() => route.params.id, loadCheckData)

async function handlePass() {
  if (!detail.value) return
  // 节点要求校验人签批 → 检查签名图片
  if (detail.value.require_checker_signature) {
    if (detail.value.current_signature_url) {
      sigSlots.value = null
      showSignatureDialog.value = true
      return
    } else {
      try {
        await ElMessageBox.alert('该节点要求校验人签批，但您尚未上传签名图片，请先上传。', '无法签批', {
          confirmButtonText: '前往上传',
          type: 'warning',
        })
        router.push({ name: 'Profile', query: { tab: 'signature' } })
        return
      } catch { return }
    }
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

/** 签批预览确认回调 */
function onSignatureConfirm(slots: SignatureSlot[]) {
  sigSlots.value = slots
  showSignatureDialog.value = false
  doPass()
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

// 时间/文件大小/状态标签 —— 统一从 @/utils 导入
</script>

<style lang="scss" scoped>
.check-detail { /* max-width 由 AppLayout 内容区统一控制 */ }

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

.node-desc {
  font-size: 13px; color: var(--el-text-color-secondary);
  padding: 8px 12px; background: var(--el-bg-color-page);
  border-radius: 6px; margin-bottom: 12px; line-height: 1.6;
}

.info-grid {
  display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 16px 12px; font-size: 14px;
  .k { color: var(--el-text-color-secondary); margin-bottom: 4px; font-size: 12px; }
  .v { color: var(--el-text-color-primary); font-weight: 500; }
}

/* 文件分组 */
.file-group {
  margin-bottom: 12px;
  &:last-child { margin-bottom: 0; }
  &__header {
    display: flex; align-items: center; gap: 8px;
    padding: 4px 0; margin-bottom: 4px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }
  &__node-name { font-size: 13px; font-weight: 600; color: var(--el-text-color-primary); }
  &__count { font-size: 12px; color: var(--el-text-color-secondary); margin-left: auto; }
}

.file-row { display: flex; align-items: center; gap: 10px; padding: 4px 8px; background: var(--el-bg-color-page); border-radius: 4px; margin-bottom: 4px; font-size: 13px; }
.file-size { color: var(--el-text-color-secondary); font-size: 12px; }
.empty-hint { color: var(--el-text-color-placeholder); font-size: 13px; text-align: center; padding: 12px; }
.progress-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.opinion { color: var(--el-text-color-secondary); font-size: 12px; }
.actions-bar { display: flex; gap: 12px; margin-top: 12px; }

/* 难度 badge */
.diff-badge {
  font-size: 12px; font-weight: 500; padding: 1px 6px; border-radius: 8px;
  &.diff--4 { color: #fff; background: var(--el-color-danger); }
  &.diff--3 { color: #fff; background: var(--el-color-warning); }
  &.diff--2 { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.diff--1 { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}

.pri-tag {
  font-size: 12px; font-weight: 500; padding: 1px 6px; border-radius: 8px;
  &.pri--urgent { color: #fff; background: var(--el-color-danger); }
  &.pri--high { color: #fff; background: var(--el-color-warning); }
  &.pri--normal { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.pri--low { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}
</style>
