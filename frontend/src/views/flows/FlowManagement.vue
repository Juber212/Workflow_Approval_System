<template>
  <div class="flow-management">
    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab">
      <el-tab-pane label="流程模板" name="template" />
      <el-tab-pane label="流程实例" name="instance" />
    </el-tabs>

    <!-- 模板 Tab -->
    <template v-if="activeTab === 'template'">
      <OrgCardList
        :orgs="orgs"
        :active-org-id="selectedOrgId"
        @select="handleOrgSelect"
      />

      <el-divider />

      <TemplateTable
        :items="templates"
        :loading="loading"
        :total="total"
        @search="handleSearch"
        @create="handleCreate"
        @detail="handleDetail"
        @edit="handleEdit"
        @publish="handlePublish"
        @disable="handleDisable"
        @new-version="handleNewVersion"
        @delete="handleDelete"
        @start="handleStart"
        @page-change="handlePageChange"
      />
    </template>

    <!-- 实例 Tab（占位） -->
    <el-empty v-else description="流程实例功能开发中" />

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="formVisible"
      :title="editingTpl ? '编辑模板' : '新建模板'"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="模板名称" prop="name">
          <el-input v-model="form.name" maxlength="50" placeholder="请输入模板名称" />
        </el-form-item>
        <el-form-item label="所属组织" prop="organization_id">
          <el-select v-model="form.organization_id" :disabled="!!editingTpl" placeholder="请选择组织" style="width: 100%">
            <el-option v-for="o in orgs" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  getTemplateOrganizations,
  getTemplates,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  publishTemplate,
  disableTemplate,
  newVersionTemplate,
  type OrgCardItem,
  type TemplateItem,
} from '@/api/template'
import OrgCardList from './components/OrgCardList.vue'
import TemplateTable from './components/TemplateTable.vue'

const router = useRouter()

// ========== 数据 ==========
const activeTab = ref('template')
const orgs = ref<OrgCardItem[]>([])
const templates = ref<TemplateItem[]>([])
const loading = ref(false)
const total = ref(0)
const selectedOrgId = ref<number | null>(null)

const searchParams = reactive({ keyword: '', status: '' })
const currentPage = ref(1)

// ========== 表单 ==========
const formVisible = ref(false)
const saving = ref(false)
const editingTpl = ref<TemplateItem | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  description: '' as string | null,
  organization_id: null as number | null,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  organization_id: [{ required: true, message: '请选择组织', trigger: 'change' }],
}

// ========== 初始化 ==========
onMounted(async () => {
  await Promise.all([fetchOrgs(), fetchTemplates()])
})

async function fetchOrgs() {
  orgs.value = await getTemplateOrganizations()
}

async function fetchTemplates() {
  loading.value = true
  try {
    const data = await getTemplates({
      page: currentPage.value,
      organization_id: selectedOrgId.value ?? undefined,
      keyword: searchParams.keyword || undefined,
      status: searchParams.status || undefined,
    })
    templates.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

// ========== 组织卡片 ==========
function handleOrgSelect(orgId: number) {
  selectedOrgId.value = selectedOrgId.value === orgId ? null : orgId
  fetchTemplates()
}

// ========== 搜索 ==========
function handleSearch(params: { keyword: string; status: string }) {
  searchParams.keyword = params.keyword
  searchParams.status = params.status
  currentPage.value = 1
  fetchTemplates()
}

function handlePageChange(page: number) {
  currentPage.value = page
  fetchTemplates()
}

// ========== 新建/编辑 ==========
function handleCreate() {
  editingTpl.value = null
  form.name = ''
  form.description = ''
  form.organization_id = null
  formVisible.value = true
}

function handleEdit(row: TemplateItem) {
  editingTpl.value = row
  form.name = row.name
  form.description = row.description
  form.organization_id = row.organization_id
  formVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    if (editingTpl.value) {
      await updateTemplate(editingTpl.value.id, { name: form.name, description: form.description })
      ElMessage.success('模板信息已更新')
    } else {
      await createTemplate({ name: form.name, description: form.description, organization_id: form.organization_id! })
      ElMessage.success('模板创建成功')
    }
    formVisible.value = false
    fetchTemplates()
  } finally {
    saving.value = false
  }
}

// ========== 删除 ==========
async function handleDelete(id: number) {
  await deleteTemplate(id)
  ElMessage.success('模板已删除')
  fetchTemplates()
}

// ========== 发布 ==========
async function handlePublish(id: number) {
  try {
    const result = await publishTemplate(id)
    ElMessage.success(`模板已发布（v${result.version_number}）`)
    fetchTemplates()
  } catch {
    // 错误已由拦截器统一处理
  }
}

// ========== 停用 ==========
async function handleDisable(id: number) {
  try {
    await disableTemplate(id)
    ElMessage.success('模板已停用')
    fetchTemplates()
  } catch {
    // 错误已由拦截器统一处理
  }
}

// ========== 新版本 ==========
async function handleNewVersion(id: number) {
  try {
    await newVersionTemplate(id)
    ElMessage.success('新版本草稿已创建，请编辑后重新发布')
    fetchTemplates()
  } catch {
    // 错误已由拦截器统一处理
  }
}

// ========== 详情 ==========
function handleDetail(id: number) {
  router.push(`/flows/detail/${id}`)
}

// ========== 发起实例 ==========
function handleStart(_id: number) {
  router.push('/flows/start')
}
</script>
