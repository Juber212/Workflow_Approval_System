# 企业流程审批系统

以流程驱动的企业级业务管理平台。不仅限于 OA 审批，而是将每个流程视为独立项目，覆盖模板设计、实例发起、节点执行、多级审批、签批存档、超期预警的全生命周期管理。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + TypeScript + Element Plus + LogicFlow |
| 后端 | FastAPI + SQLAlchemy 2.0（异步） |
| 数据库 | MySQL 8.0 InnoDB |
| 任务队列 | Redis + arq（PDF 转换异步化） |
| 实时通信 | WebSocket + Redis Pub/Sub |
| 文件处理 | LibreOffice（Word/Excel→PDF）+ pypdf（签名） |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0
- LibreOffice 7.x+
- Redis 6.x+

### 部署

详见 [`04_Deployment.md`](04_Deployment.md)

```bash
# 后端
cd backend
pip install -r requirements.txt
cp .env.example .env  # 编辑配置
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run build  # 生产构建；开发用 npm run dev
```

## 项目文档

| 文档 | 说明 |
|------|------|
| [`00_Project_Blueprint.md`](00_Project_Blueprint.md) | 系统架构、状态机、业务规则执行细节 |
| [`01_PRD.md`](01_PRD.md) | 产品需求文档，功能模块与交互流程 |
| [`02_Database_Design.md`](02_Database_Design.md) | 数据库完整设计（DDL、ER、分区策略） |
| [`03_API_Design.md`](03_API_Design.md) | REST API 端点清单（72 个 HTTP + 1 WebSocket） |
| [`04_Deployment.md`](04_Deployment.md) | 部署与运维（Nginx 配置、备份策略） |
| [`CHANGELOG.md`](CHANGELOG.md) | 版本变更记录 |
| [`Developer_Documentation.md`](Developer_Documentation.md) | 开发历程与技术决策记录 |
| [`Learning_Journal.md`](Learning_Journal.md) | 问题与经验积累 |
| [`AUDIT_FIX_LOG.md`](AUDIT_FIX_LOG.md) | 全量代码审计修复日志 |
| [`CLAUDE.md`](CLAUDE.md) | AI 辅助开发指南（项目上下文） |

## 项目状态

✅ 可部署上线 | 测试 190 条（0 业务逻辑 bug）| 后端 30 Service + 18 API 模块 | 前端 23 路由

## 核心特性

- **统一节点模型**：不区分开始/工作/结束，行为由位置决定
- **并行审批**：校验/审批/批准并行处理，支持 fork/join 分叉汇合
- **PDF 自动转换**：Word/Excel/图片提交时自动转 PDF
- **签批上文档**：审批通过后签名自动插入 PDF 指定坐标
- **备选审批策略**：支持 all_approve（全票通过）和 single_approve（一票通过）
- **四档难度**：难度 4 级引入批准人（Endorser）额外审批层
- **实时通知**：WebSocket 推送 + 30s 轮询兜底，侧边栏角标实时更新
- **紧急换人**：发起人可随时更换运行中实例的人员，支持兜底
- **文件模板**：Word/Excel 模板 + 15 个占位符自动替换
- **超期预警**：独立的超期项汇总页面，逾期标红警告
- **操作日志**：按年分区，只写不删，完整追溯

## 角色体系

| 角色 | 职责 |
|------|------|
| 系统管理员 | 用户/组织/角色/系统配置/文件模板维护 |
| 所长 | 流程模板设计、发起/终止流程、终审 |
| 普通用户 | 节点执行、上传文件、校验/审批 |
