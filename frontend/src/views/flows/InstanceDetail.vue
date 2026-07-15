<template>
  <!-- 流程实例详情页 —— 基本信息 + 进度条 + 节点卡片 + 操作日志 -->
  <div class="instance-detail" v-loading="loading">
    <!-- 空数据 -->
    <el-empty v-if="!loading && !detail" description="实例不存在或无权访问" :image-size="60" />

    <template v-if="detail">
      <!-- 粘性头部：基本信息 + 进度 + 操作 -->
      <InstanceInfo
        :detail="detail"
        :is-initiator="isInitiator"
        @supplement="handleSupplement"
        @change-priority="handleChangePriority"
        @terminate="handleTerminate"
      />

      <!-- 流程节点卡片列表 -->
      <h3 class="section-title">流程节点</h3>
      <NodeCard
        v-for="node in detail.nodes"
        :key="node.id"
        :node="node"
        :is-initiator="isInitiator"
        @change-personnel="handleChangePersonnel"
      />

      <!-- 实例补充说明 -->
      <div class="card" v-if="detail.description">
        <div class="card__header">
          <h3 class="card__title">补充说明</h3>
        </div>
        <div class="card__body">
          <p class="desc-text">{{ detail.description }}</p>
        </div>
      </div>

      <!-- 操作日志时间线 -->
      <OperationTimeline
        :logs="detail.logs?.items || []"
        :total="detail.logs?.total || 0"
      />

      <!-- 终止流程确认弹窗 -->
      <TerminateDialog
        v-if="detail"
        v-model="showTerminateDialog"
        :instance-id="detail.id"
        :instance-name="detail.name"
        :instance-status="detail.status"
        @terminated="handleTerminated"
      />

      <!-- 优先级修改弹窗 -->
      <PriorityEditDialog
        v-if="detail"
        v-model="showPriorityDialog"
        :instance-id="detail.id"
        :current-priority="detail.priority"
        @changed="handlePriorityChanged"
      />

      <!-- 修改人员弹窗 -->
      <ChangePersonnelDialog
        v-if="detail"
        v-model="showPersonnelDialog"
        :instance-id="detail.id"
        :node="selectedNode"
        @success="handlePersonnelChanged"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
/** 流程实例详情页 —— 编排子组件，处理数据加载与用户交互 */
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getInstanceDetail, type InstanceDetailResponse } from '@/api/instance'
import { useUserStore } from '@/stores/user'
import InstanceInfo from './components/InstanceInfo.vue'
import NodeCard from './components/NodeCard.vue'
import OperationTimeline from './components/OperationTimeline.vue'
import TerminateDialog from './components/TerminateDialog.vue'
import PriorityEditDialog from './components/PriorityEditDialog.vue'
import ChangePersonnelDialog from './components/ChangePersonnelDialog.vue'
import type { DetailNodeInfo } from '@/api/instance'

const route = useRoute()
const userStore = useUserStore()

// ========== 状态 ==========
const loading = ref(false)
const detail = ref<InstanceDetailResponse | null>(null)
const showTerminateDialog = ref(false)
const showPriorityDialog = ref(false)
const showPersonnelDialog = ref(false)
const selectedNode = ref<DetailNodeInfo | null>(null)

/** 当前用户是否为发起人 */
const isInitiator = computed(() => {
  if (!detail.value || !userStore.userInfo) return false
  return detail.value.initiator_id === userStore.userInfo.id
})

// ========== 生命周期 ==========
onMounted(() => {
  fetchDetail()
})

// ========== 数据加载 ==========
async function fetchDetail() {
  const id = Number(route.params.id)
  if (!id) return

  loading.value = true
  try {
    detail.value = await getInstanceDetail(id)
  } catch (err: any) {
    const msg = err?.response?.data?.message || err?.message || '加载实例详情失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

// ========== 操作处理 ==========
function handleSupplement() {
  ElMessage.info('补交文件功能将在后续版本实现')
}

/** 打开优先级修改弹窗 */
function handleChangePriority() {
  showPriorityDialog.value = true
}

/** 优先级修改成功后刷新 */
function handlePriorityChanged() {
  fetchDetail()
}

/** 打开终止确认弹窗 */
function handleTerminate() {
  showTerminateDialog.value = true
}

/** 终止成功后刷新详情 */
function handleTerminated() {
  fetchDetail()
}

/** 打开修改人员弹窗 */
function handleChangePersonnel(nodeId: number) {
  if (!detail.value) return
  const node = detail.value.nodes.find(n => n.id === nodeId)
  if (node) {
    selectedNode.value = node
    showPersonnelDialog.value = true
  }
}

/** 人员修改成功后刷新详情 */
function handlePersonnelChanged() {
  fetchDetail()
}
</script>

<style lang="scss" scoped>
.instance-detail {
  /* max-width 由 AppLayout 内容区统一控制 */
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 12px;
}

.desc-text {
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.7;
  margin: 0;
  white-space: pre-wrap;
}
</style>
