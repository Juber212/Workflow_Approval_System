<template>
  <!-- 任务处理页 —— 顶部摘要 + 进度条 + 单栏表单 -->
  <!-- P1-34：非本人任务后端返回 403，渲染「无权查看」而非误导的「任务不存在」空态 -->
  <ForbiddenPage v-if="forbidden" />
  <div class="task-detail" v-if="!forbidden" v-loading="loading">
    <el-empty v-if="!loading && !detail" description="任务不存在" :image-size="50" />

    <template v-if="detail">
      <!-- ===== 顶部摘要条 ===== -->
      <TopSummary :title="detail.instance_name">
        <span>当前节点：<b>{{ detail.node_name }}</b>（第{{ detail.round }}轮）</span>
        <span class="top-summary__sep">·</span>
        <span>截止时间：{{ formatTime(detail.deadline) }}</span>
        <span class="top-summary__sep">·</span>
        <span>{{ detail.require_file ? '必须上传文件' : '可选上传文件' }}</span>
      </TopSummary>

      <!-- 流程进度 + 节点信息（P2-2 共享组件） -->
      <NodeInfoGrid :detail="detail" />

      <!-- 负责人备注 -->
      <div class="card">
        <div class="card__header">备注说明</div>
        <div class="card__body">
          <el-input v-model="assigneeNote" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="输入处理说明（选填）" />
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
          <div v-for="group in historyFileGroups" :key="group.nodeKey" class="file-group">
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

      <!-- 文件模板下载（可提交状态下显示：模板包 + 散模板） -->
      <div v-if="canSubmit && (docCategories.length > 0 || docTemplates.length > 0)" class="card">
        <div class="card__header">
          <span class="card__title">文件模板</span>
          <span class="card__title-hint">（下载后填写，可作为附件上传）</span>
        </div>
        <div class="card__body">
          <!-- 模板包卡片 -->
          <div v-for="cat in docCategories" :key="'cat-' + cat.id" class="tpl-cat-card">
            <div class="tpl-cat-card__header" @click="toggleCatExpand(cat.id)">
              <el-icon :size="14" class="tpl-cat-arrow" :class="{ 'is-expanded': expandedCats.has(cat.id) }"><ArrowRight /></el-icon>
              <span class="tpl-cat-icon">📦</span>
              <span class="tpl-cat-name">{{ cat.name }}</span>
              <span class="tpl-cat-count">（{{ cat.document_count }} 个模板）</span>
              <el-button size="small" type="primary" plain style="margin-left:auto" @click.stop="handleDownloadCategoryZip(cat.id)">打包下载</el-button>
            </div>
            <!-- 展开后显示包内模板 -->
            <div v-show="expandedCats.has(cat.id)" class="tpl-cat-body">
              <div v-for="doc in cat.documents" :key="doc.id" class="doc-tpl-item doc-tpl-item--sub">
                <span class="doc-tpl-item__icon">📄</span>
                <span class="doc-tpl-item__name">{{ doc.name }}</span>
                <el-tag size="small" effect="plain" :type="doc.file_type === 'xlsx' ? 'success' : ''">.{{ doc.file_type }}</el-tag>
                <el-button link type="primary" size="small" @click="handleDownloadTemplate(doc)">下载</el-button>
              </div>
              <div v-if="cat.documents.length === 0" class="tpl-empty">该包内暂无模板</div>
            </div>
          </div>

          <!-- 散模板（未归包） -->
          <div v-if="docTemplates.length > 0" class="tpl-solo-section">
            <div v-for="doc in docTemplates" :key="'doc-' + doc.id" class="doc-tpl-item">
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
            <span class="folder-header__icon"><el-icon :size="14"><Folder /></el-icon></span>
            <span class="folder-header__name">{{ folder.name }}</span>
            <span class="folder-header__rule">{{ folderStatusLabel(folder) }}</span>
            <span class="folder-header__count">[{{ getFolderFileCount(folder.name) }}/{{ folder.file_count ?? '--' }}]</span>
          </div>
          <div class="card__body">
            <div class="file-list" v-if="getFolderFiles(folder.name).length > 0">
              <div v-for="f in getFolderFiles(folder.name)" :key="f.id" class="file-row">
                <span>{{ f.original_name }}</span>
                <!-- 转换期间：每文件迷你进度条；平时：状态文字标签 -->
                <span v-if="showFileProgress(f)" class="conv-progress" :class="{ 'is-failed': fileFailed[f.id] }">
                  <span class="conv-progress__bar"><span class="conv-progress__fill" :style="{ width: (fileProgress[f.id] || 0) + '%' }"></span></span>
                  <span class="conv-progress__label">{{ progressLabel(f) }}</span>
                </span>
                <span v-else-if="!isFileReady(f) && conversionLabel(f)" class="conv-tag" :class="'conv-tag--' + f.conversion_status">{{ conversionLabel(f) }}</span>
                <span class="file-size">{{ formatFileSize(f.file_size) }}</span>
                <el-button v-if="canPreview(f)" text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
                <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
                <el-button text type="danger" size="small" @click="handleDeleteFile(f.id)">删除</el-button>
              </div>
            </div>
            <div v-else class="folder-empty-hint">{{ folder.required ? '⚠ 必须上传文件' : '可选，暂无文件' }}</div>
            <el-upload
              :show-file-list="false"
              :http-request="(opt: any) => handleUpload(opt, folder.name)"
              :before-upload="beforeUpload"
              :disabled="isFolderFull(folder)"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg"
              style="margin-top:8px"
            >
              <el-button size="small" :loading="uploading" :disabled="isFolderFull(folder)">
                {{ isFolderFull(folder) ? '已达数量上限' : '+ 上传到此文件夹' }}
              </el-button>
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
        <div class="card__header">上传文件（{{ currentNodeFiles.length }}）</div>
        <div class="card__body">
          <div class="file-list" v-if="currentNodeFiles.length > 0">
            <div v-for="f in currentNodeFiles" :key="f.id" class="file-row">
              <span>{{ f.original_name }}</span>
              <!-- 转换期间：每文件迷你进度条；平时：状态文字标签 -->
              <span v-if="showFileProgress(f)" class="conv-progress" :class="{ 'is-failed': fileFailed[f.id] }">
                <span class="conv-progress__bar"><span class="conv-progress__fill" :style="{ width: (fileProgress[f.id] || 0) + '%' }"></span></span>
                <span class="conv-progress__label">{{ progressLabel(f) }}</span>
              </span>
              <span v-else-if="!isFileReady(f) && conversionLabel(f)" class="conv-tag" :class="'conv-tag--' + f.conversion_status">{{ conversionLabel(f) }}</span>
              <span class="file-size">{{ formatFileSize(f.file_size) }}</span>
              <el-button v-if="canPreview(f)" text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
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
        <el-button size="large" type="primary" @click="handleSubmit" :loading="submitting || preparing || waitingConversion">
          {{ waitingConversion ? '文件转换中，请稍候...' : preparing ? '准备中...' : detail.rejected_type ? '重新提交并进入校验' : '提交并进入校验' }}
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
/** 任务处理页 —— 上传文件 + 提交/保存草稿，支持文件夹分组上传 */
import { ref, reactive, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Folder } from '@element-plus/icons-vue'
import { getTaskDetail, saveTaskDraft, submitTask, uploadTaskFile, deleteTaskFile, previewFile, downloadFile, prepareSign, getFilesStatus, getTaskDocTemplates, downloadTaskTemplateZip, type TaskDetail, type TaskFileItem, type TaskTemplateCategory, type TaskDocTemplatesResponse, type FilesStatusResponse, type FileStatusItem, type PrepareSignFile } from '@/api/task'
import { downloadDocTemplate, type DocTemplateItem } from '@/api/template'
import type { FileFolderConfig } from '@/api/designer'
import { formatTime, formatFileSize } from '@/utils/format'
import { validateUploadSize } from '@/utils/upload'
import { checkStatusClass, checkStatusLabel } from '@/utils/labels'
import TopSummary from '@/views/flows/components/TopSummary.vue'
import NodeInfoGrid from '@/views/flows/components/NodeInfoGrid.vue'
import SignaturePreviewDialog from '@/views/flows/components/SignaturePreviewDialog.vue'
import ForbiddenPage from '@/views/error/403.vue'
import { useDetailLoad } from '@/composables/useDetailLoad'
import { useDetailFileGrouping } from '@/composables/useDetailFileGrouping'
import { useSignatureDialog } from '@/composables/useSignatureDialog'

const router = useRouter()

/** 文件转换状态标签（上传后 pending 待转换，提交时才转 PDF） */
function conversionLabel(f: TaskFileItem): string {
  const s = f.conversion_status
  if (s === 'pending') return '待转换'
  if (s === 'converting') return '转换中'
  if (s === 'failed') return '转换失败'
  return ''
}

/** 文件是否可在线预览（转换完成或未标注状态才可，未转/转换中/失败均不可） */
function canPreview(f: TaskFileItem): boolean {
  const s = f.conversion_status
  return !s || s === 'ready'
}

// 加载 + 403 + 面包屑 + 路由监听（P1-34 403 语义保留）
const { loading, forbidden, detail } = useDetailLoad<TaskDetail>({
  loadFn: getTaskDetail,
  breadcrumbTail: '任务处理',
  onLoaded: (d) => {
    assigneeNote.value = d.assignee_note || ''
    loadDocTemplates()
  },
})

const assigneeNote = ref('')
const uploading = ref(false)
const saving = ref(false)
const submitting = ref(false)
const preparing = ref(false)  // 预提交转化 PDF 中的状态
const waitingConversion = ref(false)  // 等待 ARQ Worker 后台转换完成
let conversionPollTimer: ReturnType<typeof setInterval> | null = null

// ─── 每文件转换进度条（伪动画 + 轮询真实状态校正） ────────────────
/** 每文件进度 0-100（fileId → 进度） */
const fileProgress = reactive<Record<number, number>>({})
/** 转换失败文件标记 */
const fileFailed = reactive<Record<number, boolean>>({})
/** 当前正在转换的文件 ID 集合（驱动动画推进） */
const convertingIds = ref<Set<number>>(new Set())
/** 进度动画定时器 */
let progressTimer: ReturnType<typeof setInterval> | null = null

/** 启动进度动画：每 100ms 推进转换中文件的进度 +2%，封顶 95%（真实完成由轮询补 100%） */
function startProgressAnimation() {
  if (progressTimer) return
  progressTimer = setInterval(() => {
    if (convertingIds.value.size === 0) { stopProgressAnimation(); return }
    convertingIds.value.forEach((id) => {
      fileProgress[id] = Math.min(95, (fileProgress[id] || 0) + 2)
    })
  }, 100)
}

/** 停止进度动画 */
function stopProgressAnimation() {
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
}

/** 重置所有文件进度状态（进入转换等待 / 转换结束） */
function resetConversionProgress() {
  Object.keys(fileProgress).forEach(k => delete fileProgress[Number(k)])
  Object.keys(fileFailed).forEach(k => delete fileFailed[Number(k)])
  convertingIds.value = new Set()
  stopProgressAnimation()
}

/** 进入转换等待时立即启动进度动画（不等首次轮询，避免转换过快时进度条来不及显示） */
function bootProgressForCurrentFiles() {
  if (!detail.value) return
  const ids = new Set<number>()
  detail.value.node_files.forEach((f) => {
    if (f.conversion_status && f.conversion_status !== 'ready') {
      ids.add(f.id)
      fileProgress[f.id] = 15  // 立即给基础进度，让进度条可见
    }
  })
  convertingIds.value = ids
  if (ids.size > 0) startProgressAnimation()
}

/** 轮询状态同步到每文件进度条：ready 补 100%，converting 启动动画，failed 置红，pending 归零 */
function syncConversionProgress(files: FileStatusItem[]) {
  const converting = new Set<number>()
  files.forEach((f) => {
    if (f.conversion_status === 'ready') {
      fileProgress[f.id] = 100
      delete fileFailed[f.id]
    } else if (f.conversion_status === 'converting') {
      converting.add(f.id)
      fileFailed[f.id] = false
      // 开始转换即给基础进度，让进度条立即可见推进
      fileProgress[f.id] = Math.max(fileProgress[f.id] || 0, 15)
    } else if (f.conversion_status === 'failed') {
      fileProgress[f.id] = 100
      fileFailed[f.id] = true
    } else {
      fileProgress[f.id] = 0  // pending：等待转换
    }
  })
  convertingIds.value = converting
  if (converting.size > 0) startProgressAnimation()
  else stopProgressAnimation()
}

/** 进度条旁文案：失败 → 转换失败；有推进 → 转换中；否则等待中 */
function progressLabel(f: TaskFileItem): string {
  if (fileFailed[f.id]) return '转换失败'
  return (fileProgress[f.id] || 0) > 0 ? '转换中' : '等待中'
}

/** 是否显示该文件的迷你进度条（转换期间：失败 或 未完成） */
function showFileProgress(f: TaskFileItem): boolean {
  return waitingConversion.value && (!!fileFailed[f.id] || (fileProgress[f.id] || 0) < 100)
}

/** 文件是否已转换完成（进度条消失后不误显「待转换」——详情快照未刷新时按进度状态判断） */
function isFileReady(f: TaskFileItem): boolean {
  if (f.conversion_status === 'ready') return true
  return (fileProgress[f.id] || 0) >= 100 && !fileFailed[f.id]
}

/** 用 prepareSign 返回的真实状态更新本地文件列表（不替换整个详情，避免与上传/删除刷新竞态） */
function applyConvertedStatus(files: PrepareSignFile[]) {
  if (!detail.value) return
  ;[detail.value.files, detail.value.node_files].forEach((list) => {
    list.forEach((f) => {
      const rf = files.find(x => x.id === f.id)
      if (rf) {
        f.conversion_status = rf.conversion_status
        if (rf.mime_type) f.mime_type = rf.mime_type
      }
    })
  })
}

// 签批弹窗（弹窗状态 + 确认回调）
const { showSignatureDialog, sigSlots, authToken, openSignatureDialog, promptUploadSignature, makeSignatureConfirm } = useSignatureDialog()
const onSignatureConfirm = makeSignatureConfirm(doSubmit)

const canUpload = computed(() => detail.value && ['pending', 'processing'].includes(detail.value.status))
const canSubmit = computed(() => detail.value && ['pending', 'processing'].includes(detail.value.status))

/** PDF 文件列表（供签批弹框使用）

使用 mime_type 判断是否为 PDF（优先），兜底用文件名后缀。
负责人提交前调用 prepareSign 获取已转换的 PDF 文件列表。 */
const pdfFiles = ref<Array<{ file_id: number; name: string; url: string }>>([])

// ─── 文件模板下载（含模板包） ────────────────────────────────────────
const docTemplates = ref<DocTemplateItem[]>([])             // 未归包的散模板
const docCategories = ref<TaskTemplateCategory[]>([])       // 模板包列表
const expandedCats = ref<Set<number>>(new Set())            // 展开的包 ID 集合

/** 加载该任务可用的文件模板列表（含模板包） */
async function loadDocTemplates() {
  if (!detail.value) return
  try {
    const data: TaskDocTemplatesResponse = await getTaskDocTemplates(detail.value.id)
    docTemplates.value = data.templates || []
    docCategories.value = data.categories || []
  } catch {
    // 无模板时不报错
  }
}

/** 切换包展开/折叠 */
function toggleCatExpand(catId: number) {
  const next = new Set(expandedCats.value)
  if (next.has(catId)) next.delete(catId)
  else next.add(catId)
  expandedCats.value = next
}

/** 下载单个文件模板（自动替换占位符） */
async function handleDownloadTemplate(doc: DocTemplateItem) {
  if (!detail.value) return
  try {
    await downloadDocTemplate(detail.value.id, doc.id)
    ElMessage.success(`「${doc.name}」下载成功`)
  } catch (e: any) {
    ElMessage.error(e?.message || '下载失败')
  }
}

/** 下载模板包 ZIP（填充占位符后打包） */
async function handleDownloadCategoryZip(catId: number) {
  if (!detail.value) return
  try {
    await downloadTaskTemplateZip(detail.value.id, catId)
    ElMessage.success('模板包下载成功')
  } catch (e: any) {
    ElMessage.error(e?.message || '下载失败')
  }
}
const hasFileFolders = computed(() => {
  const folders = detail.value?.file_folders
  return folders && Array.isArray(folders) && folders.length > 0
})

/** 本节点文件（后端 node_files 已过滤，直接使用） */
const currentNodeFiles = computed(() => {
  if (!detail.value) return [] as TaskFileItem[]
  return detail.value.node_files as TaskFileItem[]
})

/** 历史节点文件（按节点分组，排除当前节点） */
const { historyFileGroups } = useDetailFileGrouping(
  computed(() => detail.value?.files),
  computed(() => detail.value?.node_id),
)
const historyFileTotal = computed(() => historyFileGroups.value.reduce((s, g) => s + g.files.length, 0))
const showHistoryFiles = ref(false)

/** 获取指定文件夹的文件列表（仅本节点） */
function getFolderFiles(folderName: string): TaskFileItem[] {
  return currentNodeFiles.value.filter(f => f.folder_name === folderName)
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

/** 文件夹是否已达精确数量上限（达到后禁止继续上传，防止超传导致提交校验失败） */
function isFolderFull(folder: FileFolderConfig): boolean {
  if (!folder.required || folder.file_count == null) return false
  return getFolderFileCount(folder.name) >= folder.file_count
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
  if (count > folder.file_count) return `⚠ 已达上限 ${folder.file_count} 个，请先移除多余文件`
  return ''
}

// 离开页面时清理转换轮询与进度动画定时器
onUnmounted(() => {
  stopConversionPolling()
  stopProgressAnimation()
  // 清理未触发的 conversion-all-done 事件监听器，防止泄漏
  if (_conversionDoneHandler) {
    window.removeEventListener('conversion-all-done', _conversionDoneHandler)
    _conversionDoneHandler = null
  }
})

function beforeUpload(file: File) {
  return validateUploadSize(file)
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
  try { await ElMessageBox.confirm('确认删除此文件？', '确认', { type: 'warning' }) } catch { /* 用户取消或关闭弹窗 */ return }
  try {
    await deleteTaskFile(detail.value.id, fileId)
    ElMessage.success('已删除')
    detail.value = await getTaskDetail(detail.value.id)
  } catch {
    // 拦截器已统一弹错（P1-35），无需重复提示
  }
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
      // 有签名图 → 调用 prepareSign（立即返回）→ 等待转换 → 弹签批弹窗
      preparing.value = true
      try {
        const result = await prepareSign(detail.value.id)

        if (result.conversion_pending) {
          // 文件需要后台转换，进入等待模式
          waitingConversion.value = true
          resetConversionProgress()  // 重置每文件进度
          bootProgressForCurrentFiles()  // 立即启动进度动画，不等首次轮询
          // 启动轮询兜底（每 1 秒检查一次，直到全部完成或失败）
          startConversionPolling(detail.value!.id)
          // 也监听 WebSocket 通知（由 notification.ts 的 useNotificationSocket 触发自定义事件）
          listenConversionDone()
          return
        }

        // 无需转换（所有文件已是 PDF），直接打开签批弹窗
        pdfFiles.value = result.files.map(f => ({
          file_id: f.id,
          name: f.original_name,
          url: f.url,
        }))
        if (pdfFiles.value.length === 0) {
          ElMessage.warning('没有可签批的 PDF 文件，请先上传文件')
          return
        }
        openSignatureDialog()
      } catch {
        // 拦截器已统一弹错（P1-35）：网络异常与业务错误均不再重复提示，消除误报
      } finally {
        preparing.value = false
      }
      return
    }
    // 无签名图 → 提示前往上传
    await promptUploadSignature('该节点要求负责人签批，但您尚未上传签名图片，请先上传。')
    return
  }

  await doSubmit()
}

async function doSubmit() {
  if (!detail.value) return
  submitting.value = true
  try {
    await submitTask(detail.value.id, { assignee_note: assigneeNote.value, signatures: sigSlots.value })
    ElMessage.success('任务已提交，等待校验')
    router.push({ name: 'Profile' })
  } finally { submitting.value = false }
}

/** 签批预览确认回调 */
// ==================== 异步转换等待（50+ 优化） ====================

/** 启动轮询：每 2 秒检查文件转换状态（WebSocket 通知的兜底方案） */
function startConversionPolling(taskId: number) {
  stopConversionPolling()
  conversionPollTimer = setInterval(async () => {
    try {
      const status = await getFilesStatus(taskId)
      // 同步每文件进度条状态（ready 补 100%、converting 动画、failed 置红）
      syncConversionProgress(status.files)
      if (status.all_ready || status.has_failed) {
        stopConversionPolling()
        handleConversionComplete(status)
      }
    } catch {
      // 轮询静默失败，下次继续
    }
  }, 1000)
}

/** 停止轮询 */
function stopConversionPolling() {
  if (conversionPollTimer) {
    clearInterval(conversionPollTimer)
    conversionPollTimer = null
  }
}

/** 存储事件监听器引用，用于组件卸载时清理 */
let _conversionDoneHandler: ((e: Event) => void) | null = null

/** 监听 WebSocket 推送的 conversion_all_done 事件 */
function listenConversionDone() {
  const currentTaskId = detail.value?.id
  const handler = (e: Event) => {
    const cd = (e as CustomEvent).detail
    // 确认是当前任务的通知
    if (cd.task_id !== currentTaskId) return
    stopConversionPolling()
    handleConversionComplete(cd)
  }

  _conversionDoneHandler = handler
  window.addEventListener('conversion-all-done', handler, { once: true })
}

/** 转换完成后：检查结果 → 打开签批弹框或显示错误
 * 轮询路径传入 FilesStatusResponse（has_failed），WebSocket 路径传入 conversion_all_done 消息体（failed），两者字段不同需归一化 */
async function handleConversionComplete(status: FilesStatusResponse | { total: number; ready: number; failed: number; status?: string }) {
  waitingConversion.value = false
  stopProgressAnimation()  // 停止进度动画（进度条随 waitingConversion 消失）
  // 移除一次性 WebSocket 监听：无论由轮询还是事件触发完成都需清理，防残留监听重复处理
  if (_conversionDoneHandler) {
    window.removeEventListener('conversion-all-done', _conversionDoneHandler)
    _conversionDoneHandler = null
  }

  // 归一化失败数量：轮询结果统计 files 中的 failed 状态，WebSocket 消息直接取 failed 数字
  const failedCount = 'has_failed' in status
    ? status.files.filter(f => f.conversion_status === 'failed').length
    : status.failed

  if (failedCount > 0) {
    ElMessage.error(`${failedCount} 个文件转换失败，请检查文件格式后重新上传再提交`)
    return
  }

  // 重新调用 prepareSign 获取更新后的 PDF 文件列表
  try {
    const result = await prepareSign(detail.value!.id)
    if (result.conversion_pending) {
      // 理论上不应发生（状态已 ready），但防御性处理
      waitingConversion.value = true
      startConversionPolling(detail.value!.id)
      return
    }
    pdfFiles.value = result.files.map(f => ({
      file_id: f.id,
      name: f.original_name,
      url: f.url,
    }))
    // 转换完成后本地同步文件状态（conversion_status → ready）：徽标消失、出现预览按钮。
    // 不整页刷新，避免与「上传/删除后刷新」竞态导致 detail 被旧快照覆盖（文件夹计数回退报错）
    applyConvertedStatus(result.files)
    if (pdfFiles.value.length === 0) {
      ElMessage.warning('没有可签批的 PDF 文件，请先上传文件')
      return
    }
    openSignatureDialog()
  } catch {
    // 拦截器已统一弹错（P1-35）：网络异常与业务错误均不再重复提示，消除误报
  }
}
</script>

<style lang="scss" scoped>
.task-detail { /* max-width 由 AppLayout 内容区统一控制 */ }

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

/* 文件列表 */
.file-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.file-row { display: flex; align-items: center; gap: 10px; padding: 6px 10px; background: var(--el-bg-color-page); border-radius: 6px; font-size: 13px; }
// 文件转换状态标签
.conv-tag {
  font-size: 11px;
  line-height: 18px;
  padding: 0 7px;
  border-radius: 999px;
  flex-shrink: 0;
  white-space: nowrap;

  &--pending { color: var(--el-color-warning); background: var(--el-color-warning-light-9); }
  &--converting { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
  &--failed { color: var(--el-color-danger); background: var(--el-color-danger-light-9); }
}
// 文件转换迷你进度条（转换期间显示，伪动画 + 轮询校正）
.conv-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;

  &__bar {
    width: 64px;
    height: 8px;
    border-radius: 4px;
    background: var(--el-border-color);  // 深灰底，与文件行浅灰背景区分（不融为一条）
    overflow: hidden;
  }

  &__fill {
    display: block;
    height: 100%;
    border-radius: 4px;
    background: var(--el-color-primary);
    transition: width 0.2s linear;
  }

  &__label {
    font-size: 11px;
    color: var(--el-text-color-secondary);
    white-space: nowrap;
  }

  &.is-failed {
    .conv-progress__fill { background: var(--el-color-danger); }
    .conv-progress__label { color: var(--el-color-danger); }
  }
}
.file-size { color: var(--el-text-color-secondary); font-size: 12px; flex: 1; }
.upload-hint { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 6px; }

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

/* ─── 文件模板（模板包 + 散模板） ─── */
.card__title-hint { font-size: 12px; color: var(--el-text-color-placeholder); font-weight: 400; margin-left: 4px; }

.tpl-cat-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;

  &__header {
    display: flex; align-items: center; gap: 8px;
    padding: 10px 14px;
    cursor: pointer;
    background: var(--el-fill-color-lighter);
    transition: background 0.15s;
    user-select: none;
    &:hover { background: var(--el-fill-color-light); }
  }

  .tpl-cat-body {
    padding: 0 12px 8px 32px;
    border-top: 1px solid var(--el-border-color-lighter);
  }
}

.tpl-cat-arrow {
  transition: transform 0.2s;
  color: var(--el-text-color-secondary);
  &.is-expanded { transform: rotate(90deg); }
}

.tpl-cat-icon { font-size: 16px; }
.tpl-cat-name { font-weight: 600; font-size: 14px; color: var(--el-text-color-primary); }
.tpl-cat-count { font-size: 12px; color: var(--el-text-color-secondary); }

.doc-tpl-item {
  display: flex; align-items: center; gap: 10px; padding: 6px 0;
  &__icon { font-size: 16px; }
  &__name { flex: 1; font-size: 14px; }

  &--sub {
    padding: 4px 8px;
    border-left: 2px solid var(--el-color-primary-light-5);
    margin-bottom: 2px;
    border-radius: 0 4px 4px 0;
    &:hover { background: var(--el-fill-color-lighter); }
  }
}

.tpl-solo-section {
  border-top: 1px dashed var(--el-border-color-lighter);
  padding-top: 8px;
}

.tpl-empty {
  font-size: 12px; color: var(--el-text-color-placeholder);
  text-align: center; padding: 12px 0;
}
</style>
