<template>
  <!-- 签批预览弹框 —— 增强版：文档多选 + 多次签名 + 拖拽定位 -->
  <el-dialog
    v-model="dialogVisible"
    title="签批确认"
    width="90vw"
    top="3vh"
    :close-on-click-modal="false"
    @closed="handleClose"
  >
    <div class="sig-preview">
      <div class="sig-layout">
        <!-- 左侧：文档列表 + 签名槽位 -->
        <div class="sig-sidebar">
          <div class="sig-sidebar__title">选择文档</div>

          <!-- 无文件提示 -->
          <div v-if="files.length === 0 && !initializing" class="sig-sidebar__empty">
            <p>暂无可签批的 PDF 文件</p>
            <p class="sig-sidebar__empty-hint">请确认已上传文件并转换为 PDF 格式</p>
          </div>

          <div class="sig-file-list">
            <div
              v-for="f in files"
              :key="f.file_id"
              class="sig-file-item"
              :class="{ 'sig-file-item--active': activeFileId === f.file_id, 'sig-file-item--unchecked': !f.checked }"
            >
              <!-- 文档行：复选框 + 名称 -->
              <div class="sig-file-row" @click="selectFile(f.file_id)">
                <el-checkbox
                  v-model="f.checked"
                  @change="onFileCheckChange(f)"
                />
                <span class="sig-file-name" :title="f.name">{{ f.name }}</span>
              </div>
              <!-- 该文档的签名槽位（仅选中时显示） -->
              <template v-if="f.checked">
                <div
                  v-for="(slot, si) in f.slots"
                  :key="si"
                  class="sig-slot-row"
                  :class="{ 'sig-slot-row--active': activeFileId === f.file_id && activeSlotIdx === si }"
                  @click.stop="selectSlot(f.file_id, si)"
                >
                  <span class="sig-slot-icon">✍</span>
                  <span class="sig-slot-label">
                    签名 {{ si + 1 }} · 第{{ slot.signature_page < 0 ? '末' : slot.signature_page }}页
                  </span>
                  <el-button
                    v-if="f.slots.length > 1"
                    text
                    size="small"
                    type="danger"
                    @click.stop="removeSlot(f, si)"
                  >
                    ✕
                  </el-button>
                </div>
                <el-button text size="small" type="primary" class="sig-add-slot" @click.stop="addSlot(f)">
                  + 加一处签名
                </el-button>
              </template>
            </div>
          </div>
          <!-- 全选/取消 -->
          <div class="sig-sidebar__actions">
            <el-button text size="small" @click="toggleAll(true)">全选</el-button>
            <el-button text size="small" @click="toggleAll(false)">取消全选</el-button>
          </div>
        </div>

        <!-- 右侧：PDF 预览 -->
        <div class="sig-main">
          <!-- 页面导航 + 缩放（始终渲染，canvas 始终在 DOM 中确保 renderPage 可访问） -->
          <div class="sig-toolbar">
            <el-button-group>
              <el-button :disabled="currentPage <= 1" @click="goPage(currentPage - 1)">◀</el-button>
              <span class="page-indicator">{{ currentPage }} / {{ totalPages || '—' }}</span>
              <el-button :disabled="currentPage >= totalPages" @click="goPage(currentPage + 1)">▶</el-button>
            </el-button-group>
            <!-- 缩放控制 -->
            <el-button-group class="sig-zoom-group">
              <el-button :disabled="zoomLevel <= 0.5" @click="zoomOut">−</el-button>
              <span class="zoom-indicator">{{ Math.round(zoomLevel * 100) }}%</span>
              <el-button :disabled="zoomLevel >= 3.0" @click="zoomIn">+</el-button>
            </el-button-group>
            <span class="sig-hint">拖拽缩放签名</span>
          </div>

          <!-- PDF 渲染区（始终渲染，loading/空状态用叠加层展示） -->
          <div
            ref="wrapperRef"
            class="sig-canvas-wrapper"
            @mousemove="onWrapperMouseMove"
            @mouseup="onWrapperMouseUp"
            @mouseleave="onWrapperMouseUp"
          >
            <!-- 加载中 / 未选择文件 覆盖层 -->
            <div v-if="!activeFileId || loadingPdf" class="sig-canvas-overlay">
              <template v-if="loadingPdf">加载中...</template>
              <template v-else-if="files.length === 0">暂无 PDF 文件</template>
              <template v-else>请在左侧选择文档预览</template>
            </div>

            <!-- canvas 和 overlay 共享同一个定位容器，确保坐标原点一致 -->
            <div class="sig-canvas-stage" :style="{ position: 'relative', display: 'inline-block', lineHeight: 0 }">
              <canvas ref="canvasRef" style="display:block;" />
              <!-- 签名拖拽叠加层（支持移动 + 四角缩放） -->
              <div
                v-if="sigBlobUrl && activeFileId && !loadingPdf"
                class="sig-overlay"
                :style="overlayStyle"
                @mousedown.stop="startDrag"
              >
                <img :src="sigBlobUrl" class="sig-image" draggable="false" />
                <span class="sig-label">签名</span>
                <!-- 缩放拖拽手柄（四角） -->
                <span class="sig-resize-handle sig-resize--nw" @mousedown.stop="startResize('nw', $event)" />
                <span class="sig-resize-handle sig-resize--ne" @mousedown.stop="startResize('ne', $event)" />
                <span class="sig-resize-handle sig-resize--sw" @mousedown.stop="startResize('sw', $event)" />
                <span class="sig-resize-handle sig-resize--se" @mousedown.stop="startResize('se', $event)" />
              </div>
            </div>
          </div>

          <!-- 坐标信息 -->
          <div class="sig-coords">
            <span v-if="activeSlotLabel">{{ activeSlotLabel }} · </span>
            位置：X={{ Math.round(currentSigX) }} Y={{ Math.round(currentSigY) }} · 页码：{{ currentPage }}
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <span v-if="checkedCount === 0 && files.length > 0" class="sig-error">请至少选择一个文档</span>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :loading="loading" :disabled="checkedCount === 0">
        确认签批（{{ checkedCount }}个文档 · {{ totalSlots }}处签名）
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 签批预览弹框 —— 增强版：文档多选 + 多次签名 + 拖拽定位

核心改进：
- 使用 watch 监听 dialogVisible 替代 @opened（解决 Element Plus @opened 偶发不触发问题）
- 弹窗宽度 90vw，适配双栏布局
- PDF 加载失败时输出 console.warn 便于调试
*/
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import axios from 'axios'
import * as pdfjsLib from 'pdfjs-dist'
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import type { SignatureSlot } from '@/api/signature'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker

// ========== 内部类型 ==========

/** PDF 文件信息（外部传入） */
interface PdfFileInfo {
  file_id: number
  name: string
  url: string
}

/** 内部文件状态（含复选框和签名槽位） */
interface FileState {
  file_id: number
  name: string
  url: string
  checked: boolean
  slots: SignatureSlot[]  // 每个文件至少一个默认槽位
}

// ========== Props ==========

const props = defineProps<{
  modelValue: boolean
  /** 新版：PDF 文件列表（含 file_id + name + url） */
  pdfFiles?: PdfFileInfo[]
  /** 兼容旧版：纯 URL 数组（此时回退为单文件模式） */
  pdfUrls?: string[]
  authToken?: string
  sigUrl?: string | null
  defaultX: number
  defaultY: number
  defaultPage: number
  /** 签名默认宽度（对应 PDF 配置 pdf_signature_max_width，默认 100） */
  defaultWidth?: number
  /** 签名默认高度（对应 PDF 配置 pdf_signature_max_height，默认 26） */
  defaultHeight?: number
}>()

// ========== Emits ==========

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  /** 新版 confirm：返回所有选中文档的所有签名槽位 */
  'confirm': [slots: SignatureSlot[]]
}>()

// ========== 状态 ==========

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const loading = ref(false)
const loadingPdf = ref(false)  // PDF 加载中的独立状态，不影响文档列表显示
const initializing = ref(false)  // 初始化中，避免闪烁"暂无文件"提示
const wrapperRef = ref<HTMLDivElement>()
const canvasRef = ref<HTMLCanvasElement>()
const totalPages = ref(0)
const currentPage = ref(1)

// PDF 预览缩放（50% ~ 300%，步进 25%）
const zoomLevel = ref(1.0)
function zoomIn() { zoomLevel.value = Math.min(3.0, +(zoomLevel.value + 0.25).toFixed(2)) }
function zoomOut() { zoomLevel.value = Math.max(0.5, +(zoomLevel.value - 0.25).toFixed(2)) }
// 缩放变化时重新渲染当前页
watch(zoomLevel, () => { if (pdfDoc) renderPage(currentPage.value) })

// 当前编辑的签名位置（绑到当前激活的槽位）
const currentSigX = ref(props.defaultX)
const currentSigY = ref(props.defaultY)
// 当前编辑的签名尺寸
const currentSigW = ref(props.defaultWidth ?? 100)
const currentSigH = ref(props.defaultHeight ?? 26)

// 拖拽状态（移动）
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const sigStart = ref({ x: 0, y: 0 })

// 拖拽状态（缩放）
const resizing = ref(false)
const resizeDir = ref<'se' | 'sw' | 'ne' | 'nw'>('se')
const resizeStart = ref({ x: 0, y: 0, w: 0, h: 0 })

// 文件列表状态
const files = ref<FileState[]>([])
const activeFileId = ref<number>(0)
const activeSlotIdx = ref(0)

let pdfDoc: pdfjsLib.PDFDocumentProxy | null = null

// ========== 签名图片 Blob URL（解决 <img> 标签不带 Bearer Token 的问题）==========

const sigBlobUrl = ref<string | null>(null)

/** 释放之前的 blob URL 避免内存泄漏 */
function revokeSigBlob() {
  if (sigBlobUrl.value) {
    URL.revokeObjectURL(sigBlobUrl.value)
    sigBlobUrl.value = null
  }
}

/** 用 Axios + Bearer Token 加载签名图片并转换为 blob URL（不用 fetch，避免代理拦截问题） */
async function loadSigBlob(url: string | null | undefined) {
  revokeSigBlob()
  if (!url) {
    console.log('[SignaturePreview] sigUrl 为空，跳过加载')
    return
  }
  try {
    const token = localStorage.getItem('token')
    console.log('[SignaturePreview] 加载签名图:', url, 'token:', token ? '已获取' : '无')
    const res = await axios.get(url, {
      responseType: 'blob',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      // 不设置 baseURL，url 已是完整路径
    })
    sigBlobUrl.value = URL.createObjectURL(res.data)
    console.log('[SignaturePreview] 签名图加载成功, blob:', sigBlobUrl.value)
  } catch (e: any) {
    console.warn('[SignaturePreview] 签名图片加载失败:', url, e?.message || e)
    sigBlobUrl.value = null
  }
}

// 监听 sigUrl 变化，自动加载
watch(() => props.sigUrl, loadSigBlob, { immediate: true })

// 组件卸载时释放 blob URL
onBeforeUnmount(revokeSigBlob)

// ========== 计算属性 ==========

/** 签名覆盖层样式：PDF 坐标 × 缩放倍率 = 显示坐标（随 PDF 缩放等比变化） */
const overlayStyle = computed(() => ({
  left: `${currentSigX.value * zoomLevel.value}px`,
  top: `${currentSigY.value * zoomLevel.value}px`,
  width: `${currentSigW.value * zoomLevel.value}px`,
  height: `${currentSigH.value * zoomLevel.value}px`,
}))

const checkedCount = computed(() => files.value.filter(f => f.checked).length)

const totalSlots = computed(() =>
  files.value.filter(f => f.checked).reduce((sum, f) => sum + f.slots.length, 0)
)

const activeSlotLabel = computed(() => {
  const f = files.value.find(x => x.file_id === activeFileId.value)
  if (!f) return ''
  const idx = activeSlotIdx.value
  return `${f.name} · 签名${idx + 1}`
})

// ========== 监听弹窗打开（替代 @opened，更可靠）==========

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    initializing.value = true
    await nextTick()
    initFiles()
    currentSigX.value = props.defaultX
    currentSigY.value = props.defaultY
    currentPage.value = props.defaultPage < 0 ? 1 : props.defaultPage
    // 短暂延迟确保 DOM 就绪后加载第一个文件
    setTimeout(() => {
      initializing.value = false
      if (files.value.length > 0) {
        selectFile(files.value[0].file_id)
      }
    }, 150)
  },
)

// ========== 初始化 ==========

function initFiles() {
  const list: FileState[] = []

  // 优先使用 pdfFiles 新版参数
  if (props.pdfFiles && props.pdfFiles.length > 0) {
    for (const pf of props.pdfFiles) {
      list.push({
        file_id: pf.file_id,
        name: pf.name,
        url: pf.url,
        checked: true,  // 默认全选
        slots: [{
          file_id: pf.file_id,
          signature_x: props.defaultX,
          signature_y: props.defaultY,
          signature_page: props.defaultPage,
          signature_width: props.defaultWidth ?? null,
          signature_height: props.defaultHeight ?? null,
        }],
      })
    }
  } else if (props.pdfUrls && props.pdfUrls.length > 0) {
    // 兼容旧版：纯 URL 列表 → 生成临时 id
    for (let i = 0; i < props.pdfUrls.length; i++) {
      list.push({
        file_id: -(i + 1),  // 负 id 表示兼容模式的临时文件
        name: `文件 ${i + 1}`,
        url: props.pdfUrls[i],
        checked: true,
        slots: [{
          file_id: -(i + 1),
          signature_x: props.defaultX,
          signature_y: props.defaultY,
          signature_page: props.defaultPage,
          signature_width: null,
          signature_height: null,
        }],
      })
    }
  }

  files.value = list
  if (list.length > 0) {
    activeFileId.value = list[0].file_id
    activeSlotIdx.value = 0
  }
}

// ========== 文件/槽位选择 ==========

async function selectFile(fileId: number) {
  const f = files.value.find(x => x.file_id === fileId)
  if (!f || !f.checked) return
  activeFileId.value = fileId
  activeSlotIdx.value = 0  // 切换文件时重置到第一个槽位

  // 尝试加载该文件的 PDF
  loadingPdf.value = true
  try {
    const params: any = { url: f.url }
    if (props.authToken) {
      params.httpHeaders = { Authorization: `Bearer ${props.authToken}` }
    }
    pdfDoc = await pdfjsLib.getDocument(params).promise
    totalPages.value = pdfDoc.numPages

    if (props.defaultPage < 0 && pdfDoc.numPages > 0) {
      currentPage.value = pdfDoc.numPages
    } else {
      currentPage.value = Math.min(Math.max(1, props.defaultPage), pdfDoc.numPages)
    }
    // 同步槽位位置和尺寸（首次加载时使用默认位置）
    if (f.slots.length > 0) {
      currentSigX.value = f.slots[0].signature_x
      currentSigY.value = f.slots[0].signature_y
      currentSigW.value = f.slots[0].signature_width ?? (props.defaultWidth ?? 100)
      currentSigH.value = f.slots[0].signature_height ?? (props.defaultHeight ?? 26)
    }
    await renderPage(currentPage.value)
  } catch (err) {
    console.warn('[SignaturePreview] PDF 加载失败:', f.name, f.url, err)
    totalPages.value = 0
  } finally {
    loadingPdf.value = false
  }
}

function selectSlot(fileId: number, slotIdx: number) {
  activeFileId.value = fileId
  activeSlotIdx.value = slotIdx
  const f = files.value.find(x => x.file_id === fileId)
  if (!f || slotIdx >= f.slots.length) return
  const slot = f.slots[slotIdx]
  currentSigX.value = slot.signature_x
  currentSigY.value = slot.signature_y
  currentSigW.value = slot.signature_width ?? (props.defaultWidth ?? 100)
  currentSigH.value = slot.signature_height ?? (props.defaultHeight ?? 26)
  // 切换到该槽位的页码
  let page = slot.signature_page
  if (page < 0 && totalPages.value > 0) page = totalPages.value
  if (page > 0 && page <= totalPages.value && page !== currentPage.value) {
    goPage(page)
  }
}

function addSlot(f: FileState) {
  f.slots.push({
    file_id: f.file_id,
    signature_x: props.defaultX,
    signature_y: props.defaultY,
    signature_page: props.defaultPage,
    signature_width: props.defaultWidth ?? null,
    signature_height: props.defaultHeight ?? null,
  })
}

function removeSlot(f: FileState, idx: number) {
  if (f.slots.length <= 1) return
  f.slots.splice(idx, 1)
  if (activeFileId.value === f.file_id && activeSlotIdx.value >= f.slots.length) {
    activeSlotIdx.value = f.slots.length - 1
  }
}

function onFileCheckChange(f: FileState) {
  if (!f.checked && activeFileId.value === f.file_id) {
    // 如果取消选中的是当前活跃文件，切换到第一个选中的
    const firstChecked = files.value.find(x => x.checked)
    if (firstChecked) {
      selectFile(firstChecked.file_id)
    }
  }
}

function toggleAll(checked: boolean) {
  for (const f of files.value) {
    f.checked = checked
  }
  if (!checked) {
    activeFileId.value = 0
  } else if (files.value.length > 0 && !activeFileId.value) {
    selectFile(files.value[0].file_id)
  }
}

// ========== PDF 渲染 ==========

async function renderPage(pageNum: number) {
  if (!pdfDoc || !canvasRef.value) return
  loadingPdf.value = true
  try {
    const page = await pdfDoc.getPage(pageNum)
    const viewport = page.getViewport({ scale: zoomLevel.value })
    const canvas = canvasRef.value
    canvas.width = viewport.width
    canvas.height = viewport.height
    const ctx = canvas.getContext('2d')!
    await page.render({ canvasContext: ctx, viewport }).promise
  } catch (err) {
    console.warn('[SignaturePreview] 页面渲染失败:', pageNum, err)
  } finally {
    loadingPdf.value = false
  }
}

async function goPage(page: number) {
  if (page < 1 || page > totalPages.value || loadingPdf.value) return
  currentPage.value = page
  await renderPage(page)

  // 回写当前槽位的页码
  const f = files.value.find(x => x.file_id === activeFileId.value)
  if (f && activeSlotIdx.value < f.slots.length) {
    f.slots[activeSlotIdx.value].signature_page = page
  }
}

// ========== 坐标转换 ==========

/** 将鼠标事件 clientX/Y 转为 PDF 坐标（除以 zoomLevel 归一化，与后端坐标一致） */
function toCanvasPos(e: MouseEvent): { x: number; y: number } {
  const canvas = canvasRef.value
  if (!canvas) return { x: e.clientX, y: e.clientY }
  const rect = canvas.getBoundingClientRect()
  return {
    x: (e.clientX - rect.left) * (canvas.width / rect.width) / zoomLevel.value,
    y: (e.clientY - rect.top) * (canvas.height / rect.height) / zoomLevel.value,
  }
}

// ========== 拖拽 ==========

function startDrag(e: MouseEvent) {
  dragging.value = true
  const pos = toCanvasPos(e)
  dragStart.value = { x: pos.x, y: pos.y }
  sigStart.value = { x: currentSigX.value, y: currentSigY.value }
}

function onDrag(e: MouseEvent) {
  if (!dragging.value) return
  const pos = toCanvasPos(e)
  const dx = pos.x - dragStart.value.x
  const dy = pos.y - dragStart.value.y
  currentSigX.value = Math.max(0, sigStart.value.x + dx)
  currentSigY.value = Math.max(0, sigStart.value.y + dy)
}

function endDrag() {
  if (!dragging.value) return
  dragging.value = false
  // 拖拽结束后回写到当前槽位
  const f = files.value.find(x => x.file_id === activeFileId.value)
  if (f && activeSlotIdx.value < f.slots.length) {
    f.slots[activeSlotIdx.value].signature_x = Math.round(currentSigX.value)
    f.slots[activeSlotIdx.value].signature_y = Math.round(currentSigY.value)
  }
}

/** 统一的 wrapper mousemove 处理（移动 + 缩放） */
function onWrapperMouseMove(e: MouseEvent) {
  if (dragging.value) onDrag(e)
  else if (resizing.value) onResize(e)
}

/** 统一的 wrapper mouseup/leave 处理 */
function onWrapperMouseUp() {
  if (dragging.value) endDrag()
  else if (resizing.value) endResize()
}

// ========== 缩放 ==========

/** 缩放开始（四角拖拽） */
function startResize(dir: 'se' | 'sw' | 'ne' | 'nw', e: MouseEvent) {
  e.stopPropagation()
  e.preventDefault()
  resizing.value = true
  resizeDir.value = dir
  const pos = toCanvasPos(e)
  resizeStart.value = { x: pos.x, y: pos.y, w: currentSigW.value, h: currentSigH.value }
}

/** 缩放中 */
function onResize(e: MouseEvent) {
  if (!resizing.value) return
  const pos = toCanvasPos(e)
  const dx = pos.x - resizeStart.value.x
  const dy = pos.y - resizeStart.value.y
  const startW = resizeStart.value.w
  const startH = resizeStart.value.h

  // 计算新尺寸（四角不同方向）
  let newW: number, newH: number
  switch (resizeDir.value) {
    case 'se':
      newW = startW + dx
      newH = startW > 0 ? newW * (startH / startW) : startH  // 保持比例
      break
    case 'sw':
      newW = startW - dx
      newH = startW > 0 ? newW * (startH / startW) : startH
      break
    case 'ne':
      newH = startH - dy
      newW = startH > 0 ? newH * (startW / startH) : startW
      break
    case 'nw':
      newH = startH - dy
      newW = startH > 0 ? newH * (startW / startH) : startW
      break
  }

  // 最小尺寸限制
  currentSigW.value = Math.max(20, newW)
  currentSigH.value = Math.max(8, newH)
}

/** 缩放结束，回写当前槽位 */
function endResize() {
  if (!resizing.value) return
  resizing.value = false
  const f = files.value.find(x => x.file_id === activeFileId.value)
  if (f && activeSlotIdx.value < f.slots.length) {
    f.slots[activeSlotIdx.value].signature_width = Math.round(currentSigW.value)
    f.slots[activeSlotIdx.value].signature_height = Math.round(currentSigH.value)
  }
}

// ========== 确认 ==========

function handleConfirm() {
  // 收集所有选中文件的所有签名槽位
  const result: SignatureSlot[] = []
  for (const f of files.value) {
    if (!f.checked) continue
    for (const slot of f.slots) {
      result.push({ ...slot })
    }
  }
  emit('confirm', result)
  dialogVisible.value = false
}

function handleClose() {
  pdfDoc = null
  totalPages.value = 0
  currentPage.value = 1
  files.value = []
  activeFileId.value = 0
  activeSlotIdx.value = 0
  loadingPdf.value = false
  initializing.value = false
  zoomLevel.value = 1.0  // 重置缩放
}
</script>

<style lang="scss" scoped>
.sig-preview {
  .sig-layout {
    display: flex;
    gap: 16px;
    min-height: 480px;
    max-height: calc(90vh - 180px);  /* 弹窗内最大高度，避免溢出 */
  }

  // ─── 左侧文档列表 ───
  .sig-sidebar {
    width: 240px;
    flex-shrink: 0;
    border-right: 1px solid var(--el-border-color-light);
    padding-right: 12px;
    display: flex;
    flex-direction: column;

    &__title {
      font-size: 14px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      margin-bottom: 10px;
    }

    &__empty {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: var(--el-text-color-secondary);
      font-size: 13px;
      text-align: center;
      padding: 20px;
    }

    &__empty-hint {
      font-size: 12px;
      color: var(--el-text-color-placeholder);
      margin-top: 6px;
    }

    &__actions {
      margin-top: auto;
      padding-top: 10px;
      display: flex;
      gap: 4px;
    }
  }

  .sig-file-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .sig-file-item {
    border-radius: 6px;
    padding: 4px 6px;
    transition: background 0.15s;

    &--active {
      background: var(--el-color-primary-light-9);
    }

    &--unchecked {
      opacity: 0.55;
    }

    &:hover {
      background: var(--el-fill-color);
    }

    &--active:hover {
      background: var(--el-color-primary-light-8);
    }
  }

  .sig-file-row {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    padding: 2px 0;
  }

  .sig-file-name {
    font-size: 13px;
    color: var(--el-text-color-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sig-slot-row {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: 20px;
    padding: 3px 6px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    transition: background 0.12s;

    &:hover {
      background: var(--el-fill-color-light);
    }

    &--active {
      background: var(--el-color-primary-light-8);
      color: var(--el-color-primary);
    }
  }

  .sig-slot-icon {
    font-size: 11px;
  }

  .sig-slot-label {
    flex: 1;
  }

  .sig-add-slot {
    margin-left: 20px;
    font-size: 12px;
    padding: 2px 6px;
  }

  // ─── 右侧 PDF 预览 ───
  .sig-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .sig-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    flex-shrink: 0;
    gap: 12px;

    .page-indicator {
      display: inline-flex;
      align-items: center;
      padding: 0 14px;
      font-size: 14px;
      font-weight: 500;
      color: var(--el-text-color-primary);
    }

    .sig-zoom-group {
      .zoom-indicator {
        display: inline-flex;
        align-items: center;
        padding: 0 12px;
        font-size: 13px;
        font-weight: 500;
        color: var(--el-text-color-primary);
        min-width: 48px;
        justify-content: center;
      }
    }

    .sig-hint {
      font-size: 12px;
      color: var(--el-text-color-secondary);
      margin-left: auto;
    }
  }

  .sig-canvas-wrapper {
    flex: 1;
    border: 1px solid var(--el-border-color);
    border-radius: 4px;
    overflow: auto;
    background: #f5f5f5;
    text-align: center;
    cursor: default;
    user-select: none;
    min-height: 400px;
    position: relative;  // 叠加层的定位容器
  }

  .sig-canvas-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--el-text-color-placeholder);
    font-size: 14px;
    background: rgba(245, 245, 245, 0.85);
    z-index: 10;
  }

  .sig-canvas-stage {
    margin: auto;
    // canvas 和 overlay 在此容器内共享同一 (0,0) 原点
    // line-height:0 内联在 template 中设置
  }

  .sig-overlay {
    position: absolute;
    cursor: grab;
    border: 2px dashed var(--el-color-primary);
    border-radius: 4px;
    padding: 2px;
    background: rgba(64, 158, 255, 0.08);
    transition: box-shadow 0.15s;
    box-sizing: border-box;
    overflow: hidden;

    &:hover {
      box-shadow: 0 0 8px rgba(64, 158, 255, 0.3);
    }

    .sig-image {
      display: block;
      width: 100%;
      height: 100%;               // 填满 overlay，不再预留标签高度
      object-fit: contain;
      opacity: 0.85;
    }

    .sig-label {
      position: absolute;
      bottom: 1px;
      right: 3px;
      font-size: 9px;
      color: var(--el-color-primary);
      background: rgba(255, 255, 255, 0.75);
      padding: 0 3px;
      border-radius: 2px;
      line-height: 1.4;
      pointer-events: none;       // 不阻挡拖拽
    }

    // ── 四角缩放手柄 ──
    .sig-resize-handle {
      position: absolute;
      width: 10px;
      height: 10px;
      background: var(--el-color-primary);
      border: 1.5px solid #fff;
      border-radius: 2px;
      z-index: 5;

      &:hover {
        background: var(--el-color-primary-dark-2);
      }
    }

    .sig-resize--nw {
      top: -5px; left: -5px;
      cursor: nw-resize;
    }
    .sig-resize--ne {
      top: -5px; right: -5px;
      cursor: ne-resize;
    }
    .sig-resize--sw {
      bottom: -5px; left: -5px;
      cursor: sw-resize;
    }
    .sig-resize--se {
      bottom: -5px; right: -5px;
      cursor: se-resize;
    }
  }

  .sig-coords {
    margin-top: 8px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    flex-shrink: 0;
  }

  .sig-error {
    color: var(--el-color-danger);
    font-size: 13px;
    margin-right: 12px;
  }
}
</style>
