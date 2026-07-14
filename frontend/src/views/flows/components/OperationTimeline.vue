<template>
  <!-- 操作日志时间线 -->
  <div class="card" v-if="logs && logs.length > 0">
    <div class="card__header">
      <h3 class="card__title">操作日志</h3>
      <span class="card__extra" v-if="total > logs.length">共 {{ total }} 条</span>
    </div>
    <div class="card__body">
      <el-timeline>
        <el-timeline-item
          v-for="log in logs"
          :key="log.id"
          :timestamp="formatTime(log.created_at)"
          placement="top"
          :color="logColor(log.operation_type)"
          size="normal"
        >
          <div class="log-content">
            <span class="log-operator">{{ log.operator_name || '系统' }}</span>
            <span class="log-type-tag">{{ logTypeLabel(log.operation_type) }}</span>
            <span class="log-desc">{{ log.description }}</span>
          </div>
        </el-timeline-item>
      </el-timeline>
      <div v-if="logs.length === 0" class="log-empty">暂无操作日志</div>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 操作日志时间线 —— 使用 el-timeline 展示操作记录 */
import type { LogItemBrief } from '@/api/instance'

defineProps<{
  logs: LogItemBrief[]
  total?: number
}>()

/** 操作类型中文映射 */
function logTypeLabel(type: string): string {
  const map: Record<string, string> = {
    instance_created: '发起实例',
    node_started: '节点开始',
    node_submitted: '节点提交',
    node_completed: '节点完成',
    node_skipped: '节点跳过',
    check_passed: '校验通过',
    check_rejected: '校验退回',
    approval_approved: '审批通过',
    approval_rejected: '审批退回',
    instance_completed: '流程完成',
    instance_terminated: '流程终止',
    instance_rejected: '流程驳回',
    personnel_changed: '人员变更',
    priority_changed: '优先级变更',
    file_uploaded: '文件上传',
    file_deleted: '文件删除',
  }
  return map[type] || type
}

/** 操作类型对应颜色 */
function logColor(type: string): string {
  if (type.includes('rejected') || type.includes('terminated')) return 'var(--el-color-danger)'
  if (type.includes('completed') || type.includes('passed') || type.includes('approved')) return 'var(--el-color-success)'
  if (type.includes('created') || type.includes('started')) return 'var(--el-color-primary)'
  return 'var(--el-color-info)'
}

function formatTime(val: string | null): string {
  if (!val) return ''
  return val.replace('T', ' ').substring(0, 16)
}
</script>

<style lang="scss" scoped>
.card__extra {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.log-content {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  line-height: 1.6;
}

.log-operator {
  font-weight: 500;
  color: var(--el-text-color-primary);
  font-size: 13px;
}

.log-type-tag {
  display: inline-flex;
  align-items: center;
  padding: 0 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  line-height: 20px;
}

.log-desc {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.log-empty {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
  padding: 20px 0;
  text-align: center;
}
</style>
