# 企业流程审批系统 — 前端

## 技术栈

- Vue 3 + TypeScript（Composition API）
- Element Plus 2.x 组件库
- LogicFlow 流程设计器
- Pinia 状态管理
- Vue Router 4 路由
- Axios HTTP 客户端

## 快速启动

```bash
cd frontend

# 安装依赖
npm install

# 开发模式（默认 http://localhost:5173）
npm run dev

# 类型检查
npx vue-tsc --noEmit

# 生产构建
npm run build
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_API_BASE_URL` | 后端 API 地址 | `/api/v1` |
| `VITE_WS_URL` | WebSocket 地址 | `ws://当前域名/api/v1/ws` |

## 目录结构

```
frontend/src/
├── api/            # 16 个 API 模块，按后端路由对应
│   └── request.ts  # Axios 实例 + 拦截器（Token 注入、401 跳转）
├── components/     # 全局可复用组件
│   ├── NotificationBell.vue  # 通知铃铛（WebSocket 实时 + 30s 轮询兜底）
│   ├── UserSelector.vue      # 用户选择器
│   └── ...
├── composables/    # 组合函数（useBreadcrumb 等）
├── layouts/        # 布局组件（AppLayout：侧边栏 + 顶栏 + 面包屑）
├── router/         # 23 个路由 + 全局守卫（登录校验 + 角色校验）
├── stores/         # Pinia 状态（userStore、notificationStore）
├── styles/         # SCSS 主题变量 + 全局样式
├── types/          # TypeScript 类型定义
├── utils/          # 工具函数（日期格式化、文件大小格式化等）
└── views/          # 页面组件
    ├── admin/      # 系统管理（用户/组织/角色/配置/文件模板）
    ├── dashboard/  # 首页看板
    ├── error/      # 403/404 错误页
    ├── flows/      # 流程管理（设计器/模板详情/实例详情/组织主页）
    ├── login/      # 登录页
    ├── overdue/    # 超期预警页
    ├── profile/    # 个人中心（多 Tab：待办/校验/审批/批准/发起）
    └── proposals/  # 方案管理
```

## 开发约定

- 使用 `<script setup lang="ts">` + Composition API
- 中文注释标注关键逻辑
- 表格分页统一右下角
- 表格操作列按钮左对齐
