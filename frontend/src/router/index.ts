import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import { setupRouterGuards } from './guards'

/** 面包屑项 */
export interface BreadcrumbItem {
  label: string
  to?: string
}

/** 扩展路由 meta 类型 */
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    /** 允许访问的角色列表，不设置表示所有已登录用户可访问 */
    roles?: string[]
    /** 面包屑导航（静态部分），动态部分由页面 provide 补充 */
    breadcrumb?: BreadcrumbItem[]
  }
}

/** 路由配置 —— 一级菜单：Dashboard / 流程管理 / 个人中心 / 系统管理 */
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '首页', breadcrumb: [{ label: '首页' }] },
      },
      {
        path: 'flows',
        name: 'Flows',
        component: () => import('@/views/flows/index.vue'),
        meta: { title: '流程管理', breadcrumb: [{ label: '流程管理' }] },
      },
      {
        path: 'flows/organization/:orgId',
        name: 'OrgHome',
        component: () => import('@/views/flows/OrgHome.vue'),
        meta: { title: '所内主页', breadcrumb: [{ label: '流程管理', to: '/flows' }, { label: '所内主页' }] },
      },
      {
        path: 'flows/detail/:id',
        name: 'TemplateDetail',
        component: () => import('@/views/flows/TemplateDetail.vue'),
        meta: { title: '模板详情', breadcrumb: [{ label: '流程管理', to: '/flows' }, { label: '模板详情' }] },
      },
      {
        path: 'flows/designer/:id',
        name: 'FlowDesigner',
        component: () => import('@/views/flows/FlowDesigner.vue'),
        meta: { title: '流程设计器', breadcrumb: [{ label: '流程管理', to: '/flows' }, { label: '流程设计器' }] },
      },
      {
        path: 'flows/instances/:id',
        name: 'InstanceDetail',
        component: () => import('@/views/flows/InstanceDetail.vue'),
        meta: { title: '实例详情', breadcrumb: [{ label: '流程管理', to: '/flows' }, { label: '实例详情' }] },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/index.vue'),
        meta: { title: '个人中心', roles: ['manager', 'user'], breadcrumb: [{ label: '个人中心' }] },
      },
      {
        path: 'profile/task/:id',
        name: 'TaskDetail',
        component: () => import('@/views/profile/TaskDetail.vue'),
        meta: { title: '任务处理', roles: ['manager', 'user'], breadcrumb: [{ label: '个人中心', to: '/profile' }, { label: '任务处理' }] },
      },
      {
        path: 'profile/check/:id',
        name: 'CheckDetail',
        component: () => import('@/views/profile/CheckDetail.vue'),
        meta: { title: '校验处理', roles: ['manager', 'user'], breadcrumb: [{ label: '个人中心', to: '/profile' }, { label: '校验处理' }] },
      },
      {
        path: 'profile/approval/:id',
        name: 'ApprovalDetail',
        component: () => import('@/views/profile/ApprovalDetail.vue'),
        meta: { title: '审批处理', roles: ['manager', 'user'], breadcrumb: [{ label: '个人中心', to: '/profile' }, { label: '审批处理' }] },
      },
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/index.vue'),
        meta: { title: '系统管理', roles: ['system_admin'], breadcrumb: [{ label: '系统管理' }] },
      },
      {
        path: 'admin/organizations',
        name: 'AdminOrgs',
        component: () => import('@/views/admin/index.vue'),
        meta: { title: '系统管理', roles: ['system_admin'], breadcrumb: [{ label: '系统管理' }] },
      },
      {
        path: 'admin/roles',
        name: 'AdminRoles',
        component: () => import('@/views/admin/index.vue'),
        meta: { title: '系统管理', roles: ['system_admin'], breadcrumb: [{ label: '系统管理' }] },
      },
      {
        path: 'admin/config',
        name: 'AdminConfig',
        component: () => import('@/views/admin/index.vue'),
        meta: { title: '系统管理', roles: ['system_admin'], breadcrumb: [{ label: '系统管理' }] },
      },
    ],
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error/403.vue'),
    meta: { title: '403' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/404.vue'),
    meta: { title: '404' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 安装全局路由守卫
setupRouterGuards(router)

export default router
