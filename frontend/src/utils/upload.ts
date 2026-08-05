/** 上传工具 —— 文件大小预校验（TaskDetail/SupplementFileDialog 共用，P2-2 抽取） */
import { ElMessage } from 'element-plus'

/** 上传文件大小预校验 —— 超过 maxMB 拦截并提示（返回 false 阻止上传） */
export function validateUploadSize(file: File, maxMB = 50): boolean {
  if (file.size > maxMB * 1024 * 1024) {
    ElMessage.warning(`文件「${file.name}」超过 ${maxMB}MB 限制`)
    return false
  }
  return true
}
