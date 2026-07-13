import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import { setupRouterGuards } from './guards'

/** 扩展路由 meta 类型 */
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    /** 允许访问的角色列表，不设置表示所有已登录用户可访问 */
    roles?: string[]
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
        meta: { title: '首页看板' },
      },
      {
        path: 'flows',
        name: 'Flows',
        component: () => import('@/views/flows/index.vue'),
        meta: { title: '流程管理', roles: ['manager', 'user'] },
      },
      {
        path: 'flows/detail/:id',
        name: 'TemplateDetail',
        component: () => import('@/views/flows/TemplateDetail.vue'),
        meta: { title: '模板详情', roles: ['manager', 'user'] },
      },
      {
        path: 'flows/designer/:id',
        name: 'FlowDesigner',
        component: () => import('@/views/flows/FlowDesigner.vue'),
        meta: { title: '流程设计器', roles: ['manager'] },
      },
      {
        path: 'flows/start',
        name: 'StartInstance',
        component: () => import('@/views/flows/StartInstance.vue'),
        meta: { title: '发起流程实例', roles: ['manager'] },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/index.vue'),
        meta: { title: '个人中心', roles: ['manager', 'user'] },
      },
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/index.vue'),
        meta: { title: '系统管理', roles: ['system_admin'] },
      },
      {
        path: 'admin/organizations',
        name: 'AdminOrgs',
        component: () => import('@/views/admin/index.vue'),
        meta: { title: '系统管理', roles: ['system_admin'] },
      },
      {
        path: 'admin/roles',
        name: 'AdminRoles',
        component: () => import('@/views/admin/index.vue'),
        meta: { title: '系统管理', roles: ['system_admin'] },
      },
      {
        path: 'admin/config',
        name: 'AdminConfig',
        component: () => import('@/views/admin/index.vue'),
        meta: { title: '系统管理', roles: ['system_admin'] },
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
