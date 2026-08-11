# 智展研究院设计开发管理系统

<p align="center">
  <strong>以流程驱动项目的企业级业务管理平台</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-deployable-success" alt="status">
  <img src="https://img.shields.io/badge/tests-326%20passed-brightgreen" alt="tests">
  <img src="https://img.shields.io/badge/python-3.10+-blue" alt="python">
  <img src="https://img.shields.io/badge/vue-3.5-brightgreen" alt="vue">
</p>

---

## 这是什么

不是传统 OA 请假系统。是让一个项目像流水线一样自动推进的审批管理平台。

- 所长画一条流程（比如"初步设计 → 校对 → 审核 → 批准 → 归档"）
- 发起时指定每个环节谁做、谁校验、谁审批
- 系统自动推任务，文件自动转 PDF、签名自动上文档、所有操作有日志

> 新手入门：[用户使用手册](docs/user-manual/用户使用手册.md)

---

## 流程全景

```
  所长设计模板              发起项目实例           节点执行与审批
┌──────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│              │    │                  │    │  负责人上传文件       │
│  拖拽节点     │    │  选模板、调配置    │    │      ↓              │
│  配置审批人   │──→│  指定每节点人员    │──→│  系统自动转 PDF       │
│  发布上线     │    │  确认发起         │    │      ↓              │
│              │    │                  │    │  校验人并行校验       │
└──────────────┘    └──────────────────┘    │      ↓              │
                                            │  审批人并行审批       │
                                            │      ↓              │
                                            │  [难度4] 批准人签阅   │
                                            │      ↓              │
                                            │  签名上PDF → 下一节点 │
                                            └─────────────────────┘
```

---

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 前端框架 | Vue 3 + TypeScript | Composition API |
| UI 组件 | Element Plus | 企业级组件库 |
| 流程设计器 | LogicFlow | 滴滴开源，拖拽式流程编辑 |
| 后端框架 | FastAPI | 异步 Python 框架 |
| ORM | SQLAlchemy 2.0 | 异步模式 |
| 数据库 | MySQL 8.0 | InnoDB，操作日志按年分区 |
| 任务队列 | Redis + arq | PDF 转换异步化 |
| 认证 | JWT | python-jose |
| 实时通信 | WebSocket + Redis Pub/Sub | 通知实时推送，30s 轮询兜底 |
| PDF 转换 | LibreOffice | 无头模式，asyncio.Semaphore 限流 4 并发 |
| PDF 签名 | pypdf | 签名图片插入，多角色多槽位 |

---

## 角色体系

| 角色 | 标识 | 职责 |
|------|------|------|
| 系统管理员 | `system_admin` | 用户/组织/角色/配置/文件模板维护，不参与业务 |
| 所长 | `manager` | 设计流程、发起与终止项目、终审 |
| 普通用户 | `user` | 执行节点、上传文件、校验、审批 |

> 一个人可以有多个角色，所长也可以被分配去做审批人

---

## 主要功能

<table>
<tr>
<td width="50%">

**流程设计器**
- 拖拽节点、配置负责人/校验人/审批人/批准人/时限
- 连线即流程，发布前自动校验完整性和连通性
- 支持 fork/join 并行分叉汇合

**文件处理**
- 上传 Word/Excel/图片/PDF，非 PDF 自动转 PDF
- 节点可配置文件提交分类（文件夹模式，必填/可选 + 数量限制）
- 文件模板下载时自动替换 15 个占位符（项目名称、发起日期等）

**签批**
- 用户上传签名图片（PNG 透明底）
- 审批/批准通过后签名自动插入 PDF，多角色多槽位
- 拖拽调整位置，签名下方显示中文日期

</td>
<td width="50%">

**通知**
- WebSocket 推送 + 30s 轮询兜底
- 侧边栏角标、个人中心 Tab 角标、首页红点实时更新
- 预留企业微信通知集成

**截止时间预警**
- 逾期标红、临期（≤1天）标黄
- 覆盖首页、个人中心、项目管理、方案管理全部列表

**紧急处理**
- 发起人可随时更换未完成节点的人员
- 优先级和截止时间随时可调
- 任何状态的项目均可终止（不可恢复）

**操作日志**
- 所有流程操作记录日志，按年分区
- 只写不删，完整审计

</td>
</tr>
</table>

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0
- Redis 6.x+
- LibreOffice 7.x+（PDF 转换核心依赖，需安装；验证：`soffice --headless --version`）

### 后端

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env    # 按需修改 DB_HOST/DB_PASSWORD/SECRET_KEY/DEFAULT_ADMIN_PASSWORD 等；开发环境 ENV 保持 development

python -m app.core.deploy_db   # 建库 + 建表 + 操作日志分区 + alembic 基线（全新库专用，见 04_Deployment.md）
python -m app.core.seed        # 预置角色/组织/配置/管理员 admin

uvicorn app.main:app --reload                       # 开发热重载
python -m arq app.worker.WorkerSettings             # 后台 PDF 转换 Worker（不启则 PDF 转换功能不可用）
```

Swagger：`http://localhost:8000/docs`

### 前端

```bash
cd frontend
npm install
npm run dev          # 开发
npm run build        # 生产构建
```

### 默认管理员

| 用户名 | 密码 |
|--------|------|
| `admin` | 环境变量 `DEFAULT_ADMIN_PASSWORD` 设定的值 |

---

## 测试

```bash
pytest tests/ -v          # Mock 测试 291 条（225 单元 + 66 集成），毫秒级
pytest tests/mysql/ -v    # MySQL 真实测试 29 条，需要 workflow_approval_test 库
```

| 类型 | 数量 | 说明 |
|------|:--:|------|
| 单元测试 | 225 | 内存运行，毫秒级 |
| 集成测试 | 66 | TestClient + mock_db |
| MySQL 真实 | 29 | SAVEPOINT 隔离，独立建表删表 |
| **合计** | **326** | **无已知未修复问题** |

---

## 文档

| 文档 | 说明 |
|------|------|
| [用户使用手册](docs/user-manual/用户使用手册.md) | 操作步骤，20 分钟上手 |
| [开发者上手指南](Developer_Documentation.md) | 环境搭建、目录结构、常用命令 |
| [技术蓝图](00_Project_Blueprint.md) | 系统架构、状态机、流程引擎设计 |
| [产品需求文档](01_PRD.md) | 功能模块与交互流程 |
| [数据库设计](02_Database_Design.md) | 24 张表完整 DDL + ER 图 + 分区策略 |
| [API 设计](03_API_Design.md) | 92 个 HTTP 端点 + 1 个 WebSocket |
| [部署运维](04_Deployment.md) | Nginx、HTTPS、备份 |
| [变更日志](CHANGELOG.md) | 版本变更记录 |
| [审计修复日志](AUDIT_FIX_LOG.md) | 全量代码审计 + 修复记录 |
| [CLAUDE.md](CLAUDE.md) | AI 辅助开发指南 |
| [企业微信通知集成](docs/superpowers/specs/2026-07-29-wework-notification-design.md) | 设计方案（待实施） |

---

## 项目结构

```
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/              # 18 个路由文件，92 端点
│   │   ├── models/           # 24 个模型，24 张表
│   │   ├── schemas/          # Pydantic 请求/响应 Schema
│   │   ├── services/         # 业务逻辑层
│   │   └── core/             # 配置/安全/数据库/种子/限流
│   ├── alembic/              # 数据库迁移
│   ├── tests/                # 317 条测试
│   └── storage/archive/      # 文件存储
├── frontend/                 # Vue 3 前端
│   └── src/
│       ├── views/            # admin / dashboard / flows / profile / proposals
│       ├── api/              # 请求封装 + 类型定义
│       ├── stores/           # Pinia 状态管理
│       └── components/       # 公共组件
└── docs/
    ├── user-manual/          # 用户使用手册 + 截图
    └── superpowers/          # 设计规范与实施计划
```
