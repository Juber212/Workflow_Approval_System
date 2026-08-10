/**
 * 下载助手 —— 统一「blob 响应 → 浏览器保存对话框」逻辑
 * 低危项：抽取 task.ts / template.ts 中 4 处重复的下载实现
 */

/**
 * 从 blob 响应触发浏览器下载
 *
 * @param resp            fetch 响应（调用方负责携带 Authorization 请求头）
 * @param fallbackName    响应头无 Content-Disposition 时的兜底文件名
 * @throws 非 2xx 时抛后端错误消息（解析失败兜底「下载失败」）
 */
export async function downloadBlobResponse(resp: Response, fallbackName: string): Promise<void> {
  if (!resp.ok) {
    const errData = await resp.json().catch(() => ({}))
    throw new Error((errData as any)?.message || '下载失败')
  }
  const blob = await resp.blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  // 从响应头解析文件名：优先 filename*=UTF-8'' 编码名，兜底 filename=
  const disposition = resp.headers.get('Content-Disposition') || ''
  const starMatch = disposition.match(/filename\*=UTF-8''([^;\s]+)/)
  const plainMatch = disposition.match(/filename="?([^";\s]+)"?/)
  const raw = starMatch?.[1] || plainMatch?.[1] || fallbackName
  // 文件名含非法 % 序列时 decodeURIComponent 抛 URIError → 兜底用原始名
  try {
    a.download = decodeURIComponent(raw)
  } catch {
    a.download = raw
  }
  a.click()
  URL.revokeObjectURL(blobUrl)
}
