/** 面包屑 provide/inject 工具 —— 供页面注入动态面包屑（如组织名称） */
import { provide, inject, type Ref, ref } from 'vue'
import type { BreadcrumbItem } from '@/router'

const BREADCRUMB_KEY = Symbol('pageBreadcrumb')

/** 在页面中使用：设置动态面包屑（覆盖路由静态 meta） */
export function provideBreadcrumb(items: BreadcrumbItem[]) {
  provide(BREADCRUMB_KEY, ref(items))
}

/** 在 AppLayout 中使用：获取页面注入的动态面包屑 */
export function usePageBreadcrumb(): Ref<BreadcrumbItem[] | null> {
  return inject(BREADCRUMB_KEY, ref(null))
}
