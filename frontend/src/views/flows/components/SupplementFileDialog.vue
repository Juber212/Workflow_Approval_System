<template>
  <!-- 补交文件弹窗 —— 两步流程：选择节点（可选）+ 上传文件 -->
  <el-dialog
    v-model="visible"
    title="补交文件"
    width="520px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="supplement" v-loading="submitting">
      <!-- ===== 第1步：选择目标节点（全局入口时显示） ===== -->
      <div v-if="!props.preselectedNodeId" class="supplement__step">
        <div class="supplement__label">选择补交目标节点</div>
        <el-select
          v-model="selectedNodeId"
          placeholder="请选择已完成的工作节点"
          style="width: 100%"
          :disabled="submitting"
        >
          <el-option
            v-for="n in eligibleNodes"
            :key="n.id"
            :label="`${n.sort_order}. ${n.name}`"
            :value="n.id"
          />
        </el-select>
        <div v-if="eligibleNodes.length === 0" class="supplement__empty">
          没有可补交的节点（需要已完成的非开始/结束节点）
        </div>
      </div>

      <!-- ===== 第2步：上传文件区 ===== -->
      <div class="supplement__step" :class="{ 'is-disabled': !canUpload }">
        <div class="supplement__label">上传文件</div>
        <!-- 拖拽/点击上传 -->
        <el-upload
          ref="uploadRef"
          v-model:file-list="fileList"
          :auto-upload="false"
          :multiple="true"
          :accept="'.pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.gif,.webp'"
          :before-upload="beforeUpload"
          :disabled="!canUpload || submitting"
          drag
        >
          <el-icon class="supplement__upload-icon" :size="32"><UploadFilled /></el-icon>
          <div class="supplement__upload-text">拖拽文件到此处，或点击上传</div>
          <div class="supplement__upload-hint">支持 PDF / Word / Excel / 图片，单文件 ≤ 50MB</div>
        </el-upload>
      </div>
    </div>

    <!-- 底部按钮 -->
    <template #footer>
      <el-button @click="visible = false" :disabled="submitting">取消</el-button>
      <el-button
        type="primary"
        :disabled="!canSubmit"
        :loading="submitting"
        @click="handleSubmit"
      >
        确认补交（{{ fileList.length }} 个文件）
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 补交文件弹窗 —— 节点选择 + 多文件上传，支持全局入口和节点卡片入口 */
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadInstance, UploadRawFile } from 'element-plus'
import { supplementFiles } from '@/api/instance'
import type { DetailNodeInfo } from '@/api/instance'

// ========== Props & Emits ==========
const props = defineProps<{
  modelValue: boolean          // 弹窗可见性
  instanceId: number           // 实例 ID
  nodes: DetailNodeInfo[]      // 实例全部节点（全局入口时用于筛选）
  preselectedNodeId?: number   // 预选节点（节点卡片入口时传入）
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  success: []
}>()

// ========== 双向绑定弹窗可见性 ==========
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// ========== 状态 ==========
const uploadRef = ref<UploadInstance>()
const fileList = ref<UploadFile[]>([])
const submitting = ref(false)

/** 可补交节点列表：finished + 非开始/结束 */
const eligibleNodes = computed(() =>
  props.nodes.filter(n => {
    if (n.is_start || n.is_end) return false
    return (n.status || '').toLowerCase() === 'finished'
  })
)

/** 当前选中的节点 ID */
const selectedNodeId = ref<number | null>(
  props.preselectedNodeId || (eligibleNodes.value.length > 0 ? null : null)
)

// 当 preselectedNodeId 变化时同步（父组件重新打开弹窗时）
watch(
  () => props.preselectedNodeId,
  (val) => {
    selectedNodeId.value = val || null
  }
)

/** 是否可上传：必须已选中节点 */
const canUpload = computed(() =>
  !!props.preselectedNodeId || selectedNodeId.value !== null
)

/** 是否可提交：已选中节点 + 有文件 + 未提交中 */
const canSubmit = computed(() =>
  canUpload.value && fileList.value.length > 0 && !submitting.value
)

// ========== 文件预校验 ==========
function beforeUpload(rawFile: UploadRawFile): boolean {
  // 文件大小校验
  if (rawFile.size > 50 * 1024 * 1024) {
    ElMessage.warning(`文件「${rawFile.name}」超过 50MB 限制`)
    return false
  }
  return true
}

// ========== 提交补交 ==========
async function handleSubmit() {
  const nodeId = props.preselectedNodeId || selectedNodeId.value
  const files = fileList.value.map(f => f.raw!)

  if (!nodeId || files.length === 0) return

  submitting.value = true
  try {
    await supplementFiles(props.instanceId, nodeId, files)
    ElMessage.success('文件补交成功')
    visible.value = false
    emit('success')
  } catch (err: any) {
    const msg = err?.response?.data?.message || err?.message || '补交失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

// ========== 关闭时重置状态 ==========
function handleClose() {
  fileList.value = []
  if (!props.preselectedNodeId) {
    selectedNodeId.value = null
  }
}
</script>

<style lang="scss" scoped>
.supplement {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.supplement__step {
  &.is-disabled {
    opacity: 0.45;
    pointer-events: none;
  }
}

.supplement__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}

.supplement__empty {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  text-align: center;
  padding: 12px 0;
}

.supplement__upload-icon {
  color: var(--el-text-color-placeholder);
}

.supplement__upload-text {
  font-size: 14px;
  color: var(--el-text-color-regular);
  margin-top: 6px;
}

.supplement__upload-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 4px;
}
</style>
