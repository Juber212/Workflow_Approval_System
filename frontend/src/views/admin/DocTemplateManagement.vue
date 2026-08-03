<template>
  <div class="doc-tpl-admin">
    <!-- 上传区域 -->
    <div class="upload-bar">
      <el-select v-model="uploadOrgId" placeholder="选择组织" style="width:200px">
        <el-option v-for="org in orgs" :key="org.id" :label="org.name" :value="org.id" />
      </el-select>
      <el-upload
        :show-file-list="false" :before-upload="handleUpload"
        accept=".doc,.docx,.xlsx" :disabled="!uploadOrgId"
        style="margin-left:12px;display:inline-block"
      >
        <el-button type="primary" :disabled="!uploadOrgId">上传文件模板</el-button>
      </el-upload>
      <span style="font-size:12px;color:var(--el-text-color-secondary);margin-left:8px">支持 .doc / .docx / .xlsx，≤10MB</span>

      <el-input v-model="filterKeyword" placeholder="搜索模板名称" clearable style="width:220px;margin-left:20px">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <!-- ====== 按组织分组 ====== -->
    <div v-loading="loading">
      <div v-for="org in orgCards" :key="org.id" class="org-block">
        <!-- 组织头部 -->
        <div class="org-block__header">
          <h3 class="org-block__name">{{ org.name }}</h3>
          <span class="org-block__count">{{ org.packs.length }} 个包 · {{ org.uncategorized.length }} 个未归包</span>
          <el-button type="primary" size="small" style="margin-left:auto" @click="openPackDialog(org.id)">+ 新建包</el-button>
        </div>

        <div class="org-block__body">
          <!-- 包卡片 -->
          <div v-for="pack in org.packs" :key="pack.id" class="pack-card">
            <div class="pack-card__header" @click="pack.expanded = !pack.expanded">
              <div class="pack-card__info">
                <span class="pack-card__icon">📦</span>
                <span class="pack-card__name">{{ pack.name }}</span>
                <el-tag size="small" effect="plain" round>{{ pack.documents.length }} 个模板</el-tag>
                <span v-if="pack.description" class="pack-card__desc">{{ pack.description }}</span>
              </div>
              <div class="pack-card__actions" @click.stop>
                <el-button link type="primary" size="small" @click="openPackDialog(org.id, pack)">编辑</el-button>
                <el-popconfirm title="确定删除此包？（不删除模板文件）" @confirm="handlePackDelete(pack)">
                  <template #reference>
                    <el-button link type="danger" size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </div>
            </div>

            <!-- 展开：包内模板 -->
            <div v-if="pack.expanded" class="pack-card__body">
              <div v-if="pack.documents.length === 0" class="pack-card__empty">此包还没有模板</div>
              <div v-for="doc in pack.documents" :key="doc.id" class="pack-doc-row">
                <span class="pack-doc-row__info">
                  <el-tag :type="doc.file_type === 'xlsx' ? 'success' : ''" size="small" effect="plain">.{{ doc.file_type }}</el-tag>
                  <span class="pack-doc-row__name">{{ doc.name }}</span>
                  <span class="pack-doc-row__meta">{{ doc.original_name }} · {{ formatFileSize(doc.file_size) }}</span>
                </span>
                <el-button link type="danger" size="small" @click.stop="handleRemoveFromPack(pack, doc)">移除</el-button>
              </div>

              <div class="pack-add-row">
                <el-select
                  v-model="pack._addIds"
                  multiple filterable collapse-tags collapse-tags-tooltip
                  placeholder="选择模板加入此包"
                  style="flex:1" size="small"
                >
                  <el-option
                    v-for="tpl in availableForPack(pack)"
                    :key="tpl.id"
                    :label="tpl.name"
                    :value="tpl.id"
                  >
                    <span>{{ tpl.name }}</span>
                    <span style="color:var(--el-text-color-placeholder);font-size:12px;margin-left:8px">{{ tpl.original_name }}</span>
                  </el-option>
                </el-select>
                <el-button size="small" type="primary" text :disabled="!pack._addIds?.length" @click="handleAddToPack(pack)">加入</el-button>
              </div>
            </div>
          </div>

          <!-- 未归包模板 -->
          <div v-if="org.uncategorized.length > 0" class="uncategorized">
            <h4 class="uncategorized__title">未归包模板（{{ org.uncategorized.length }}）</h4>
            <div class="uncategorized__list">
              <div v-for="doc in org.uncategorized" :key="doc.id" class="uncat-doc">
                <span class="uncat-doc__info">
                  <el-tag :type="doc.file_type === 'xlsx' ? 'success' : ''" size="small" effect="plain">.{{ doc.file_type }}</el-tag>
                  <span class="uncat-doc__name">{{ doc.name }}</span>
                  <span class="uncat-doc__meta">{{ doc.original_name }} · {{ formatFileSize(doc.file_size) }}</span>
                </span>
                <el-select
                  v-model="quickAddMap[doc.id]"
                  placeholder="加入包"
                  size="small"
                  style="width:140px"
                  clearable
                  @change="(val: number | '') => { if (val) handleQuickAdd(doc, val) }"
                >
                  <el-option v-for="p in org.packs" :key="p.id" :label="p.name" :value="p.id" />
                </el-select>
                <el-popconfirm title="确定删除此模板？" @confirm="handleDeleteDoc(doc)">
                  <template #reference>
                    <el-button link type="danger" size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </div>
            </div>
          </div>

          <!-- 组织无数据 -->
          <div v-if="org.packs.length === 0 && org.uncategorized.length === 0" class="org-block__empty">
            暂无文件模板
          </div>
        </div>
      </div>
    </div>

    <!-- 可用变量 -->
    <el-card shadow="never" style="margin-top:20px">
      <template #header><span>可用变量参考（供管理员制作模板时使用）</span></template>
      <div class="var-tags">
        <el-tag v-for="v in variables" :key="v" size="small" type="info" style="font-family:monospace;margin:2px 4px">{{ v }}</el-tag>
      </div>
    </el-card>

    <!-- ====== 包编辑弹窗 ====== -->
    <el-dialog v-model="packDialogVisible" :title="editingPack ? '编辑包' : '新建包'" width="460px" @closed="packFormRef?.resetFields()">
      <el-form :model="packForm" ref="packFormRef" label-width="80px">
        <el-form-item label="所属组织" required>
          <el-select v-model="packForm.organization_id" placeholder="选择组织" style="width:100%" :disabled="!!editingPack">
            <el-option v-for="org in orgs" :key="org.id" :label="org.name" :value="org.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="包名" required>
          <el-input v-model="packForm.name" placeholder="如：合同相关" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="packForm.description" placeholder="可选" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="packDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handlePackSave" :disabled="!packForm.name || !packForm.organization_id">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/** 系统管理员 —— 文件模板 + 包管理（按组织分组） */
import { ref, onMounted, computed, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import {
  getAdminDocTemplates, deleteAdminDocTemplate, adminUploadDocTemplate,
  getAdminOrganizations, type AdminDocTemplateItem,
  getAdminCategories, createAdminCategory, updateAdminCategory, deleteAdminCategory,
  getAdminCategoryDetail, linkDocsToCategory, unlinkDocsFromCategory,
} from '@/api/template'
import { formatFileSize } from '@/utils/format'

// ─── 类型 ───
interface PackItem {
  id: number; name: string; description: string | null
  organization_id: number
  documents: AdminDocTemplateItem[]
  expanded: boolean
  _addIds: number[]
}

interface OrgCard {
  id: number; name: string
  packs: PackItem[]
  uncategorized: AdminDocTemplateItem[]
}

// ─── 状态 ───
const loading = ref(false)
const orgs = ref<{ id: number; name: string }[]>([])
const uploadOrgId = ref<number | ''>('')
const filterKeyword = ref('')

const allDocs = ref<AdminDocTemplateItem[]>([])
const allPacks = ref<PackItem[]>([])
const quickAddMap = reactive<Record<number, number | ''>>({})

// ─── 按组织分组的卡片列表 ───
const orgCards = computed<OrgCard[]>(() => {
  const kw = filterKeyword.value.toLowerCase()

  const inAnyPackIds = new Set<number>()
  for (const p of allPacks.value) {
    for (const d of p.documents) {
      inAnyPackIds.add(d.id)
    }
  }

  return orgs.value.map(org => {
    // 该组织的包
    const packs = allPacks.value.filter(p => p.organization_id === org.id)
    // 按关键词过滤
    const filteredPacks = kw
      ? packs.filter(p => {
          if (p.name.toLowerCase().includes(kw)) return true
          return p.documents.some(d => d.name.toLowerCase().includes(kw) || d.original_name.toLowerCase().includes(kw))
        })
      : packs

    // 该组织未归包模板
    const uncategorized = allDocs.value.filter(d => {
      if (d.organization_id !== org.id) return false
      if (inAnyPackIds.has(d.id)) return false
      if (kw && !d.name.toLowerCase().includes(kw) && !d.original_name.toLowerCase().includes(kw)) return false
      return true
    })

    return { id: org.id, name: org.name, packs: filteredPacks, uncategorized }
  })
})

// ─── 数据加载 ───
async function fetchAll(showLoading = true) {
  if (showLoading) loading.value = true
  try {
    const [tplRes, catRes] = await Promise.all([
      getAdminDocTemplates({ page_size: 200 }),
      getAdminCategories({ page_size: 200 }),
    ])

    // 补齐超过 200 的模板
    let docs = tplRes.items
    if (tplRes.total > docs.length) {
      const extraPages = Math.ceil((tplRes.total - docs.length) / 200)
      for (let p = 2; p <= extraPages + 1; p++) {
        const extra = await getAdminDocTemplates({ page: p, page_size: 200 })
        docs = docs.concat(extra.items)
      }
    }
    allDocs.value = docs

    // 为每个包加载内部文档
    const packs: PackItem[] = []
    for (const cat of catRes.items || []) {
      let documents: AdminDocTemplateItem[] = []
      try {
        const detail = await getAdminCategoryDetail(cat.id)
        const docIdSet = new Set(detail.documents.map((d: any) => d.id))
        documents = docs.filter(d => docIdSet.has(d.id))
      } catch { /* ignore */ }

      packs.push({
        id: cat.id, name: cat.name, description: cat.description,
        organization_id: cat.organization_id,
        documents, expanded: true, _addIds: [],
      })
    }
    allPacks.value = packs
  } catch { /* ignore */ } finally {
    if (showLoading) loading.value = false
  }
}

async function fetchOrgs() {
  try { orgs.value = await getAdminOrganizations() } catch { /* ignore */ }
}

/** 某包下可添加的模板：同组织 + 不在本包内 */
function availableForPack(pack: PackItem): AdminDocTemplateItem[] {
  const inPackIds = new Set(pack.documents.map(d => d.id))
  return allDocs.value.filter(d => d.organization_id === pack.organization_id && !inPackIds.has(d.id))
}

// ─── 上传 ───
async function handleUpload(file: File) {
  if (!uploadOrgId.value) return false
  loading.value = true
  try {
    await adminUploadDocTemplate(file, uploadOrgId.value as number)
    ElMessage.success(`"${file.name}" 上传成功`)
    fetchAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '上传失败')
  } finally { loading.value = false }
  return false
}

// ─── 删除模板 ───
async function handleDeleteDoc(doc: AdminDocTemplateItem) {
  try {
    await deleteAdminDocTemplate(doc.id)
    ElMessage.success('已删除')
    fetchAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '删除失败')
  }
}

// ─── 包 CRUD ───
const packDialogVisible = ref(false)
const editingPack = ref<PackItem | null>(null)
const packForm = ref({ organization_id: 0, name: '', description: '' })
const packFormRef = ref<any>(null)

function openPackDialog(orgId: number, pack?: PackItem) {
  editingPack.value = pack || null
  if (pack) {
    packForm.value = { organization_id: pack.organization_id, name: pack.name, description: pack.description || '' }
  } else {
    packForm.value = { organization_id: orgId, name: '', description: '' }
  }
  packDialogVisible.value = true
}

async function handlePackSave() {
  try {
    if (editingPack.value) {
      await updateAdminCategory(editingPack.value.id, {
        name: packForm.value.name,
        description: packForm.value.description || null,
      })
      ElMessage.success('包已更新')
    } else {
      await createAdminCategory({
        organization_id: packForm.value.organization_id,
        name: packForm.value.name,
        description: packForm.value.description || null,
      })
      ElMessage.success('包创建成功')
    }
    packDialogVisible.value = false
    fetchAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '保存失败')
  }
}

async function handlePackDelete(pack: PackItem) {
  try {
    await deleteAdminCategory(pack.id)
    ElMessage.success('包已删除')
    fetchAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '删除失败')
  }
}

// ─── 包内模板操作 ───
async function handleRemoveFromPack(pack: PackItem, doc: AdminDocTemplateItem) {
  try {
    await unlinkDocsFromCategory(pack.id, [doc.id])
    ElMessage.success(`已从「${pack.name}」移除`)
    fetchAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '移除失败')
  }
}

async function handleAddToPack(pack: PackItem) {
  if (!pack._addIds?.length) return
  try {
    await linkDocsToCategory(pack.id, pack._addIds)
    ElMessage.success(`已加入 ${pack._addIds.length} 个模板`)
    pack._addIds = []
    fetchAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '加入失败')
  }
}

async function handleQuickAdd(doc: AdminDocTemplateItem, packId: number) {
  try {
    await linkDocsToCategory(packId, [doc.id])
    ElMessage.success('已加入')
    quickAddMap[doc.id] = ''
    fetchAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '加入失败')
  }
}

const variables = [
  '{{项目名称}}', '{{项目描述}}', '{{合同号}}', '{{产品型号}}',
  '{{销售经理}}', '{{模板名称}}', '{{优先级}}', '{{当前节点}}',
  '{{发起人}}', '{{发起日期}}', '{{所属部门}}', '{{当前负责人}}',
  '{{当前日期}}', '{{难度}}', '{{截止日期}}',
]

onMounted(() => {
  fetchOrgs()
  fetchAll()
})
</script>

<style lang="scss" scoped>
.doc-tpl-admin {
  .upload-bar { display: flex; align-items: center; }
}

/* ─── 组织分组卡片 ─── */
.org-block {
  margin-top: 20px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
  &__header {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 20px;
    background: #fafbfc;
    border-bottom: 1px solid var(--el-border-color-light);
    border-radius: 8px 8px 0 0;
  }
  &__name { font-size: 15px; font-weight: 600; margin: 0; }
  &__count { font-size: 12px; color: var(--el-text-color-secondary); }
  &__body { padding: 12px 20px 20px; }
  &__empty {
    text-align: center; padding: 36px 0;
    color: var(--el-text-color-placeholder); font-size: 13px;
  }
}

/* ─── 包卡片 ─── */
.pack-card {
  margin-top: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
  background: #fafbfc;
  &__header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px;
    cursor: pointer; user-select: none;
    &:hover { background: #eff1f4; }
  }
  &__info { display: flex; align-items: center; gap: 8px; }
  &__icon { font-size: 16px; }
  &__name { font-weight: 600; font-size: 13px; }
  &__desc { font-size: 12px; color: var(--el-text-color-placeholder); }
  &__actions { display: flex; align-items: center; gap: 4px; }
  &__body {
    padding: 4px 14px 10px;
    border-top: 1px solid #e5e7eb;
    background: #fff;
  }
  &__empty {
    text-align: center; padding: 16px 0;
    color: var(--el-text-color-placeholder); font-size: 13px;
  }
}

/* 包内模板行 */
.pack-doc-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 0;
  &:not(:last-child) { border-bottom: 1px solid #f2f3f5; }
  &__info { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
  &__name { font-size: 13px; font-weight: 500; }
  &__meta { font-size: 12px; color: var(--el-text-color-placeholder); white-space: nowrap; }
}

.pack-add-row {
  display: flex; align-items: center; gap: 8px;
  margin-top: 8px; padding-top: 8px;
  border-top: 1px dashed #d9dde3;
}

/* ─── 未归包模板 ─── */
.uncategorized {
  margin-top: 16px;
  &__title {
    font-size: 13px; font-weight: 600; margin-bottom: 6px;
  }
  &__list {
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    overflow: hidden;
  }
}

.uncat-doc {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 8px 12px;
  background: #fafbfc;
  &:not(:last-child) { border-bottom: 1px solid #e5e7eb; }
  &__info { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
  &__name { font-size: 13px; font-weight: 500; }
  &__meta { font-size: 12px; color: var(--el-text-color-placeholder); white-space: nowrap; }
}

.var-tags { display: flex; flex-wrap: wrap; }
</style>
