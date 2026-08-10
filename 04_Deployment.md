# 企业流程审批系统 — 部署与运维

> **版本**：3.0 | **更新**：2026-08-06
> 3.0 变更：全新库建表改为 `deploy_db.py`（阻断修复）；补 Redis 依赖与默认密码；后端改为**单进程 API + 独立 ARQ worker** 双进程；新增 systemd 托管；操作日志分区由部署脚本创建。

---

## 1. 部署架构

```
Browser → Nginx (:80) → /          → /var/www/workflow/ (Vue 3 静态文件)
                       → /api/*     → Uvicorn (:8000) → FastAPI（单进程）
                       → /api/v1/ws → Uvicorn WebSocket
                                                        → MySQL (:3306)
                                                        → Redis (:6379，DB0 队列/DB1 PubSub/DB2 黑名单)
                                                        → 本地文件存储 (storage/)
                       后台进程      → ARQ Worker（独立进程，PDF 转换任务）
```

> **进程说明**：PDF 转换完全由 ARQ Worker 异步执行（FastAPI 只入队、不转换）。
> Worker 必须与 API 同时运行，否则文件上传后永远卡在 converting、超时后被标记失败。

---

## 2. 环境要求

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 后端运行 |
| Node.js | 18+ | 前端构建 |
| MySQL | 8.0 | 数据库（需 InnoDB + 分区支持） |
| Redis | 6.x+ | 任务队列（DB0）/ PubSub 桥接（DB1）/ Token 黑名单（DB2） |
| LibreOffice | 7.x+ | Word/Excel 转 PDF（无头模式，**必装**，Worker 依赖） |
| Nginx | 1.20+ | 反向代理 + 静态文件服务 |

---

## 3. 环境变量

后端通过 `backend/.env` 文件配置。**推荐复制 `.env.example` 为 `.env` 后修改**：

```ini
# 应用
APP_NAME=企业流程审批系统
APP_VERSION=1.0.0
DEBUG=false
# 运行环境：生产必须设为 prod（触发生产守卫：DEBUG=true 拒启动 +
# SECRET_KEY 强密钥校验 + 关闭 Swagger 文档），本地开发用 development
ENV=prod

# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_strong_password
DB_NAME=workflow_approval

# JWT —— 生产必须替换为随机强密钥（用 openssl rand -hex 32 生成），
# 使用已知默认值会被生产守卫拒绝启动
SECRET_KEY=your-random-64-char-secret
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Redis（硬依赖）
REDIS_URL=redis://localhost:6379/0
REDIS_ARQ_DB=0
REDIS_PUBSUB_DB=1

# 默认密码（生产守卫必填，未配置拒启动）
# DEFAULT_USER_PASSWORD：管理员「重置密码」时把用户密码重置为该值
DEFAULT_USER_PASSWORD=your-user-default-password
# DEFAULT_ADMIN_PASSWORD：首次部署 python -m app.core.seed 创建 admin 时使用
DEFAULT_ADMIN_PASSWORD=your-admin-initial-password

# 文件存储（相对 backend/ 目录）
STORAGE_ROOT=storage
LIBREOFFICE_PATH=soffice

# 存储子目录（使用默认值无需配置）
# PROJECT_ARCHIVE_DIR=项目
# PROPOSAL_ARCHIVE_DIR=方案
# STORAGE_SIGNATURES_DIR=signatures
# STORAGE_DOCUMENT_TEMPLATES_DIR=document_templates

# 文件上传限制
# MAX_FILE_SIZE_MB=50
# ALLOWED_MIME_TYPES=...

# CORS —— 前端域名，逗号分隔
CORS_ORIGINS=http://your-domain.com
```

---

## 4. 生产部署步骤

### 4.1 部署后端

```bash
cd backend

# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate      # Linux

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 .env（复制 .env.example 并修改，见第 3 节）

# 4. 初始化数据库（建库 + 建表 + 操作日志分区 + alembic 基线，一条命令）
python -m app.core.deploy_db

# 5. 预置数据（幂等：角色 + 示例组织 + 系统配置 + 管理员 admin）
python -m app.core.seed

# 6. 启动服务 —— 两个进程，缺一不可
uvicorn app.main:app --host 0.0.0.0 --port 8000        # API（单进程）
python -m arq app.worker.WorkerSettings                # 后台 PDF 转换 Worker
```

> **单进程部署（生产口径，约 100 人同时在线）**：
> - API 用单进程（默认 `--workers 1`）。**不要**用 `--workers 4`——多进程下：
>   - 进程内 `asyncio.Lock`（PDF 签名并发锁）、`_pdf_locks` 失效
>   - WebSocket 连接注册在各自进程内，通知推送会连到错误 worker
>   - MySQL 连接数翻倍（40×4=160 超默认上限 151）
> - 单进程连接池默认 `pool_size=20 + max_overflow=20`，最多 40 连接，远低于 MySQL 上限。
>   如无特殊需要，无需调小连接池。
> - 生产环境用 systemd 托管这两个进程（见 4.4）。

### 4.2 部署前端

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 配置 API 地址（可选，同源部署可跳过）
# 构建时默认同源：API 请求 /api/*、WebSocket /api/v1/ws 由 Nginx 反代，
# 无需 VITE_API_BASE_URL / VITE_WS_URL。若前后端不同域才需配置：
# VITE_API_BASE_URL=http://your-domain.com/api/v1

# 3. 构建
npm run build

# 4. dist/ 目录部署到 Nginx 静态目录
cp -r dist/* /var/www/workflow/
```

### 4.3 Nginx 配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 文件上传大小限制（与系统的 50MB 匹配）
    client_max_body_size 55m;

    # 前端静态文件
    root /var/www/workflow;
    index index.html;

    # API 反向代理（含 WebSocket）
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（/api/v1/ws 在此 location 下，自动生效）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    # Vue Router History 模式回退
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 4.4 systemd 托管（推荐）

```ini
# /etc/systemd/system/workflow-api.service
[Unit]
Description=Workflow Approval API
After=network.target mysql.service redis-server.service
Wants=mysql.service redis-server.service

[Service]
WorkingDirectory=/opt/workflow/backend
EnvironmentFile=/opt/workflow/backend/.env
ExecStart=/opt/workflow/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
# 按需调整进程用户；需对 storage/、logs/ 目录有写权限
User=www-data

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/workflow-worker.service
[Unit]
Description=Workflow Approval ARQ Worker
After=network.target mysql.service redis-server.service
Wants=mysql.service redis-server.service

[Service]
WorkingDirectory=/opt/workflow/backend
EnvironmentFile=/opt/workflow/backend/.env
ExecStart=/opt/workflow/backend/venv/bin/python -m arq app.worker.WorkerSettings
Restart=always
RestartSec=5
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now workflow-api workflow-worker
sudo systemctl status workflow-api workflow-worker   # 查看运行状态
```

---

## 5. 数据库初始化

`python -m app.core.deploy_db` 完成建库、建表、分区、基线，`python -m app.core.seed` 预置数据，**无需手工执行 SQL**：

| 步骤 | 命令 | 说明 |
|------|------|------|
| 建库 | `python -m app.core.deploy_db` | CREATE DATABASE（utf8mb4）+ 全部表 + operation_logs 分区 + alembic stamp head |
| 预置 | `python -m app.core.seed` | roles（system_admin/manager/user）+ 4 示例组织 + 系统配置 + admin 用户（幂等） |

> **为什么不用 `alembic upgrade head` 建全新库**：迁移链首版（`cdc82f5bf321`）是「修正注释」的增量迁移，假设表已存在，无法在空库上重放。
> 因此全新部署用 `deploy_db.py`（create_all 建当前结构 + stamp head）。**已有库升级 schema 仍走 `alembic upgrade head`**。

---

## 6. LibreOffice 安装

```bash
# Ubuntu/Debian
sudo apt-get install -y libreoffice-common libreoffice-writer

# CentOS/RHEL 8+ / Fedora
sudo dnf install -y libreoffice

# 验证安装
soffice --headless --version
```

> 确保 `soffice` 命令在 PATH 中，或通过 `LIBREOFFICE_PATH` 指定完整路径。
> Worker 进程会以最多 4 并发调用 soffice 转换。

---

## 7. 存储目录

系统首次使用对应功能时自动创建以下目录：

```
backend/storage/
├── 项目/                       # 项目文件归档
│   └── {实例名称}/
│       ├── {uuid}.pdf
│       └── 文件夹A/             # 按 file_folders 配置预创建
├── 方案/                       # 方案文件归档
│   └── {实例名称}/
├── signatures/                 # 用户签名图片
└── document_templates/         # 文件模板（.docx/.xlsx）
```

**磁盘规划**：
- 归档文件持续增长，建议定期监控
- 签名图片很小（<500KB），可忽略
- 文件模板按组织数量线性增长
- 部署时确保运行用户（如 www-data）对 `backend/storage/`、`backend/logs/` 有写权限

---

## 8. 运维建议

### 8.1 监控

| 检查项 | 方式 | 频率 |
|--------|------|------|
| 服务存活 + 依赖探活 | `GET /api/v1/health`（DB/Redis 任一不可用返回 503） | 每分钟 |
| 磁盘使用率 | `df -h storage/` | 每天 |
| 数据库连接 | MySQL 连接数监控 | 持续 |
| Worker 状态 | `systemctl status workflow-worker` + 转换成功率 | 每天 |
| Redis 内存 | `redis-cli INFO memory` | 每天 |

### 8.2 备份策略

| 备份内容 | 方式 | 频率 |
|----------|------|------|
| MySQL 全库 | `mysqldump` 或 xtrabackup | 每日 |
| `storage/` 目录 | rsync 到备份服务器 | 每日 |
| `.env` 配置文件 | Git 版本控制 | 每次变更 |
| Nginx / systemd 配置 | Git 版本控制 | 每次变更 |

**恢复流程**：
1. 恢复 MySQL 备份
2. 恢复 `storage/` 目录
3. 重新部署应用代码
4. 验证 `GET /api/v1/health` 返回 200

> Redis 无需备份：Token 黑名单/密码版本号可重建（重启后旧登出 token 在自然过期前恢复有效，可接受），队列任务重启后丢失需重新上传文件。

### 8.3 性能参数

| 组件 | 参数 | 说明 |
|------|------|------|
| Uvicorn | 单进程（默认 workers=1） | 生产口径 100 人规模；多进程破坏 WS/锁一致性（见 4.1） |
| ARQ Worker | `max_jobs=4` | 对应 LibreOffice 并发 4，`job_timeout=150` 覆盖单次转换超时+重试 |
| LibreOffice | `asyncio.Semaphore(4)` | 最多 4 个并发转换进程（Worker 端） |
| 文件上传 | ≤50MB | 可配置，Nginx `client_max_body_size` 需同步调整 |
| MySQL 连接池 | `pool_size=20 + max_overflow=20` | 单进程最多 40 连接，远低于 MySQL 默认上限 151 |

### 8.4 安全清单

- [ ] `ENV=prod` 已设置（自动关闭 Swagger/OpenAPI 文档 + 生产守卫）
- [ ] `SECRET_KEY` 已替换为 `openssl rand -hex 32` 生成的随机密钥（≥32 字符）
- [ ] 数据库密码使用强密码
- [ ] `DEFAULT_USER_PASSWORD` / `DEFAULT_ADMIN_PASSWORD` 已设置且非弱密码
- [ ] 数据库限制来源 IP（bind-address / firewall）
- [ ] HTTPS 通过 Nginx 反向代理层 SSL 终端实现
- [ ] `CORS_ORIGINS` 仅包含实际前端域名
- [ ] 定期更新依赖：`pip list --outdated` / `npm outdated`
- [ ] 防火墙仅开放 80/443 端口，8000 和 3306 仅本地访问

### 8.5 日志

- 应用日志：`backend/logs/` 目录（按天滚动）
- Nginx 访问日志：`/var/log/nginx/access.log`
- Nginx 错误日志：`/var/log/nginx/error.log`
- MySQL 慢查询日志：建议开启，阈值 1 秒
- 操作日志：`operation_logs` 表（按年分区，只写不删）

### 8.6 分区维护

`operation_logs` 按年 RANGE 分区，由 `deploy_db.py` 在建库时创建（**当年起未来 10 年** + `p_future=MAXVALUE` 兜底），**10 年内无需人工维护**。

`p_future` 兜底保证即使 10 年后忘了加年份分区，新数据也能写入（进 p_future）。10 年后或 `p_future` 数据将满时再拆分：

```sql
-- 把 p_future 拆出新的一年分区（示例为 2036 年）
ALTER TABLE operation_logs
  REORGANIZE PARTITION p_future INTO (
    PARTITION p2036 VALUES LESS THAN (2037),
    PARTITION p_future VALUES LESS THAN MAXVALUE
  );
```

查看现有分区：
```sql
SELECT PARTITION_NAME, PARTITION_DESCRIPTION
FROM INFORMATION_SCHEMA.PARTITIONS
WHERE TABLE_NAME = 'operation_logs';
```

---

## 9. 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 全新库 `alembic upgrade head` 报 1146 表不存在 | 迁移链是增量迁移，不建主表 | 用 `python -m app.core.deploy_db` 初始化 |
| 文件上传后一直「转换中」→ 超时失败 | ARQ Worker 未启动 | 启动 `python -m arq app.worker.WorkerSettings` |
| 数据库注释乱码 | 建库字符集不是 utf8mb4 | 确认 `CHARACTER SET utf8mb4` + 连接 URL `charset=utf8mb4`，执行 `fix_charset_comments` 迁移 |
| LibreOffice 转换失败 | soffice 未安装或不在 PATH | `which soffice`，检查 `LIBREOFFICE_PATH` 配置 |
| WebSocket 连接失败 | Nginx 未配置 Upgrade 头 | 参考 4.3，确保 `proxy_http_version 1.1` + Upgrade 头 |
| Redis 连接失败 | Redis 未启动或 REDIS_URL 错误 | 启动 redis-server，检查 `.env` 中 REDIS_URL |
| 文件上传 413 | Nginx body size 限制 | 添加 `client_max_body_size 55m;` |
| 文件上传 422 | 文件格式不支持 | 检查文件是否在 `ALLOWED_MIME_TYPES` 列表中 |
| 429 限流 | 请求过于频繁 | 等待 60 秒后重试，或检查是否误触限流阈值 |
| CORS 错误 | CORS_ORIGINS 配置不正确 | 确认包含前端实际域名（含协议和端口） |
| Alembic 迁移冲突 | 多人同时生成迁移 | 确保迁移链连续，检查 `down_revision` 指向正确的父版本 |
