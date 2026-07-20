<template>
  <!-- 签名预览弹框 —— PDF 预览 + 拖拽签名定位 -->
  <el-dialog
    v-model="dialogVisible"
    title="签批预览"
    width="860px"
    :close-on-click-modal="false"
    @opened="loadPdf"
    @closed="handleClose"
  >
    <div class="sig-preview">
      <!-- 页面导航 -->
      <div class="sig-toolbar">
        <el-button-group>
          <el-button :disabled="currentPage <= 1" @click="goPage(currentPage - 1)">上一页</el-button>
          <span class="page-indicator">{{ currentPage }} / {{ totalPages || '—' }}</span>
          <el-button :disabled="currentPage >= totalPages" @click="goPage(currentPage + 1)">下一页</el-button>
        </el-button-group>
        <span class="sig-hint">拖拽签名图片调整位置</span>
      </div>

      <!-- PDF 渲染区 + 签名叠加 -->
      <div
        ref="wrapperRef"
        class="sig-canvas-wrapper"
        @mousemove="onDrag"
        @mouseup="endDrag"
        @mouseleave="endDrag"
      >
        <div class="sig-canvas-inner" :style="{ position: 'relative', display: 'inline-block' }">
          <canvas ref="canvasRef" />
          <!-- 签名拖拽叠加层 -->
          <div
            v-if="sigUrl && !loading"
            class="sig-overlay"
            :style="overlayStyle"
            @mousedown.stop="startDrag"
          >
            <img :src="sigUrl" class="sig-image" draggable="false" />
            <span class="sig-label">审批人签名</span>
          </div>
        </div>
      </div>

      <!-- 坐标信息 -->
      <div class="sig-coords">
        签名位置：X={{ Math.round(sigX) }} Y={{ Math.round(sigY) }} · 页码：{{ currentPage }}
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :loading="loading">确认签批</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 签名预览弹框 —— PDF.js 渲染 PDF + 拖拽签名图片定位 */
import { ref, computed, watch, nextTick } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

// 使用本地打包的 worker（避免 CDN 404）
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker

// ========== Props ==========
const props = defineProps<{
  /** 是否显示 */
  modelValue: boolean
  /** PDF 文件 URL 列表（取第一个可用） */
  pdfUrls: string[]
  /** 认证 Token（用于 pdfjs-dist 下载 PDF） */
  authToken?: string
  /** 签名图片 URL */
  sigUrl?: string | null
  /** 默认 X 坐标（距左边） */
  defaultX: number
  /** 默认 Y 坐标（距顶部） */
  defaultY: number
  /** 默认页码 */
  defaultPage: number
  /** 签名图片最大宽度 */
  sigMaxWidth?: number
}>()

// ========== Emits ==========
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'confirm': [pos: { signature_x: number; signature_y: number; signature_page: number }]
}>()

// ========== 状态 ==========
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const loading = ref(false)
const wrapperRef = ref<HTMLDivElement>()
const canvasRef = ref<HTMLCanvasElement>()
const totalPages = ref(0)
const currentPage = ref(1)
const sigX = ref(props.defaultX)
const sigY = ref(props.defaultY)

// 拖拽状态
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const sigStart = ref({ x: 0, y: 0 })

/** 签名叠加层位置样式 */
const overlayStyle = computed(() => ({
  left: `${sigX.value}px`,
  top: `${sigY.value}px`,
}))

// ========== PDF 加载 ==========
let pdfDoc: pdfjsLib.PDFDocumentProxy | null = null

async function loadPdf() {
  loading.value = true
  currentPage.value = 1
  sigX.value = props.defaultX
  sigY.value = props.defaultY

  // 从默认页码加载
  let startPage = props.defaultPage
  if (startPage < 0) startPage = 1 // 先加载第一页，用户看到后可切换

  try {
    // 尝试 URL 列表中的第一个有效 URL
    let loaded = false
    for (const url of props.pdfUrls) {
      try {
        // 如果有 auth token，传给 pdfjs-dist 的 httpHeaders
        const params: any = { url }
        if (props.authToken) {
          params.httpHeaders = { Authorization: `Bearer ${props.authToken}` }
        }
        pdfDoc = await pdfjsLib.getDocument(params).promise
        totalPages.value = pdfDoc.numPages
        loaded = true
        break
      } catch { continue }
    }

    if (!loaded || !pdfDoc) {
      totalPages.value = 0
      return
    }

    // 默认最后一页？
    if (props.defaultPage < 0 && pdfDoc.numPages > 0) {
      currentPage.value = pdfDoc.numPages
    } else {
      currentPage.value = Math.min(Math.max(1, startPage), pdfDoc.numPages)
    }

    await renderPage(currentPage.value)
  } finally {
    loading.value = false
  }
}

/** 渲染指定页码到 canvas */
async function renderPage(pageNum: number) {
  if (!pdfDoc || !canvasRef.value) return
  const page = await pdfDoc.getPage(pageNum)
  const scale = 1.0
  const viewport = page.getViewport({ scale })

  const canvas = canvasRef.value
  canvas.width = viewport.width
  canvas.height = viewport.height
  const ctx = canvas.getContext('2d')!
  await page.render({ canvasContext: ctx, viewport }).promise
}

/** 切换页面 */
async function goPage(page: number) {
  if (page < 1 || page > totalPages.value || loading.value) return
  currentPage.value = page
  await renderPage(page)
}

// ========== 拖拽逻辑 ==========
function startDrag(e: MouseEvent) {
  dragging.value = true
  dragStart.value = { x: e.clientX, y: e.clientY }
  sigStart.value = { x: sigX.value, y: sigY.value }
}

function onDrag(e: MouseEvent) {
  if (!dragging.value) return
  const dx = e.clientX - dragStart.value.x
  const dy = e.clientY - dragStart.value.y
  sigX.value = Math.max(0, sigStart.value.x + dx)
  sigY.value = Math.max(0, sigStart.value.y + dy)
}

function endDrag() {
  dragging.value = false
}

// ========== 确认 ==========
function handleConfirm() {
  emit('confirm', {
    signature_x: Math.round(sigX.value),
    signature_y: Math.round(sigY.value),
    signature_page: currentPage.value,
  })
  dialogVisible.value = false
}

function handleClose() {
  pdfDoc = null
  totalPages.value = 0
  currentPage.value = 1
}
</script>

<style lang="scss" scoped>
.sig-preview {
  .sig-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;

    .page-indicator {
      display: inline-flex;
      align-items: center;
      padding: 0 16px;
      font-size: 14px;
      font-weight: 500;
      color: var(--el-text-color-primary);
    }

    .sig-hint {
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }

  .sig-canvas-wrapper {
    border: 1px solid var(--el-border-color);
    border-radius: 4px;
    max-height: 500px;
    overflow: auto;
    background: #f5f5f5;
    text-align: center;
    cursor: default;
    user-select: none;
  }

  .sig-canvas-inner {
    margin: auto;
  }

  .sig-overlay {
    position: absolute;
    cursor: grab;
    border: 2px dashed var(--el-color-primary);
    border-radius: 4px;
    padding: 2px;
    background: rgba(64, 158, 255, 0.08);
    transition: box-shadow 0.15s;

    &:hover {
      box-shadow: 0 0 8px rgba(64, 158, 255, 0.3);
    }

    .sig-image {
      display: block;
      max-width: 150px;
      max-height: 50px;
      opacity: 0.85;
    }

    .sig-label {
      display: block;
      text-align: center;
      font-size: 10px;
      color: var(--el-color-primary);
      margin-top: 2px;
    }
  }

  .sig-coords {
    margin-top: 10px;
    font-size: 13px;
    color: var(--el-text-color-secondary);
    display: flex;
    gap: 16px;
  }
}
</style>
