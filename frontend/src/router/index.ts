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

/** 路由配置 —— 一级菜单：Dashboard / 项目管理 / 个人中心 / 系统管理 */
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
        meta: { title: '首页' },
      },
      {
        path: 'flows',
        name: 'Flows',
        component: () => import('@/views/flows/index.vue'),
        meta: { title: '项目管理' },
      },
      {
        path: 'flows/organization/:orgId',
        name: 'OrgHome',
        component: () => import('@/views/flows/OrgHome.vue'),
        meta: { title: '所内主页' },
      },
      {
        path: 'flows/detail/:id',
        name: 'TemplateDetail',
        component: () => import('@/views/flows/TemplateDetail.vue'),
        meta: { title: '模板详情' },
      },
      {
        path: 'flows/designer/:id',
        name: 'FlowDesigner',
        component: () => import('@/views/flows/FlowDesigner.vue'),
        meta: { title: '项目设计器', roles: ['manager'] },
      },
      {
        path: 'flows/instances/:id',
        name: 'InstanceDetail',
        component: () => import('@/views/flows/InstanceDetail.vue'),
        meta: { title: '项目详情' },
      },
      {
        path: 'proposals',
        name: 'Proposals',
        component: () => import('@/views/proposals/ProposalManagement.vue'),
        meta: { title: '方案管理' },
      },
      {
        path: 'proposals/organization/:orgId',
        name: 'OrgProposalHome',
        component: () => import('@/views/proposals/OrgProposalHome.vue'),
        meta: { title: '所内方案' },
      },
      {
        path: 'proposals/instances/:id',
        name: 'ProposalDetail',
        component: () => import('@/views/flows/InstanceDetail.vue'),
        meta: { title: '方案详情' },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/index.vue'),
        meta: { title: '个人中心', roles: ['manager', 'user'] },
      },
      {
        path: 'profile/task/:id',
        name: 'TaskDetail',
        component: () => import('@/views/profile/TaskDetail.vue'),
        meta: { title: '任务处理', roles: ['manager', 'user'] },
      },
      {
        path: 'profile/check/:id',
        name: 'CheckDetail',
        component: () => import('@/views/profile/CheckDetail.vue'),
        meta: { title: '校验处理', roles: ['manager', 'user'] },
      },
      {
        path: 'profile/approval/:id',
        name: 'ApprovalDetail',
        component: () => import('@/views/profile/ApprovalDetail.vue'),
        meta: { title: '审批处理', roles: ['manager', 'user'] },
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
      {
        path: 'admin/document-templates',
        name: 'AdminDocTemplates',
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
