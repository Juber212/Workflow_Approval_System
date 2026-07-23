<template>
  <div class="doc-tpl-admin" v-loading="loading">
    <!-- 上传区域 -->
    <div class="upload-bar">
      <el-select v-model="uploadOrgId" placeholder="选择组织" style="width:200px">
        <el-option v-for="org in orgs" :key="org.id" :label="org.name" :value="org.id" />
      </el-select>
      <el-upload
        :show-file-list="false"
        :before-upload="handleUpload"
        accept=".doc,.docx,.xlsx"
        :disabled="!uploadOrgId"
        style="margin-left:12px;display:inline-block"
      >
        <el-button type="primary" :disabled="!uploadOrgId">上传文件模板</el-button>
      </el-upload>
      <span style="font-size:12px;color:var(--el-text-color-secondary);margin-left:8px">支持 .doc / .docx / .xlsx，≤10MB</span>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar" style="margin-top:16px">
      <el-select v-model="filterOrgId" placeholder="按组织筛选" clearable @change="handleFilter" style="width:200px">
        <el-option v-for="org in orgs" :key="org.id" :label="org.name" :value="org.id" />
      </el-select>
      <el-input v-model="filterKeyword" placeholder="模板名称/文件名搜索" clearable @clear="handleFilter" @keyup.enter="handleFilter" style="width:260px;margin-left:12px">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button @click="handleFilter" style="margin-left:12px">搜索</el-button>
    </div>

    <!-- 表格 -->
    <el-table :data="list" stripe class="doc-table" style="margin-top:16px">
      <el-table-column prop="organization_name" label="所属组织" min-width="120" />
      <el-table-column prop="name" label="模板名称" min-width="160" />
      <el-table-column prop="original_name" label="原始文件名" min-width="180" />
      <el-table-column label="类型" width="80">
        <template #default="{ row }">
          <el-tag :type="row.file_type === 'xlsx' ? 'success' : ''" size="small" effect="plain">
            .{{ row.file_type }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="100">
        <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
      </el-table-column>
      <el-table-column label="上传时间" width="160">
        <template #default="{ row }">{{ row.created_at?.slice(0, 16) || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="80" align="center">
        <template #default="{ row }">
          <el-popconfirm title="确定删除？" @confirm="handleDelete(row)">
            <template #reference>
              <el-button link type="danger" size="small">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && list.length === 0" description="暂无文件模板" :image-size="60" />

    <!-- 分页 -->
    <div v-if="total > pageSize" class="pager-wrap">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchList"
      />
    </div>

    <!-- 可用变量提示 -->
    <el-collapse style="margin-top:20px">
      <el-collapse-item title="可用变量参考（供管理员制作模板时使用）">
        <div class="var-tags">
          <el-tag v-for="v in variables" :key="v" size="small" type="info" style="font-family:monospace;margin:2px 4px">{{ v }}</el-tag>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
/** 系统管理员 —— 文件模板管理（跨组织） */
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import {
  getAdminDocTemplates, deleteAdminDocTemplate, adminUploadDocTemplate,
  getAdminOrganizations, type AdminDocTemplateItem,
} from '@/api/template'
import { formatFileSize } from '@/utils/format'

const loading = ref(false)
const list = ref<AdminDocTemplateItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(30)

const orgs = ref<{ id: number; name: string }[]>([])
const filterOrgId = ref<number | ''>('')
const filterKeyword = ref('')
const uploadOrgId = ref<number | ''>('')

const variables = [
  '{{项目名称}}', '{{项目描述}}', '{{合同号}}', '{{产品型号}}',
  '{{销售经理}}', '{{模板名称}}', '{{优先级}}', '{{当前节点}}',
  '{{发起人}}', '{{发起日期}}', '{{所属部门}}', '{{当前负责人}}',
  '{{当前日期}}',
]

async function fetchList() {
  loading.value = true
  try {
    const data = await getAdminDocTemplates({
      organization_id: filterOrgId.value || undefined,
      keyword: filterKeyword.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    list.value = data.items
    total.value = data.total
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

async function fetchOrgs() {
  try {
    orgs.value = await getAdminOrganizations()
  } catch {
    // ignore
  }
}

function handleFilter() {
  page.value = 1
  fetchList()
}

async function handleUpload(file: File) {
  if (!uploadOrgId.value) return false
  loading.value = true
  try {
    await adminUploadDocTemplate(file, uploadOrgId.value as number)
    ElMessage.success(`"${file.name}" 上传成功`)
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '上传失败')
  } finally {
    loading.value = false
  }
  return false  // 阻止 el-upload 默认行为
}

async function handleDelete(row: AdminDocTemplateItem) {
  try {
    await deleteAdminDocTemplate(row.id)
    ElMessage.success('已删除')
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '删除失败')
  }
}

// 文件大小格式化 —— 统一从 @/utils/format 导入

onMounted(() => {
  fetchOrgs()
  fetchList()
})
</script>

<style lang="scss" scoped>
.doc-tpl-admin {
  .filter-bar { display: flex; align-items: center; }
  .pager-wrap { display: flex; justify-content: center; margin-top: 16px; }
}
</style>
