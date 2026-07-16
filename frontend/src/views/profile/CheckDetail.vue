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
              <div class="k">流程状态</div>
              <div class="v">
                <span class="status-tag" :class="instStatusClass(detail.instance_status)">{{ instStatusLabel(detail.instance_status) }}</span>
              </div>
            </div>
            <div class="info-grid__item">
              <div class="k">节点进度</div>
              <div class="v">{{ detail.current_node_index }} / {{ detail.total_nodes }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 负责人备注 -->
      <div class="card" v-if="detail.assignee_note">
        <div class="card__header">负责人备注</div>
        <div class="card__body">{{ detail.assignee_note }}</div>
      </div>

      <!-- 文件列表 -->
      <div class="card">
        <div class="card__header">节点文件（{{ detail.files.length }}）</div>
        <div class="card__body">
          <div v-if="detail.files.length === 0" class="empty-hint">暂无文件</div>
          <div v-for="f in detail.files" :key="f.id" class="file-row">
            <span>{{ f.original_name }}</span>
            <span class="file-size">{{ formatSize(f.file_size) }}</span>
            <el-button text type="primary" size="small" @click="previewFile(f.id)">查看</el-button>
            <el-button text type="primary" size="small" @click="downloadFile(f.id)">下载</el-button>
          </div>
        </div>
      </div>

      <!-- 校验进度 -->
      <div class="card" v-if="detail.check_progress.length > 0">
        <div class="card__header">校验进度</div>
        <div class="card__body">
          <div v-for="c in detail.check_progress" :key="c.id" class="progress-row">
            <span>{{ c.checker_name }}</span>
            <span class="status-tag" :class="checkStatusClass(c.status)">{{ checkStatusLabel(c.status) }}</span>
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getCheckDetail, passCheck, returnCheck, type CheckDetail } from '@/api/check'
import { previewFile, downloadFile } from '@/api/task'
import { useBreadcrumb } from '@/composables/useBreadcrumb'
import ProgressBar from '@/views/flows/components/ProgressBar.vue'

const { setBreadcrumb } = useBreadcrumb()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref<CheckDetail | null>(null)
const opinion = ref('')
const passing = ref(false)
const returning = ref(false)

onMounted(async () => {
  setBreadcrumb([
    { label: '首页', to: '/dashboard' },
    { label: '个人中心', to: '/profile' },
    { label: '校验处理' },
  ])
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try { detail.value = await getCheckDetail(id) } finally { loading.value = false }
})

async function handlePass() {
  if (!detail.value) return
  passing.value = true
  try {
    await passCheck(detail.value.id, opinion.value || null)
    ElMessage.success('校验通过')
    router.push('/profile')
  } finally { passing.value = false }
}

async function handleReturn() {
  if (!detail.value) return
  if (!opinion.value.trim()) { ElMessage.error('退回必须填写意见'); return }
  returning.value = true
  try {
    await returnCheck(detail.value.id, opinion.value)
    ElMessage.success('已退回')
    router.push('/profile')
  } finally { returning.value = false }
}

function formatSize(b: number | null) { if (!b) return ''; return b < 1024 ? b + 'B' : b < 1048576 ? (b / 1024).toFixed(1) + 'KB' : (b / 1048576).toFixed(1) + 'MB' }
function priLabel(p: string) { const m: Record<string, string> = { urgent: '紧急', high: '高', normal: '普通', low: '低' }; return m[p] || p }
function instStatusClass(s: string) { const m: Record<string, string> = { running: 'status-tag--running', completed: 'status-tag--completed', terminated: 'status-tag--terminated' }; return m[s] || '' }
function instStatusLabel(s: string) { const m: Record<string, string> = { running: '运行中', completed: '已完成', terminated: '已终止' }; return m[s] || s }
function checkStatusClass(s: string) { return s === 'passed' ? 'status-tag--completed' : s === 'returned' ? 'status-tag--terminated' : 'status-tag--running' }
function checkStatusLabel(s: string) { const m: Record<string, string> = { pending: '待校验', passed: '已通过', returned: '已退回' }; return m[s] || s }
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
</style>
