<template>
  <div class="template-detail" v-loading="loading">
    <div class="page-header-row">
      <el-page-header @back="$router.push('/flows')" :content="detail?.name || '模板详情'" />
      <div class="header-actions" v-if="detail">
        <el-button type="primary" @click="$router.push(`/flows/designer/${detail.id}`)">编辑流程</el-button>
      </div>
    </div>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 基础信息 + 版本历史 -->
      <el-col :span="12">
        <TemplateInfo v-if="detail" :detail="detail" />
      </el-col>

      <!-- 节点配置列表 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>节点配置</template>
          <el-table :data="detail?.nodes || []" stripe size="small">
            <el-table-column prop="name" label="名称" width="100" />
            <el-table-column label="类型" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.is_start" type="success" size="small">开始</el-tag>
                <el-tag v-else-if="row.is_end" type="warning" size="small">结束</el-tag>
                <el-tag v-else type="info" size="small">工作</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="负责人" min-width="100">
              <template #default="{ row }">{{ row.assignee_id ? 'ID:' + row.assignee_id : '未设置' }}</template>
            </el-table-column>
            <el-table-column label="时限" width="80">
              <template #default="{ row }">{{ row.time_limit_days || '-' }}天</template>
            </el-table-column>
            <el-table-column label="可选" width="60" align="center">
              <template #default="{ row }">{{ row.is_optional ? '是' : '否' }}</template>
            </el-table-column>
            <el-table-column label="需文件" width="70" align="center">
              <template #default="{ row }">{{ row.require_file ? '是' : '否' }}</template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 连线 -->
        <el-card v-if="detail?.edges?.length" shadow="never" style="margin-top: 16px">
          <template #header>连线（{{ detail.edges.length }} 条）</template>
          <div v-for="e in detail.edges" :key="e.id" class="edge-row">
            {{ getNodeName(e.source_node_id) }} → {{ getNodeName(e.target_node_id) }}
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getTemplateDetail, type TemplateDetail } from '@/api/template'
import TemplateInfo from './components/TemplateInfo.vue'

const route = useRoute()
const loading = ref(false)
const detail = ref<TemplateDetail | null>(null)

async function fetchDetail() {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try { detail.value = await getTemplateDetail(id) }
  finally { loading.value = false }
}

onMounted(fetchDetail)

function getNodeName(nodeId: number) {
  const node = detail.value?.nodes.find(n => n.id === nodeId)
  return node?.name || `ID:${nodeId}`
}
</script>

<style lang="scss" scoped>
.page-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.edge-row {
  padding: 4px 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
