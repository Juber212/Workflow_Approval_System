<template>
  <div class="start-instance">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header__info">
        <h1 class="page-header__title">发起项目</h1>
        <p class="page-header__subtitle" v-if="selectedTemplate">
          基于「{{ selectedTemplate.name }}」发起，可逐节点调整配置
        </p>
        <p class="page-header__subtitle" v-else>
          请先选择一个已发布的项目模板
        </p>
      </div>
    </div>

    <!-- 选择模板（未选择时显示） -->
    <div class="card" v-if="!selectedTemplate" v-loading="loadingTemplates">
      <div class="card__header">
        <h3 class="card__title">选择项目模板</h3>
      </div>
      <div class="card__body">
        <div class="template-grid" v-if="publishedTemplates.length > 0">
          <div
            v-for="tpl in publishedTemplates"
            :key="tpl.id"
            class="template-card"
            @click="selectTemplate(tpl)"
          >
            <div class="tpl-name">{{ tpl.name }}</div>
            <div class="tpl-meta">
              <span class="status-tag status-tag--published">已发布</span>
              <span>{{ tpl.node_count }} 个节点</span>
            </div>
            <div class="tpl-org">{{ tpl.organization_name }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无可用的已发布模板" :image-size="60" />
      </div>
    </div>

    <!-- 模板信息（选中后只读展示） -->
    <div class="card" v-if="selectedTemplate">
      <div class="card__header">
        <h3 class="card__title">模板信息</h3>
        <span class="status-tag status-tag--published">已发布</span>
      </div>
      <div class="card__body">
        <div class="info-grid">
          <div class="info-grid__item">
            <div class="k">模板名称</div>
            <div class="v">{{ selectedTemplate.name }}</div>
          </div>
          <div class="info-grid__item">
            <div class="k">所属组织</div>
            <div class="v">{{ selectedTemplate.organization_name }}</div>
          </div>
          <div class="info-grid__item">
            <div class="k">节点数</div>
            <div class="v stat-num" style="font-size:20px">{{ selectedTemplate.node_count }}</div>
          </div>
          <div class="info-grid__item">
            <div class="k">审批策略</div>
            <div class="v">
              <el-tag size="small" type="primary" effect="plain">全部通过</el-tag>
            </div>
          </div>
        </div>
        <el-button text type="primary" size="small" @click="selectedTemplate = null" style="margin-top:12px">
          重新选择模板
        </el-button>
      </div>
    </div>

    <!-- 项目信息 -->
    <div class="card" v-if="selectedTemplate">
      <div class="card__header">
        <h3 class="card__title">项目信息</h3>
      </div>
      <div class="card__body">
        <el-form
          ref="formRef"
          :model="form"
          :rules="formRules"
          label-width="80px"
        >
          <el-form-item label="项目名称" prop="name">
            <el-input
              v-model="form.name"
              placeholder="请输入项目名称（2-100字符）"
              maxlength="100"
              show-word-limit
              style="max-width: 480px"
              @blur="handleNameBlur"
            />
            <div class="name-hint" v-if="form.name.trim().length >= 2">
              <el-icon><InfoFilled /></el-icon>
              <span>建议使用唯一、易识别的名称，方便后续查找与追踪</span>
            </div>
          </el-form-item>

          <el-form-item label="补充说明">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="2"
              placeholder="可选，补充说明此实例的业务背景"
              maxlength="500"
              show-word-limit
              style="max-width: 480px"
            />
          </el-form-item>

          <el-form-item label="优先级" style="max-width: 280px">
            <el-select v-model="form.priority" style="width: 100%">
              <el-option label="🔴 紧急" value="urgent" />
              <el-option label="🟠 高" value="high" />
              <el-option label="🔵 普通" value="normal" />
              <el-option label="🟢 低" value="low" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <!-- 节点配置调整 -->
    <div class="card" v-if="selectedTemplate && templateNodes.length > 0">
      <div class="card__header">
        <h3 class="card__title">节点配置调整</h3>
        <span style="font-size:12px;color:var(--el-text-color-secondary)">
          默认使用模板配置，展开可逐节点修改
        </span>
      </div>
      <div class="card__body">
        <NodeOverridePanel
          ref="nodePanelRef"
          :nodes="templateNodes"
          :overrides="nodeOverrides"
          @update:overrides="nodeOverrides = $event"
        />

        <!-- 节点配置问题汇总 -->
        <el-alert
          v-if="nodeIssues.length > 0"
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 16px"
        >
          <template #title>以下节点配置存在问题，请修正后提交：</template>
          <ul style="margin:0;padding-left:18px">
            <li v-for="err in nodeIssues" :key="err.nodeId" style="font-size:13px;line-height:1.8">
              <strong>{{ err.nodeName }}</strong>：{{ err.issues.join('、') }}
            </li>
          </ul>
        </el-alert>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div class="page-actions" v-if="selectedTemplate">
      <el-button @click="$router.push('/flows')">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="!canSubmit"
        @click="handleSubmit"
      >
        确认发起
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 发起项目页面 —— 选择模板 → 填写信息 → 调整节点配置 → 发起 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  getTemplates,
  type TemplateItem,
  type TemplateNodeItem,
} from '@/api/template'
import { getTemplateDetail } from '@/api/template'
import { createInstance, type NodeOverride } from '@/api/instance'
import NodeOverridePanel from './components/NodeOverridePanel.vue'

const router = useRouter()

// ========== 状态 ==========
const loadingTemplates = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const nodePanelRef = ref<InstanceType<typeof NodeOverridePanel> | null>(null)

const publishedTemplates = ref<TemplateItem[]>([])
const selectedTemplate = ref<TemplateItem | null>(null)
const templateNodes = ref<TemplateNodeItem[]>([])

const form = ref({
  name: '',
  description: '',
  priority: 'normal' as string,
})

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入项目名称', trigger: 'blur' },
    { min: 2, max: 100, message: '项目名称需 2-100 个字符', trigger: 'blur' },
  ],
}

const nodeOverrides = ref<Record<number, Record<string, any>>>({})
const nodeIssues = ref<{ nodeId: number; nodeName: string; issues: string[] }[]>([])

const canSubmit = computed(() => {
  if (!selectedTemplate.value) return false
  if (form.value.name.trim().length < 2) return false
  const hasEmptyRequired = nodeIssues.value.length > 0
  return !hasEmptyRequired
})

// ========== 生命周期 ==========
onMounted(() => {
  loadTemplates()
})

watch(nodeOverrides, () => {
  setTimeout(refreshNodeIssues, 100)
}, { deep: true })

// ========== 方法 ==========

async function loadTemplates() {
  loadingTemplates.value = true
  try {
    const data = await getTemplates({ status: 'published', page_size: 100 })
    publishedTemplates.value = data.items
  } catch {
    ElMessage.error('加载模板列表失败')
  } finally {
    loadingTemplates.value = false
  }
}

function handleNameBlur() {
  refreshNodeIssues()
}

function refreshNodeIssues() {
  if (nodePanelRef.value && typeof nodePanelRef.value.validate === 'function') {
    nodeIssues.value = nodePanelRef.value.validate()
  }
}

async function selectTemplate(tpl: TemplateItem) {
  selectedTemplate.value = tpl
  form.value.name = ''
  form.value.description = ''
  form.value.priority = 'normal'
  nodeOverrides.value = {}
  nodeIssues.value = []

  try {
    const detail = await getTemplateDetail(tpl.id)
    templateNodes.value = detail.nodes
    // 简化版模板无版本体系，直接使用模板节点
  } catch {
    ElMessage.error('加载模板节点信息失败')
    templateNodes.value = []
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || !selectedTemplate.value) return

  refreshNodeIssues()
  if (nodeIssues.value.length > 0) {
    ElMessage.warning('请修正节点配置问题后再提交')
    return
  }

  submitting.value = true
  try {
    const overrides: NodeOverride[] = []
    for (const [nodeIdStr, config] of Object.entries(nodeOverrides.value)) {
      const nodeId = Number(nodeIdStr)
      const override: NodeOverride = { node_id: nodeId }

      if (config.assignee_id !== undefined) override.assignee_id = config.assignee_id
      if (config.deadline) override.deadline = config.deadline
      if (config.checkers_ids?.length > 0) {
        override.checkers = config.checkers_ids.map((id: number) => ({ user_id: id }))
      }
      if (config.approvers_ids?.length > 0) {
        override.approvers = config.approvers_ids.map((id: number) => ({ user_id: id }))
      }
      overrides.push(override)
    }

    const result = await createInstance({
      template_id: selectedTemplate.value.id,
      name: form.value.name.trim(),
      description: form.value.description?.trim() || null,
      priority: form.value.priority,
      node_overrides: overrides.length > 0 ? overrides : undefined,
    })

    ElMessage.success(`流程「${result.name}」发起成功`)
    router.push('/flows')
  } catch (err: any) {
    const msg = err?.response?.data?.message || err?.message || '发起失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.start-instance {
  /* max-width 由 AppLayout 内容区统一控制 */

  // 模板卡片网格
  .template-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px;
  }

  .template-card {
    border: 2px solid var(--el-border-color);
    border-radius: 8px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      border-color: var(--el-color-primary-light-3);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
      transform: translateY(-1px);
    }

    .tpl-name {
      font-size: 15px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin-bottom: 8px;
    }

    .tpl-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }

    .tpl-org {
      font-size: 12px;
      color: var(--el-text-color-placeholder);
      margin-top: 8px;
    }
  }

  // 名称唯一性提示
  .name-hint {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 6px;
    font-size: 12px;
    color: var(--el-text-color-secondary);

    .el-icon {
      font-size: 14px;
      color: var(--el-color-info);
    }
  }
}
</style>
