<template>
  <!-- 任务处理页 —— 流程信息 + 文件上传 + 提交/草稿（PRD §9） -->
  <div class="task-detail" v-loading="loading">
    <div class="page-breadcrumb">
      <router-link to="/profile">个人中心</router-link><span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-current">任务处理{{ detail ? ' · ' + detail.instance_name : '' }}</span>
    </div>

    <el-empty v-if="!loading && !detail" description="任务不存在" :image-size="50" />

    <template v-if="detail">
      <!-- 流程信息 -->
      <div class="info-card">
        <h2>{{ detail.instance_name }}</h2>
        <div class="info-grid">
          <div><span class="k">当前节点</span><span class="v">{{ detail.node_name }}（第{{ detail.round }}轮）</span></div>
          <div><span class="k">节点说明</span><span class="v">{{ detail.node_description || '无' }}</span></div>
          <div><span class="k">完成时限</span><span class="v">{{ detail.time_limit_days ? detail.time_limit_days + '天' : '未设置' }} · {{ formatTime(detail.deadline) }}</span></div>
          <div><span class="k">文件要求</span><span class="v">{{ detail.require_file ? '必须上传' : '可选上传' }}</span></div>
        </div>
      </div>

      <!-- 负责人备注 -->
      <div class="card">
        <div class="card__header">备注说明</div>
        <div class="card__body">
          <el-input v-model="assigneeNote" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="输入处理说明（选填）" />
        </div>
      </div>

      <!-- 文件上传区 -->
      <div class="card" v-if="canUpload">
        <div class="card__header">上传文件（{{ detail.files.length }}）</div>
        <div class="card__body">
          <div class="file-list" v-if="detail.files.length > 0">
            <div v-for="f in detail.files" :key="f.id" class="file-row">
              <span>{{ f.original_name }}</span>
              <span class="file-size">{{ formatSize(f.file_size) }}</span>
              <el-button text type="danger" size="small" @click="handleDeleteFile(f.id)">删除</el-button>
            </div>
          </div>
          <el-upload :show-file-list="false" :http-request="handleUpload" :before-upload="beforeUpload" accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg">
            <el-button type="primary" :loading="uploading">+ 上传文件</el-button>
          </el-upload>
          <div class="upload-hint">支持 PDF/Word/Excel/图片，单文件 ≤50MB</div>
        </div>
      </div>

      <!-- 检验进度（提交后可见） -->
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

      <!-- 操作按钮 -->
      <div class="actions-bar" v-if="canSubmit">
        <el-button size="large" @click="handleSaveDraft" :loading="saving">保存草稿</el-button>
        <el-button size="large" type="primary" @click="handleSubmit" :loading="submitting">提交并进入校验</el-button>
      </div>
      <div class="actions-bar" v-else-if="detail.status === 'waiting_check'">
        <el-alert type="info" title="已提交，等待校验中..." :closable="false" show-icon />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
/** 任务处理页 —— 上传文件 + 提交/保存草稿 */
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTaskDetail, saveTaskDraft, submitTask, uploadTaskFile, deleteTaskFile, type TaskDetail } from '@/api/task'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref<TaskDetail | null>(null)
const assigneeNote = ref('')
const uploading = ref(false)
const saving = ref(false)
const submitting = ref(false)

const canUpload = computed(() => detail.value && ['pending', 'processing'].includes(detail.value.status))
const canSubmit = computed(() => detail.value && ['pending', 'processing'].includes(detail.value.status))

onMounted(async () => {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    detail.value = await getTaskDetail(id)
    assigneeNote.value = detail.value.assignee_note || ''
  } finally { loading.value = false }
})

function beforeUpload(file: File) {
  if (file.size > 50 * 1024 * 1024) { ElMessage.error('文件不能超过 50MB'); return false }
  return true
}

async function handleUpload({ file }: { file: File }) {
  if (!detail.value) return
  uploading.value = true
  try {
    await uploadTaskFile(detail.value.id, file)
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
  if (detail.value.require_file && detail.value.files.length === 0) {
    ElMessage.error('该节点要求必须上传文件')
    return
  }
  submitting.value = true
  try {
    await submitTask(detail.value.id, { assignee_note: assigneeNote.value })
    ElMessage.success('任务已提交，等待校验')
    router.push('/profile')
  } finally { submitting.value = false }
}

function formatTime(v: string | null) { return v ? v.replace('T', ' ').substring(0, 16) : '-' }
function formatSize(b: number | null) { if (!b) return ''; return b < 1024 ? b + 'B' : b < 1048576 ? (b / 1024).toFixed(1) + 'KB' : (b / 1048576).toFixed(1) + 'MB' }
function checkStatusClass(s: string) { return s === 'passed' ? 'status-tag--completed' : s === 'returned' ? 'status-tag--terminated' : 'status-tag--running' }
function checkStatusLabel(s: string) { const m: Record<string, string> = { pending: '待校验', passed: '已通过', returned: '已退回' }; return m[s] || s }
</script>

<style lang="scss" scoped>
.task-detail { max-width: 900px; margin: 0 auto; }
.info-card { background: var(--el-bg-color); border: 1px solid var(--el-border-color-light); border-radius: 10px; padding: 20px; margin-bottom: 16px; }
.info-card h2 { font-size: 18px; margin: 0 0 12px; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 14px; }
.info-grid .k { color: var(--el-text-color-secondary); margin-right: 8px; }
.file-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.file-row { display: flex; align-items: center; gap: 10px; padding: 6px 10px; background: var(--el-bg-color-page); border-radius: 6px; font-size: 13px; }
.file-size { color: var(--el-text-color-secondary); font-size: 12px; flex: 1; }
.upload-hint { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 6px; }
.progress-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.opinion { color: var(--el-text-color-secondary); font-size: 12px; }
.actions-bar { display: flex; gap: 12px; margin-top: 20px; padding: 16px 0; }
</style>
