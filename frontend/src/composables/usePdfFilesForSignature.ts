/**
 * 签批弹窗 PDF 文件列表 —— 按 mime_type 过滤，兜底文件名后缀
 * Check/Approval/Endorse 三页共用（Task 页走 prepareSign 接口，不适用）
 * URL 统一走 api/task 的 fileDownloadUrl，不再硬编码（P2-2 抽取）
 */
import { computed, type ComputedRef } from 'vue'
import { fileDownloadUrl } from '@/api/task'

/** 签批弹窗使用的 PDF 文件项 */
export interface SignaturePdfFile {
  file_id: number
  name: string
  url: string
}

export function usePdfFilesForSignature(
  nodeFiles: ComputedRef<Array<{ id: number; original_name?: string; mime_type?: string | null }> | undefined>,
) {
  /** PDF 文件列表（优先 mime_type 判断，兜底用文件名后缀） */
  const pdfFiles = computed<SignaturePdfFile[]>(() => {
    const files = nodeFiles.value
    if (!files) return []
    return files
      .filter(f => f.mime_type === 'application/pdf' || (f.original_name || '').toLowerCase().endsWith('.pdf'))
      .map(f => ({
        file_id: f.id,
        name: f.original_name || '',
        url: fileDownloadUrl(f.id),
      }))
  })

  /** PDF 预览 URL 数组（旧版兼容） */
  const pdfPreviewUrls = computed(() => pdfFiles.value.map(f => f.url))

  return { pdfFiles, pdfPreviewUrls }
}
