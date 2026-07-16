import { ref } from 'vue'

/** 面包屑单项 */
export interface BreadcrumbItem {
  /** 显示文字 */
  label: string
  /** 可选：点击跳转路径，当前页（最后一级）不传 */
  to?: string
}

/** 模块级共享状态 —— 全局只有一份面包屑 */
const items = ref<BreadcrumbItem[]>([])

/**
 * 面包屑状态管理 composable
 *
 * 用法：页面内调用 setBreadcrumb() 设置，AppLayout 读取 items 渲染
 */
export function useBreadcrumb() {
  /** 设置面包屑（覆盖旧值） */
  function setBreadcrumb(list: BreadcrumbItem[]) {
    items.value = list
  }

  return { items, setBreadcrumb }
}
