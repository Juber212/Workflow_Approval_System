<template>
  <div class="start-instance">
    <!-- 顶部导航 -->
    <div class="page-header">
      <el-page-header @back="$router.push('/flows')" content="发起流程实例" />
    </div>

    <!-- 步骤一：选择模板 -->
    <div class="section" v-loading="loadingTemplates">
      <h3 class="section-title">1. 选择流程模板</h3>
      <div class="template-grid" v-if="publishedTemplates.length > 0">
        <div
          v-for="tpl in publishedTemplates"
          :key="tpl.id"
          class="template-card"
          :class="{ selected: selectedTemplate?.id === tpl.id }"
          @click="selectTemplate(tpl)"
        >
          <div class="tpl-name">{{ tpl.name }}</div>
          <div class="tpl-meta">
            <el-tag size="small" :type="tpl.status === 'published' ? 'success' : 'info'">
              {{ tpl.status === 'published' ? '已发布' : tpl.status }}
            </el-tag>
            <span>v{{ tpl.current_version }}</span>
            <span>{{ tpl.node_count }} 个节点</span>
          </div>
          <div class="tpl-org">{{ tpl.organization_name }}</div>
        </div>
      </div>
      <el-empty v-else description="暂无可用的已发布模板" :image-size="60" />
    </div>

    <!-- 步骤二：填写基本信息 -->
    <div class="section" v-if="selectedTemplate">
      <h3 class="section-title">2. 基本信息</h3>
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="80px"
        class="basic-form"
      >
        <el-form-item label="实例名称" prop="name">
          <el-input
            v-model="form.name"
            placeholder="请输入流程实例名称（2-100字符）"
            maxlength="100"
            show-word-limit
            style="max-width: 480px"
          />
        </el-form-item>

        <el-form-item label="补充说明" prop="description">
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

        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width: 200px">
            <el-option label="🔴 紧急" value="urgent" />
            <el-option label="🟠 高" value="high" />
            <el-option label="🔵 普通" value="normal" />
            <el-option label="🟢 低" value="low" />
          </el-select>
        </el-form-item>
      </el-form>
    </div>

    <!-- 步骤三：节点配置调整 -->
    <div class="section" v-if="selectedTemplate && templateNodes.length > 0">
      <h3 class="section-title">3. 节点配置调整</h3>
      <NodeOverridePanel
        :nodes="templateNodes"
        :overrides="nodeOverrides"
        @update:overrides="nodeOverrides = $event"
      />
    </div>

    <!-- 底部操作栏 -->
    <div class="section footer-bar" v-if="selectedTemplate">
      <el-button @click="$router.push('/flows')">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="!canSubmit"
        @click="handleSubmit"
      >
        确认发起流程
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 发起流程实例页面 —— 选择模板 → 填写信息 → 调整节点配置 → 发起 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  getTemplates,
  type TemplateItem,
  type TemplateNodeItem,
} from '@/api/template'
import { getTemplateDetail } from '@/api/template'
import { createInstance, type NodeOverride } from '@/api/instance'

const router = useRouter()

// ========== 状态 ==========
const loadingTemplates = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()

/** 已发布的模板列表 */
const publishedTemplates = ref<TemplateItem[]>([])
/** 当前选中的模板 */
const selectedTemplate = ref<TemplateItem | null>(null)
/** 选中模板的版本 ID（flow_versions 记录 ID） */
const selectedVersionId = ref<number>(0)
/** 选中模板的节点列表 */
const templateNodes = ref<TemplateNodeItem[]>([])

/** 基本信息表单 */
const form = ref({
  name: '',
  description: '',
  priority: 'normal' as string,
})

/** 表单校验规则 */
const formRules: FormRules = {
  name: [
    { required: true, message: '请输入实例名称', trigger: 'blur' },
    { min: 2, max: 100, message: '实例名称需 2-100 个字符', trigger: 'blur' },
  ],
}

/** 节点覆盖配置：{ [nodeId]: { assignee_id?, deadline?, checkers_ids?, approvers_ids?, skip? } } */
const nodeOverrides = ref<Record<number, Record<string, any>>>({})

/** 是否可以提交 */
const canSubmit = computed(() => {
  return selectedTemplate.value !== null && form.value.name.trim().length >= 2
})

// ========== 生命周期 ==========
onMounted(() => {
  loadTemplates()
})

// ========== 方法 ==========

/** 加载已发布模板列表 */
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

/** 选择模板 */
async function selectTemplate(tpl: TemplateItem) {
  selectedTemplate.value = tpl
  form.value.name = ''
  form.value.description = ''
  form.value.priority = 'normal'
  nodeOverrides.value = {}

  // 加载模板详情获取节点列表和版本ID
  try {
    const detail = await getTemplateDetail(tpl.id)
    templateNodes.value = detail.nodes

    // 从版本列表中获取最新发布版本的真实 ID
    const publishedVersion = detail.versions
      ?.filter((v: any) => v.status === 'published')
      .sort((a: any, b: any) => b.version_number - a.version_number)[0]

    selectedVersionId.value = publishedVersion?.id ?? 0

    if (!selectedVersionId.value) {
      ElMessage.error('该模板没有已发布的版本，无法发起实例')
      selectedTemplate.value = null
    }
  } catch {
    ElMessage.error('加载模板节点信息失败')
    templateNodes.value = []
  }
}

/** 提交发起 */
async function handleSubmit() {
  // 表单校验
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || !selectedTemplate.value) return

  submitting.value = true
  try {
    // 构建 node_overrides（将内部格式转为 API 格式）
    const overrides: NodeOverride[] = []
    for (const [nodeIdStr, config] of Object.entries(nodeOverrides.value)) {
      const nodeId = Number(nodeIdStr)
      const override: NodeOverride = { node_id: nodeId }

      if (config.skip) {
        override.skip = true
      } else {
        if (config.assignee_id !== undefined) override.assignee_id = config.assignee_id
        if (config.deadline) override.deadline = config.deadline
        if (config.checkers_ids?.length > 0) {
          override.checkers = config.checkers_ids.map((id: number) => ({ user_id: id }))
        }
        if (config.approvers_ids?.length > 0) {
          override.approvers = config.approvers_ids.map((id: number) => ({ user_id: id }))
        }
      }
      overrides.push(override)
    }

    const result = await createInstance({
      template_id: selectedTemplate.value.id,
      version_id: selectedVersionId.value,
      name: form.value.name.trim(),
      description: form.value.description?.trim() || null,
      priority: form.value.priority,
      node_overrides: overrides.length > 0 ? overrides : undefined,
    })

    ElMessage.success(`流程「${result.name}」发起成功`)
    // 跳转到流程管理页（实例详情页尚未开发）
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
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;

  .page-header {
    margin-bottom: 24px;
  }

  .section {
    margin-bottom: 28px;

    .section-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin-bottom: 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--el-border-color-light);
    }
  }

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
    }

    &.selected {
      border-color: var(--el-color-primary);
      background: var(--el-color-primary-light-9);
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

  .basic-form {
    margin-top: 8px;
  }

  .footer-bar {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    padding-top: 16px;
    border-top: 1px solid var(--el-border-color-light);
  }
}
</style>
