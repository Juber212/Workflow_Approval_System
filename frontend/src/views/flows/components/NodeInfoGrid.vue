<template>
  <!-- 节点信息共享卡 —— 流程进度 + 8 栏信息网格（Task/Check/Approval/Endorse 四页共用，P2-2 抽取） -->
  <div class="node-info-grid">
    <!-- 流程进度条 -->
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
        <!-- 节点说明：独占一行（文字可能较长） -->
        <div v-if="detail.node_description" class="node-desc">{{ detail.node_description }}</div>
        <div class="info-grid">
          <!-- 终审节点不展示完成时限与截止时间（终审只确认文件齐全） -->
          <div v-if="!isEndNode" class="info-grid__item">
            <div class="k">完成时限</div>
            <div class="v">{{ detail.time_limit_days ? detail.time_limit_days + '工作日' : '未设置' }}</div>
          </div>
          <div v-if="!isEndNode" class="info-grid__item">
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
  </div>
</template>

<script setup lang="ts">
import { formatTime } from '@/utils/format'
import { priLabel, instStatusClass, instStatusLabel } from '@/utils/labels'
import ProgressBar from './ProgressBar.vue'

/** 节点信息卡需要的字段（四页详情数据结构同构，此处鸭子类型） */
export interface NodeInfoGridDetail {
  instance_id: number
  nodes: Array<{ id: number; name: string; is_start: boolean; is_end: boolean; status: string; sort_order?: number }>
  node_description?: string | null
  time_limit_days?: number | null
  deadline?: string | null
  initiator_name: string
  priority: string
  difficulty: string | number
  instance_status: string
  current_node_index: number
  total_nodes: number
  round: number
}

defineProps<{
  detail: NodeInfoGridDetail
  /** 终审节点（隐藏完成时限/截止时间两项） */
  isEndNode?: boolean
}>()
</script>

<style lang="scss" scoped>
/* 查看完整流程链接 */
.view-flow-link {
  font-size: 13px; color: var(--el-color-primary); text-decoration: none;
  font-weight: 400;
  &:hover { text-decoration: underline; }
}

/* 节点说明 */
.node-desc {
  font-size: 13px; color: var(--el-text-color-secondary);
  padding: 8px 12px; background: var(--el-bg-color-page);
  border-radius: 6px; margin-bottom: 12px; line-height: 1.6;
}

.empty-hint { color: var(--el-text-color-placeholder); font-size: 13px; text-align: center; padding: 12px; }
</style>
