<template>
  <!-- 任务处理页 —— 顶部摘要 + 进度条 + 单栏表单 -->
  <div class="task-detail" v-loading="loading">
    <el-empty v-if="!loading && !detail" description="任务不存在" :image-size="50" />

    <template v-if="detail">
      <!-- ===== 顶部摘要条 ===== -->
      <div class="top-summary">
        <h2 class="top-summary__title">{{ detail.instance_name }}</h2>
        <div class="top-summary__meta">
          <span>当前节点：<b>{{ detail.node_name }}</b>（第{{ detail.round }}轮）</span>
          <span class="top-summary__sep">·</span>
          <span>截止时间：{{ formatTime(detail.deadline) }}</span>
          <span class="top-summary__sep">·</span>
          <span>{{ detail.require_file ? '必须上传文件' : '可选上传文件' }}</span>
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
              <div class="k">节点说明</div>
              <div class="v">{{ detail.node_description || '无' }}</div>
            </div>
            <div class="info-grid__item">
              <div class="k">完成时限</div>
              <div class="v">{{ detail.time_limit_days ? detail.time_limit_days + '工作日' : '未设置' }} · {{ formatTime(detail.deadline) }}</div>
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
          </div>
        </div>
      </div>

      <!-- 负责人备注 -->
      <div class="card">
        <div class="card__header">备注说明</div>
        <div class="card__body">
          <el-input v-model="assigneeNote" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="输入处理说明（选填）" />
        </div>
      </div>

      <!-- 文件模板下载（可提交状态下显示） -->
      <div v-if="canSubmit && docTemplates.length > 0" class="card">
        <div class="card__header">
          <span class="card__title">文件模板</span>
          <span class="card__title-hint">（下载后填写，可作为附件上传）</span>
        </div>
        <div class="card__body">
          <div class="doc-tpl-list">
            <div v-for="doc in docTemplates" :key="doc.id" class="doc-tpl-item">
              <span class="doc-tpl-item__icon">📄</span>
              <span class="doc-tpl-item__name">{{ doc.name }}</span>
              <el-tag size="small" effect="plain" :type="doc.file_type === 'xlsx' ? 'success' : ''">.{{ doc.file_type }}</el-tag>
              <el-button link type="primary" size="small" @click="handleDownloadTemplate(doc)">下载</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 文件上传区 —— 文件夹分组模式 -->
      <!-- 有文件夹配置：每个文件夹一个独立上传区域 -->
      <template v-if="canUpload && hasFileFolders">
        <div
          v-for="folder in detail!.file_folders!"
          :key="folder.name"
          class="card folder-upload-card"
          :class="{ 'folder--warning': !isFolderSatisfied(folder), 'folder--satisfied': isFolderSatisfied(folder) }"
        >
          <div class="card__header folder-header">
            <span class="folder-header__icon">📁</span>
            <span class="folder-header__name">{{ folder.name }}</span>
            <span class="folder-header__rule">{{ folderStatusLabel(folder) }}</span>
            <span class="folder-header__count">[{{ getFolderFileCount(folder.name) }}/{{ folder.file_count ?? '--' }}]</span>
          </div>
          <div class="card__body">
            <div class="file-list" v-if="getFolderFiles(folder.name).length > 0">
              <div v-for="f in getFolderFiles(folder.name)" :key="f.id" class="file-row">
                <span>{{ f.original_name }}</span>
                <span class="file-size">{{ formatFileSize(f.file_size) }}</span>
                <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
                <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
                <el-button text type="danger" size="small" @click="handleDeleteFile(f.id)">删除</el-button>
              </div>
            </div>
            <div v-else class="folder-empty-hint">{{ folder.required ? '⚠ 必须上传文件' : '可选，暂无文件' }}</div>
            <el-upload
              :show-file-list="false"
              :http-request="(opt: any) => handleUpload(opt, folder.name)"
              :before-upload="beforeUpload"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg"
              style="margin-top:8px"
            >
              <el-button size="small" :loading="uploading">+ 上传到此文件夹</el-button>
            </el-upload>
            <!-- 实时状态提示 -->
            <div v-if="!isFolderSatisfied(folder)" class="folder-warn">{{ getFolderWarning(folder) }}</div>
          </div>
        </div>
        <div class="upload-hint" style="margin-top:8px">支持 PDF/Word/Excel/图片，单文件 ≤50MB</div>
      </template>

      <!-- 无文件夹配置：保持原有简单上传区（向后兼容） -->
      <template v-else-if="canUpload && !hasFileFolders">
      <div class="card">
        <div class="card__header">上传文件（{{ detail!.files.length }}）</div>
        <div class="card__body">
          <div class="file-list" v-if="detail!.files.length > 0">
            <div v-for="f in detail!.files" :key="f.id" class="file-row">
              <span>{{ f.original_name }}</span>
              <span class="file-size">{{ formatFileSize(f.file_size) }}</span>
              <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
              <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
              <el-button text type="danger" size="small" @click="handleDeleteFile(f.id)">删除</el-button>
            </div>
          </div>
          <el-upload :show-file-list="false" :http-request="handleUpload" :before-upload="beforeUpload" accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg">
            <el-button type="primary" :loading="uploading">+ 上传文件</el-button>
          </el-upload>
          <div class="upload-hint">支持 PDF/Word/Excel/图片，单文件 ≤50MB</div>
        </div>
      </div>
      </template>

      <!-- 校验进度（提交后可见） -->
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

      <!-- 退回提示（仅退回重做时显示） -->
      <div class="card" v-if="detail.rejected_type">
        <el-alert type="warning" :closable="false" show-icon>
          <template #title>
            {{ detail.rejected_type === 'check' ? '校验退回' : '审批退回' }}（第 {{ detail.round }} 轮）
          </template>
          {{ detail.rejected_reason || '无具体原因' }}
        </el-alert>
      </div>

      <!-- 操作按钮 -->
      <div class="actions-bar" v-if="canSubmit">
        <el-button size="large" @click="handleSaveDraft" :loading="saving">保存草稿</el-button>
        <el-button size="large" type="primary" @click="handleSubmit" :loading="submitting || preparing">
          {{ preparing ? '正在转换文件...' : detail.rejected_type ? '重新提交并进入校验' : '提交并进入校验' }}
        </el-button>
      </div>
      <div class="actions-bar" v-else-if="detail.status === 'waiting_check'">
        <el-alert type="info" title="已提交，等待校验中..." :closable="false" show-icon />
      </div>
    </template>

    <!-- 签名预览弹框 -->
    <SignaturePreviewDialog
      v-if="detail"
      v-model="showSignatureDialog"
      :pdf-files="pdfFiles"
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
/** 任务处理页 —— 上传文件 + 提交/保存草稿，支持文件夹分组上传 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTaskDetail, saveTaskDraft, submitTask, uploadTaskFile, deleteTaskFile, previewFile, downloadFile, prepareSign, type TaskDetail, type TaskFileItem } from '@/api/task'
import { downloadDocTemplate, type DocTemplateItem } from '@/api/template'
import type { FileFolderConfig } from '@/api/designer'
import type { SignatureSlot } from '@/api/signature'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import { formatTime, formatFileSize } from '@/utils/format'
import { priLabel, checkStatusClass, checkStatusLabel } from '@/utils/labels'
import request from '@/api/request'
import ProgressBar from '@/views/flows/components/ProgressBar.vue'
import SignaturePreviewDialog from '@/views/flows/components/SignaturePreviewDialog.vue'

const { setBreadcrumb } = useBreadcrumb()
const route = useRoute()
const router = useRouter()
const AUTH_TOKEN = () => localStorage.getItem('token') || ''

const loading = ref(false)
const detail = ref<TaskDetail | null>(null)
const assigneeNote = ref('')
const uploading = ref(false)
const saving = ref(false)
const submitting = ref(false)
const preparing = ref(false)  // 预提交转化 PDF 中的状态

// 签批弹框
const showSignatureDialog = ref(false)
const sigSlots = ref<SignatureSlot[] | null>(null)

const canUpload = computed(() => detail.value && ['pending', 'processing'].includes(detail.value.status))
const canSubmit = computed(() => detail.value && ['pending', 'processing'].includes(detail.value.status))

/** PDF 文件列表（供签批弹框使用）

使用 mime_type 判断是否为 PDF（优先），兜底用文件名后缀。
负责人提交前调用 prepareSign 获取已转换的 PDF 文件列表。 */
const pdfFiles = ref<Array<{ file_id: number; name: string; url: string }>>([])

// ─── 文件模板下载 ────────────────────────────────────────
const docTemplates = ref<DocTemplateItem[]>([])

/** 加载该任务可用的文件模板列表 */
async function loadDocTemplates() {
  if (!detail.value) return
  try {
    const res = await request.get(`/tasks/${detail.value.id}/document-templates`)
    const data = res.data
    if (data?.items) {
      docTemplates.value = data.items
    }
  } catch {
    // 无模板时不报错
  }
}

/** 下载文件模板（自动替换占位符） */
async function handleDownloadTemplate(doc: DocTemplateItem) {
  if (!detail.value) return
  try {
    await downloadDocTemplate(detail.value.id, doc.id)
    ElMessage.success(`「${doc.name}」下载成功`)
  } catch (e: any) {
    ElMessage.error(e?.message || '下载失败')
  }
}
const hasFileFolders = computed(() => {
  const folders = detail.value?.file_folders
  return folders && Array.isArray(folders) && folders.length > 0
})

/** 获取指定文件夹的文件列表 */
function getFolderFiles(folderName: string): TaskFileItem[] {
  return (detail.value?.files || []).filter(f => f.folder_name === folderName)
}

/** 获取指定文件夹的文件数量 */
function getFolderFileCount(folderName: string): number {
  return getFolderFiles(folderName).length
}

/** 文件夹规则是否满足 */
function isFolderSatisfied(folder: FileFolderConfig): boolean {
  const count = getFolderFileCount(folder.name)
  if (!folder.required) return true  // 可选文件夹永远满足
  if (folder.file_count == null) return count >= 1  // 至少1个
  return count === folder.file_count  // 精确匹配
}

/** 文件夹状态标签 */
function folderStatusLabel(folder: FileFolderConfig): string {
  if (!folder.required) return '可选'
  if (folder.file_count == null) return '必须提交 · 不限'
  return `必须提交 · ${folder.file_count}个`
}

/** 文件夹不满足时的警告文字 */
function getFolderWarning(folder: FileFolderConfig): string {
  const count = getFolderFileCount(folder.name)
  if (!folder.required) return ''
  if (folder.file_count == null) return count === 0 ? '⚠ 至少上传 1 个文件' : ''
  if (count < folder.file_count) return `⚠ 还需上传 ${folder.file_count - count} 个文件`
  return ''
}

onMounted(async () => {
  setBreadcrumb([
    { label: '首页', to: '/dashboard' },
    { label: '个人中心', to: '/profile' },
    { label: '任务处理' },
  ])
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    detail.value = await getTaskDetail(id)
    assigneeNote.value = detail.value.assignee_note || ''
    // 加载可用文件模板
    await loadDocTemplates()
  } finally { loading.value = false }
})

function beforeUpload(file: File) {
  if (file.size > 50 * 1024 * 1024) { ElMessage.error('文件不能超过 50MB'); return false }
  return true
}

async function handleUpload({ file }: { file: File }, folderName?: string) {
  if (!detail.value) return
  uploading.value = true
  try {
    await uploadTaskFile(detail.value.id, file, folderName)
    ElMessage.success('上传成功')
    detail.value = await getTaskDetail(detail.value.id)
  } finally { uploading.value = false }
}

async function handleDeleteFile(fileId: number) {
  if (!detail.value) return
  try { await ElMessageBox.confirm('确认删除此文件？', '确认', { type: 'warning' }) } catch { return }
  await deleteTaskFile(detail.value.id, fileId)
  ElMessage.success('已删除')
  detail.value = await getTaskDetail(detail.value.id)
}

async function handleSaveDraft() {
  if (!detail.value) return
  saving.value = true
  try {
    await saveTaskDraft(detail.value.id, { assignee_note: assigneeNote.value })
    ElMessage.success('草稿已保存')
  } finally { saving.value = false }
}

async function handleSubmit() {
  if (!detail.value) return

  // 文件夹模式校验：逐文件夹检查规则
  if (hasFileFolders.value) {
    const badFolders: string[] = []
    for (const folder of detail.value.file_folders!) {
      if (!isFolderSatisfied(folder)) {
        badFolders.push(`「${folder.name}」${getFolderWarning(folder)}`)
      }
    }
    if (badFolders.length > 0) {
      ElMessage.error(badFolders.join('；'))
      return
    }
  } else if (detail.value.require_file && detail.value.files.length === 0) {
    // 简单模式：沿用 require_file 校验
    ElMessage.error('该节点要求必须上传文件')
    return
  }

  // 节点要求负责人签批 → 检查签名图片
  if (detail.value.require_assignee_signature) {
    if (detail.value.current_signature_url) {
      // 有签名图 → 先调用 prepareSign 将文件转为 PDF → 弹签批弹窗
      preparing.value = true
      try {
        const pdfList = await prepareSign(detail.value.id)
        // 将后端返回的 PDF 文件列表设置到弹框
        pdfFiles.value = pdfList.map(f => ({
          file_id: f.id,
          name: f.original_name,
          url: f.url,
        }))
        if (pdfFiles.value.length === 0) {
          ElMessage.warning('没有可签批的 PDF 文件，请先上传文件')
          return
        }
        sigSlots.value = null
        showSignatureDialog.value = true
      } catch (err: any) {
        // axios 响应拦截器已显示后端错误消息，这里只兜底网络异常
        if (!err?.response) {
          ElMessage.error('网络连接异常，请检查网络')
        }
      } finally {
        preparing.value = false
      }
      return
    } else {
      // 无签名图 → 提示前往上传
      try {
        await ElMessageBox.alert('该节点要求负责人签批，但您尚未上传签名图片，请先上传。', '无法签批', {
          confirmButtonText: '前往上传',
          type: 'warning',
        })
        router.push('/profile?tab=signature')
        return
      } catch { return }
    }
  }

  await doSubmit()
}

async function doSubmit() {
  if (!detail.value) return
  submitting.value = true
  try {
    await submitTask(detail.value.id, { assignee_note: assigneeNote.value, signatures: sigSlots.value })
    ElMessage.success('任务已提交，等待校验')
    router.push('/profile')
  } finally { submitting.value = false }
}

/** 签批预览确认回调 */
function onSignatureConfirm(slots: SignatureSlot[]) {
  sigSlots.value = slots
  showSignatureDialog.value = false
  doSubmit()
}

// 时间/文件大小/状态标签 —— 统一从 @/utils 导入
</script>

<style lang="scss" scoped>
.task-detail { /* max-width 由 AppLayout 内容区统一控制 */ }

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

/* 查看完整流程链接 */
.view-flow-link {
  font-size: 13px; color: var(--el-color-primary); text-decoration: none;
  font-weight: 400;
  &:hover { text-decoration: underline; }
}

/* 信息网格 */
.info-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 14px;
  .k { color: var(--el-text-color-secondary); margin-bottom: 2px; font-size: 12px; }
  .v { color: var(--el-text-color-primary); font-weight: 500; }
}

/* 文件列表 */
.file-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.file-row { display: flex; align-items: center; gap: 10px; padding: 6px 10px; background: var(--el-bg-color-page); border-radius: 6px; font-size: 13px; }
.file-size { color: var(--el-text-color-secondary); font-size: 12px; flex: 1; }
.upload-hint { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 6px; }
.empty-hint { font-size: 13px; color: var(--el-text-color-placeholder); text-align: center; padding: 12px; }

/* 文件夹上传卡片 */
.folder-upload-card {
  border-left: 3px solid var(--el-color-success);
  transition: border-color 0.3s;
  &.folder--warning { border-left-color: var(--el-color-warning); }
  &.folder--satisfied { border-left-color: var(--el-color-success); }
  .folder-header {
    display: flex; align-items: center; gap: 6px;
    &__icon { font-size: 14px; }
    &__name { font-weight: 600; font-size: 14px; }
    &__rule { font-size: 12px; color: var(--el-text-color-secondary); margin-left: auto; }
    &__count { font-size: 13px; font-weight: 500; color: var(--el-text-color-primary); flex-shrink: 0; }
  }
}
.folder-empty-hint { font-size: 13px; color: var(--el-text-color-placeholder); padding: 4px 0; }
.folder-warn { font-size: 12px; color: var(--el-color-warning); margin-top: 4px; font-weight: 500; }

.progress-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.opinion { color: var(--el-text-color-secondary); font-size: 12px; }
.actions-bar { display: flex; gap: 12px; margin-top: 20px; padding: 16px 0; }

.pri-tag {
  font-size: 12px; font-weight: 500; padding: 1px 6px; border-radius: 8px;
  &.pri--urgent { color: #fff; background: var(--el-color-danger); }
  &.pri--high { color: #fff; background: var(--el-color-warning); }
  &.pri--normal { color: var(--el-text-color-secondary); background: var(--el-fill-color); }
  &.pri--low { color: var(--el-color-info); background: var(--el-color-info-light-9); }
}

/* ─── 文件模板下载列表 ─── */
.doc-tpl-list { display: flex; flex-direction: column; gap: 8px; }
.doc-tpl-item {
  display: flex; align-items: center; gap: 10px; padding: 6px 0;
  &__icon { font-size: 16px; }
  &__name { flex: 1; font-size: 14px; }
}
.card__title-hint { font-size: 12px; color: var(--el-text-color-placeholder); font-weight: 400; margin-left: 4px; }
</style>
