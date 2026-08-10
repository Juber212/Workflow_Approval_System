<template>
  <!-- 发起模式文件模板弹窗 —— 本地临时态，不写回模板（P2-8）
       初始「已关联」= 模板快照（linked + linked_categories docs），「可关联」= 全组织可用
       发起人增删仅存本地数组，发起时作为 doc_template_ids 一次性提交，实例与模板解耦 -->
  <el-dialog
    v-model="visible"
    title="关联文件模板"
    width="680px"
    @open="handleOpen"
    destroy-on-close
  >
    <!-- 已关联项 —— 分类和模板合并为一个列表 -->
    <div v-if="linkedTotal > 0" class="doc-section">
      <h4 class="doc-section__title">已关联（{{ linkedTotal }}）</h4>
      <template v-for="item in linkedList" :key="item.key">
        <div class="doc-item" :class="{ 'doc-item--expanded': item.isCategory && expandedCats.has(item.catId) }">
          <span class="doc-item__info" @click="item.isCategory && toggleCatExpand(item.catId)" :style="item.isCategory ? 'cursor:pointer' : ''">
            <el-tag size="small" :type="item.tagType" effect="plain">{{ item.tagLabel }}</el-tag>
            <span class="doc-item__name">{{ item.name }}</span>
            <span class="doc-item__orig">{{ item.subtitle }}</span>
            <span v-if="item.isCategory" class="doc-item__expand-icon">{{ expandedCats.has(item.catId) ? '▾' : '▸' }}</span>
          </span>
          <el-button link type="danger" size="small" @click="item.isCategory ? removeCategory(item.raw as TemplateCategorySummary) : removeDoc(item.raw as DocTemplateItem)">移除</el-button>
        </div>
        <!-- 展开的包内模板 -->
        <div v-if="item.isCategory && expandedCats.has(item.catId)" class="doc-sub-list">
          <div v-for="sub in catDocs(item.raw)" :key="'sub-' + sub.id" class="doc-sub-item">
            <span class="doc-sub-item__info">
              <el-tag :type="sub.file_type === 'xlsx' ? 'success' : ''" size="small" effect="plain">.{{ sub.file_type }}</el-tag>
              <span>{{ sub.name }}</span>
            </span>
            <span class="doc-sub-item__size">{{ formatFileSize(sub.file_size) }}</span>
          </div>
          <div v-if="!catDocs(item.raw)?.length" class="doc-sub-empty">暂无模板</div>
        </div>
      </template>
    </div>

    <!-- 可关联项 —— 合并列表 -->
    <div v-if="availableList.length > 0" class="doc-section">
      <h4 class="doc-section__title">可关联（{{ availableList.length }}）</h4>
      <template v-for="item in availableList" :key="item.key">
        <div class="doc-item" :class="{ 'doc-item--expanded': item.isCategory && expandedCats.has(item.catId) }">
          <span class="doc-item__info" @click="item.isCategory && toggleCatExpand(item.catId)" :style="item.isCategory ? 'cursor:pointer' : ''">
            <el-tag size="small" :type="item.tagType" effect="plain">{{ item.tagLabel }}</el-tag>
            <span class="doc-item__name">{{ item.name }}</span>
            <span class="doc-item__orig">{{ item.subtitle }}</span>
            <span v-if="item.isCategory" class="doc-item__expand-icon">{{ expandedCats.has(item.catId) ? '▾' : '▸' }}</span>
          </span>
          <el-button link type="primary" size="small" @click="item.isCategory ? linkCategory(item.raw as TemplateCategorySummary) : linkDoc(item.raw as DocTemplateItem)">关联</el-button>
        </div>
        <!-- 展开的包内模板 -->
        <div v-if="item.isCategory && expandedCats.has(item.catId)" class="doc-sub-list">
          <div v-for="sub in catDocs(item.raw)" :key="'sub-' + sub.id" class="doc-sub-item">
            <span class="doc-sub-item__info">
              <el-tag :type="sub.file_type === 'xlsx' ? 'success' : ''" size="small" effect="plain">.{{ sub.file_type }}</el-tag>
              <span>{{ sub.name }}</span>
            </span>
            <span class="doc-sub-item__size">{{ formatFileSize(sub.file_size) }}</span>
          </div>
          <div v-if="!catDocs(item.raw)?.length" class="doc-sub-empty">暂无模板</div>
        </div>
      </template>
    </div>

    <el-empty v-if="linkedTotal === 0 && availableList.length === 0" description="暂无可用文件模板，请联系管理员上传" :image-size="60" />

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 发起模式文件模板弹窗 —— 本地临时选择，不写回模板（P2-8）
 *
 * 数据源与设计器编辑弹窗相同（GET /templates/{id}/documents），
 * 但「关联/移除」只改本地数组，emit('change', ids) 通知父组件，
 * 发起时父组件将 ids 作为 doc_template_ids 一次性提交。
 */
import { ref, computed, watch } from 'vue'
import { getDocTemplates, getCategoryDetail, type DocTemplateItem, type TemplateCategorySummary, type LinkedTemplateCategory } from '@/api/template'
import { formatFileSize } from '@/utils/format'

const props = defineProps<{
  modelValue: boolean
  /** 流程模板 ID（发起模式） */
  templateId: number
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  /** 本地选择变更：已关联模板 ID 合集（含分类包内模板） */
  change: [ids: number[]]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

// ─── 本地状态（仅本次弹窗会话有效）───
const linkedDocTemplates = ref<DocTemplateItem[]>([])
/** 已关联分类（自带 documents，后端 GET /templates/{id}/documents 必带） */
const linkedCategories = ref<LinkedTemplateCategory[]>([])
const availableDocTemplates = ref<DocTemplateItem[]>([])
/** 可关联分类（无 documents，需补拉详情才能展示包内模板） */
const availableCategories = ref<TemplateCategorySummary[]>([])
/** 可关联分类的包内模板明细缓存：categoryId → 模板列表 */
const catDocsMap = ref<Record<number, DocTemplateItem[]>>({})
/** 弹窗中展开的包 ID 集合 */
const expandedCats = ref<Set<number>>(new Set())

/** 弹窗打开时加载模板快照（已关联 = 模板快照；可关联 = 全组织可用） */
async function handleOpen() {
  if (!props.templateId) return
  try {
    const data = await getDocTemplates(props.templateId)
    linkedDocTemplates.value = data.linked
    linkedCategories.value = data.linked_categories
    availableDocTemplates.value = data.available
    availableCategories.value = data.available_categories

    // 补拉可关联分类的包内模板明细（展示展开内容用；已关联分类自带 documents 无需补拉）
    const catDocs: Record<number, DocTemplateItem[]> = {}
    if (availableCategories.value.length > 0) {
      const results = await Promise.allSettled(
        availableCategories.value.map(c => getCategoryDetail(c.id)),
      )
      results.forEach((r, i) => {
        if (r.status === 'fulfilled' && availableCategories.value[i]) {
          catDocs[availableCategories.value[i].id] = r.value.documents || []
        }
      })
    }
    catDocsMap.value = catDocs

    // 初始已关联 ID = linked 单模板 + 已关联分类包内模板（模板快照）
    emit('change', collectSelectedIds())
  } catch {
    // 拦截器已统一弹错（P1-35），无需重复提示
  }
}

/** 分类包内模板明细（已关联分类用自带 documents，可关联分类用补拉缓存） */
function catDocs(cat: { id: number }): DocTemplateItem[] {
  const linked = linkedCategories.value.find(c => c.id === cat.id)
  if (linked) return linked.documents || []
  return catDocsMap.value[cat.id] || []
}

/** 计算当前已关联的模板 ID 合集（linked 单模板 + 已关联分类包内全部） */
function collectSelectedIds(): number[] {
  const ids = new Set<number>()
  linkedDocTemplates.value.forEach(d => ids.add(d.id))
  linkedCategories.value.forEach(c => (c.documents || []).forEach(d => ids.add(d.id)))
  return Array.from(ids)
}

/** 关联单个模板 → 加入已关联列表 */
function linkDoc(doc: DocTemplateItem) {
  if (linkedDocTemplates.value.some(d => d.id === doc.id)) return
  linkedDocTemplates.value = [...linkedDocTemplates.value, doc]
  emit('change', collectSelectedIds())
}

/** 关联分类 → 移入已关联，并把包内模板一并加入已关联（视为整体关联） */
function linkCategory(cat: TemplateCategorySummary) {
  if (linkedCategories.value.some(c => c.id === cat.id)) return
  // 可关联分类无 documents，用补拉的缓存构造 LinkedTemplateCategory
  const docs = catDocsMap.value[cat.id] || []
  const linked: LinkedTemplateCategory = { ...cat, documents: docs }
  linkedCategories.value = [...linkedCategories.value, linked]
  // 从可关联中移除
  availableCategories.value = availableCategories.value.filter(c => c.id !== cat.id)
  // 包内模板从可关联单个模板中移除（避免重复出现在已关联）
  const catDocIds = new Set(docs.map(d => d.id))
  availableDocTemplates.value = availableDocTemplates.value.filter(d => !catDocIds.has(d.id))
  emit('change', collectSelectedIds())
}

/** 移除单个模板 */
function removeDoc(doc: DocTemplateItem) {
  linkedDocTemplates.value = linkedDocTemplates.value.filter(d => d.id !== doc.id)
  // 放回可关联列表（若该模板不属于任何已关联分类包）
  const inCat = linkedCategories.value.some(c => (c.documents || []).some(d => d.id === doc.id))
  if (!inCat) {
    availableDocTemplates.value = [...availableDocTemplates.value, doc]
  }
  emit('change', collectSelectedIds())
}

/** 移除分类 → 包内模板一并移除（整体移除），分类放回可关联 */
function removeCategory(cat: TemplateCategorySummary) {
  linkedCategories.value = linkedCategories.value.filter(c => c.id !== cat.id)
  // 放回可关联分类（保留补拉缓存的文档明细）
  availableCategories.value = [...availableCategories.value, cat]
  // 包内模板只随包走（包已放回可关联分类），不单独放回「可关联单个模板」列表——
  // 修复：取消包关联后包内模板不应单独冒出来；若某模板此前被单独关联（linkedDocTemplates），
  // 移除分类后仍保留其单独关联（collectSelectedIds 会算入）
  emit('change', collectSelectedIds())
}

/** 切换包展开/折叠 */
function toggleCatExpand(catId: number) {
  const next = new Set(expandedCats.value)
  if (next.has(catId)) next.delete(catId)
  else next.add(catId)
  expandedCats.value = next
}

// ─── 合并列表（分类 + 模板，统一渲染）───

interface DocListItem {
  key: string
  name: string
  subtitle: string
  tagLabel: string
  tagType: '' | 'success' | 'warning' | 'info' | 'danger'
  isCategory: boolean
  catId: number  // 分类 ID，单个模板为 0
  raw: DocTemplateItem | TemplateCategorySummary
}

function _makeItems(
  cats: TemplateCategorySummary[],
  docs: DocTemplateItem[],
  keyPrefix: string,
): DocListItem[] {
  return [
    ...cats.map(c => ({
      key: `${keyPrefix}-cat-${c.id}`, name: c.name,
      subtitle: `${c.document_count} 个模板`,
      tagLabel: '📦 包', tagType: 'warning' as const,
      isCategory: true, catId: c.id, raw: c,
    })),
    ...docs.map(d => ({
      key: `${keyPrefix}-doc-${d.id}`, name: d.name,
      subtitle: d.original_name,
      tagLabel: `.${d.file_type}`, tagType: (d.file_type === 'xlsx' ? 'success' : '') as DocListItem['tagType'],
      isCategory: false, catId: 0, raw: d,
    })),
  ]
}

/** 已关联总数 */
const linkedTotal = computed(() => linkedDocTemplates.value.length + linkedCategories.value.length)

/** 已关联——合并为一个列表，分类在前 */
const linkedList = computed<DocListItem[]>(() => _makeItems(linkedCategories.value, linkedDocTemplates.value, 'linked'))

/** 可关联——合并列表 */
const availableList = computed<DocListItem[]>(() => _makeItems(availableCategories.value, availableDocTemplates.value, 'avail'))

// 关闭后清空本地状态（下次打开重新加载快照）
watch(visible, (val) => {
  if (!val) {
    linkedDocTemplates.value = []
    linkedCategories.value = []
    availableDocTemplates.value = []
    availableCategories.value = []
    catDocsMap.value = {}
    expandedCats.value = new Set()
  }
})
</script>

<style lang="scss" scoped>
/* ─── 文件模板弹窗（与设计器编辑弹窗同风格）─── */
.doc-section {
  margin-bottom: 16px;
  &__title { font-size: 13px; font-weight: 600; margin: 0 0 8px; color: var(--el-text-color-primary); }
}
.doc-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px;
  margin-bottom: 6px; transition: background .15s;
  &:hover { background: var(--el-fill-color-light); }
  &--expanded { border-color: var(--el-color-primary-light-5); border-radius: 6px 6px 0 0; margin-bottom: 0; }
  &__info { display: flex; align-items: center; gap: 8px; min-width: 0; }
  &__name { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  &__orig { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  &__expand-icon { font-size: 11px; color: var(--el-text-color-secondary); margin-left: auto; }
}

/* 包内子模板列表 */
.doc-sub-list {
  border: 1px solid var(--el-color-primary-light-5); border-top: none;
  border-radius: 0 0 6px 6px;
  margin-top: -1px; margin-bottom: 6px;
  background: var(--el-color-primary-light-9);
}
.doc-sub-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 12px 5px 28px;
  &:not(:last-child) { border-bottom: 1px solid var(--el-color-primary-light-7); }
  &__info { display: flex; align-items: center; gap: 6px; font-size: 12px; }
  &__size { font-size: 11px; color: var(--el-text-color-placeholder); }
}
.doc-sub-empty {
  padding: 8px 28px; font-size: 12px; color: var(--el-text-color-placeholder);
}
</style>
