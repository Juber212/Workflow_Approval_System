/**
 * 详情页加载公共逻辑 —— 403 处理 + loading + 面包屑 + 路由参数监听
 * Task/Check/Approval/Endorse 四页共用（P2-2 抽取）
 */
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useBreadcrumb } from './useBreadcrumb'

export function useDetailLoad<T>(options: {
  /** 详情加载函数（各页各自的 getXDetail） */
  loadFn: (id: number) => Promise<T>
  /** 面包屑末段文案（任务处理/校验处理/审批处理/批准处理） */
  breadcrumbTail: string
  /** 加载成功后的附加处理（如赋值备注、展开历史文件） */
  onLoaded?: (data: T) => void
}) {
  const route = useRoute()
  const { setBreadcrumb } = useBreadcrumb()

  const loading = ref(false)
  const forbidden = ref(false)  // P1-34：403 无权限 → 渲染「无权查看」页
  const detail = ref<T | null>(null)

  // M29：请求序号——同组件内快速切换记录时丢弃过期响应，防旧记录数据覆盖新记录
  let reqSeq = 0

  /** 加载详情（onMounted + 路由参数变化共用） */
  async function load() {
    const mySeq = ++reqSeq
    setBreadcrumb([
      { label: '首页', to: '/dashboard' },
      { label: '个人中心', to: '/profile' },
      { label: options.breadcrumbTail },
    ])
    const id = Number(route.params.id)
    if (!id) return
    loading.value = true
    forbidden.value = false  // P1-34：同组件切换路由参数时重置 403 状态
    try {
      const data = await options.loadFn(id)
      if (mySeq !== reqSeq) return  // 过期响应丢弃（M29）
      detail.value = data
      options.onLoaded?.(detail.value)
    } catch (e: any) {
      if (mySeq !== reqSeq) return
      // 非本人记录后端返回 403 → 渲染「无权查看」页
      if (e?.status === 403) forbidden.value = true
    } finally {
      if (mySeq === reqSeq) loading.value = false
    }
  }

  onMounted(load)
  // 同页面内切换记录（如点击通知跳转），监听路由参数变化重新加载
  watch(() => route.params.id, load)

  return { loading, forbidden, detail, load }
}
