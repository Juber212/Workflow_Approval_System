/**
 * 签批弹窗公共逻辑 —— Task/Check/Approval/Endorse 四页共用（P2-2 抽取）
 * 各页差异（签名检查条件、确认后的动作）留在页面内，经参数传入
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { getToken } from '@/api/request'
import type { SignatureSlot } from '@/api/signature'

export function useSignatureDialog() {
  const router = useRouter()

  const showSignatureDialog = ref(false)
  const sigSlots = ref<SignatureSlot[] | null>(null)

  /** 签批弹窗鉴权 Token */
  const authToken = () => getToken() || ''

  /** 打开签批弹窗（重置签名槽位） */
  function openSignatureDialog() {
    sigSlots.value = null
    showSignatureDialog.value = true
  }

  /** 无签名图片 → 提示前往上传（调用方提示后需 return 中断操作） */
  async function promptUploadSignature(message: string) {
    try {
      await ElMessageBox.alert(message, '无法签批', {
        confirmButtonText: '前往上传',
        type: 'warning',
      })
      router.push({ name: 'Profile', query: { tab: 'signature' } })
    } catch {
      // 用户取消或关闭弹窗，不跳转
    }
  }

  /** 生成签批确认回调（确认后执行 after 动作） */
  function makeSignatureConfirm(after: () => void) {
    return (slots: SignatureSlot[]) => {
      sigSlots.value = slots
      showSignatureDialog.value = false
      after()
    }
  }

  return { showSignatureDialog, sigSlots, authToken, openSignatureDialog, promptUploadSignature, makeSignatureConfirm }
}
