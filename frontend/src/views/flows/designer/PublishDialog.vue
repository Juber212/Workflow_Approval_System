<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="500px"
    :close-on-click-modal="false"
    destroy-on-close
    center
  >
    <!-- 发布中 loading -->
    <div v-if="publishing" class="publish-loading">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>正在校验流程并生成快照…</p>
    </div>

    <!-- 校验失败：错误列表 -->
    <div v-else-if="errors.length > 0" class="publish-errors">
      <el-alert
        title="发布校验不通过，请修复以下问题后重试"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <div class="error-list">
        <div
          v-for="(err, idx) in errors"
          :key="idx"
          class="error-item"
        >
          <span class="error-idx">{{ idx + 1 }}.</span>
          <span class="error-text">
            <!-- 解析「节点名」为可点击链接 -->
            <template v-for="(part, pi) in parseErrorParts(err)" :key="pi">
              <el-link
                v-if="part.isNode"
                type="danger"
                :underline="true"
                @click="locateNode(part.nodeName)"
              >
                「{{ part.nodeName }}」
              </el-link>
              <span v-else>{{ part.text }}</span>
            </template>
          </span>
        </div>
      </div>
      <div class="error-footer">
        <span>点击节点名可在画布中定位对应节点</span>
      </div>
    </div>

    <!-- 发布成功 -->
    <div v-else-if="result" class="publish-success">
      <el-result icon="success" title="发布成功">
        <template #sub-title>
          模板已发布至版本
          <el-tag type="success" size="large">V{{ result.version_number }}</el-tag>
        </template>
      </el-result>
      <div class="publish-stats">
        <span>{{ result.node_count }} 个节点</span>
        <el-divider direction="vertical" />
        <span>{{ result.edge_count }} 条连线</span>
      </div>
    </div>

    <template #footer>
      <el-button v-if="errors.length > 0" @click="visible = false">关闭</el-button>
      <el-button v-if="result" type="primary" @click="visible = false">完成</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import type LogicFlow from '@logicflow/core'

/** 校验错误项中解析出的部分 */
interface ErrorPart {
  text: string
  isNode: boolean
  nodeName?: string
}

const props = defineProps<{
  /** 是否显示 */
  modelValue: boolean
  /** LogicFlow 实例（定位节点用） */
  lf?: LogicFlow | null
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
}>()

/** 双向绑定 */
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

/** 发布中 */
const publishing = ref(false)

/** 校验错误列表 */
const errors = ref<string[]>([])

/** 发布成功结果 */
const result = ref<{ version_number: number; node_count: number; edge_count: number } | null>(null)

/** 弹窗标题动态切换 */
const dialogTitle = computed(() => {
  if (publishing.value) return '正在发布…'
  if (errors.value.length > 0) return '发布校验失败'
  if (result.value) return '发布成功'
  return '确认发布'
})

/** 解析错误字符串 —— 提取「节点名」为可点击链接 */
function parseErrorParts(error: string): ErrorPart[] {
  const parts: ErrorPart[] = []
  const regex = /「([^」]+)」/g
  let lastIdx = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(error)) !== null) {
    // 前置普通文本
    if (match.index > lastIdx) {
      parts.push({ text: error.slice(lastIdx, match.index), isNode: false })
    }
    // 节点名链接
    parts.push({ text: '', isNode: true, nodeName: match[1] })
    lastIdx = regex.lastIndex
  }

  // 剩余文本
  if (lastIdx < error.length) {
    parts.push({ text: error.slice(lastIdx), isNode: false })
  }

  return parts.length > 0 ? parts : [{ text: error, isNode: false }]
}

/** 点击节点名 → 定位画布 */
function locateNode(nodeName: string) {
  if (!props.lf) return

  const graphData = props.lf.getGraphData()
  const targetNode = graphData.nodes.find((n: any) =>
    n.properties?.name === nodeName || n.text?.value === nodeName
  )

  if (targetNode) {
    // 关闭弹窗 → 切到画布
    visible.value = false
    // 选中并居中节点
    props.lf.selectNodeById(String(targetNode.id))
    setTimeout(() => {
      const nodeModel = props.lf?.getNodeModelById(String(targetNode.id))
      if (nodeModel) {
        props.lf?.focusOn({ coordinate: { x: nodeModel.x, y: nodeModel.y } })
      }
    }, 100)
  }
}

/** 设置错误列表（由父组件调用） */
function setErrors(errList: string[]) {
  errors.value = errList
}

/** 设置成功结果 */
function setResult(res: { version_number: number; node_count: number; edge_count: number }) {
  result.value = res
}

/** 设置发布中状态 */
function setPublishing(val: boolean) {
  publishing.value = val
}

/** 重置状态 */
function reset() {
  errors.value = []
  result.value = null
  publishing.value = false
}

defineExpose({ setErrors, setResult, setPublishing, reset })
</script>

<style lang="scss" scoped>
.publish-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
  gap: 16px;
  color: var(--el-text-color-secondary);
}

.publish-errors {
  .error-list {
    max-height: 300px;
    overflow-y: auto;
  }

  .error-item {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    padding: 8px 0;
    border-bottom: 1px solid var(--el-border-color-lighter);
    font-size: 14px;
    line-height: 1.6;

    &:last-child { border-bottom: none; }

    .error-idx {
      color: #f56c6c;
      font-weight: 600;
      flex-shrink: 0;
    }
  }

  .error-footer {
    margin-top: 12px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    text-align: center;
  }
}

.publish-success {
  .publish-stats {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 12px;
    margin-top: 8px;
    font-size: 14px;
    color: var(--el-text-color-secondary);
  }
}
</style>
