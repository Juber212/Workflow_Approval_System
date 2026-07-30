# 开发者上手指南

> 面向新开发者或 AI agent 的项目快速上手指南。架构设计见 `CLAUDE.md` 及各设计文档。

---

## 1. 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 后端 |
| Node.js | 18+ | 前端 |
| MySQL | 8.0 | 数据库（InnoDB，utf8mb4） |
| LibreOffice | 任意 | PDF 转换（无头模式），非必须（开发可跳过） |

---

## 2. 目录结构

```
Workflow_Approval_System/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/                # 18 个路由文件，99 个 HTTP 端点 + 1 WebSocket
│   │   ├── models/             # 24 个 SQLAlchemy 模型（24 张表）
│   │   ├── schemas/            # Pydantic 请求/响应 Schema
│   │   ├── services/           # 业务逻辑层
│   │   ├── core/               # 配置/安全/数据库/种子数据/限流/异常
│   │   └── middleware/         # 中间件（CORS 等）
│   ├── alembic/                # 数据库迁移（versions/ 下 20+ 个迁移文件）
│   ├── tests/                  # 190 条测试（unit / integration / mysql）
│   ├── storage/archive/        # 文件存储根目录
│   └── requirements.txt
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── api/                # Axios 请求封装 + 类型定义
│   │   ├── components/         # 公共组件
│   │   ├── composables/        # 组合式函数
│   │   ├── layouts/            # 布局组件（AppLayout）
│   │   ├── router/             # Vue Router 路由配置
│   │   ├── stores/             # Pinia 状态管理（user / notification）
│   │   ├── styles/             # 全局样式 + Element Plus 主题变量
│   │   ├── utils/              # 工具函数（format / labels）
│   │   └── views/              # 页面组件
│   │       ├── admin/          # 系统管理（用户/组织/角色/配置/文件模板）
│   │       ├── dashboard/      # 首页仪表盘
│   │       ├── flows/          # 项目管理 + 设计器 + 详情
│   │       ├── profile/        # 个人中心（任务/校验/审批/批准）
│   │       └── proposals/      # 方案管理
│   └── package.json
├── docs/superpowers/           # AI 辅助开发的设计文档和计划
├── 00_Project_Blueprint.md     # 技术蓝图
├── 01_PRD.md                   # 产品需求文档
├── 02_Database_Design.md       # 数据库设计
├── 03_API_Design.md            # API 接口设计
├── CLAUDE.md                   # AI 开发上下文（每次会话自动加载）
├── CHANGELOG.md                # 变更日志
├── AUDIT_FIX_LOG.md            # 审计修复日志
└── Developer_Documentation.md  # 本文件
```

---

## 3. 后端快速开始

```bash
cd backend

# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 环境变量
export DATABASE_URL="mysql+aiomysql://root:password@localhost:3306/workflow_approval"
export SECRET_KEY="your-production-secret-key"
export DEFAULT_ADMIN_PASSWORD="admin-initial-password"

# 4. 创建数据库（MySQL）
mysql -u root -p -e "CREATE DATABASE workflow_approval CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p -e "CREATE DATABASE workflow_approval_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 5. 运行迁移 + 种子数据
alembic upgrade head
python -m app.core.seed

# 6. 启动（开发模式，默认 8000 端口）
uvicorn app.main:app --reload
```

Swagger 文档：`http://localhost:8000/docs`

---

## 4. 前端快速开始

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 启动开发服务器（默认 5173 端口，代理 /api → 后端）
npm run dev

# 3. 类型检查
npx vue-tsc --noEmit

# 4. 构建生产版本
npm run build
```

环境变量（`.env.development`）：`VITE_API_BASE_URL=http://localhost:8000/api/v1`

---

## 5. 常用命令

```bash
# ── 测试 ──
cd backend
pytest tests/ -v                 # Mock 测试（190 条，13s）
pytest tests/mysql/ -v           # MySQL 真实数据库测试（需要 workflow_approval_test 库）

# ── 数据库迁移 ──
cd backend
alembic upgrade head             # 执行所有未应用迁移
alembic revision --autogenerate -m "描述"  # 自动生成迁移文件
alembic downgrade -1             # 回滚一步

# ── 代码质量 ──
cd frontend && npx vue-tsc --noEmit   # 前端类型检查
```

---

## 6. 关键约定

1. **Python 类型注解**：所有 service 函数必须标注参数和返回值类型
2. **TypeScript 接口**：API 返回类型在 `frontend/src/api/*.ts` 中定义，禁止 on-page inline 类型
3. **CSS 穿透**：`el-table` 的 `:row-class-name` 样式必须写在非 scoped `<style lang="scss">` 块中
4. **错误处理**：前端拦截器统一处理 401 跳转和错误消息去重（3 秒内相同消息不重复弹出）
5. **文件存储**：`storage/archive/{实例名称}/`，文件属于实例而非节点或用户
6. **测试优先**：修改 service 后先跑 `pytest tests/ -v`，改前端后跑 `vue-tsc --noEmit`
7. **操作日志**：所有流程操作记录写入 `operation_logs`（按年分区），不可删除
