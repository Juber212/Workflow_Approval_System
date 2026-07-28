# 企业流程审批系统 — 部署与运维

> **版本**：2.0 | **更新**：2026-07-24

---

## 1. 部署架构

```
Browser → Nginx (:80) → /          → /var/www/workflow/ (Vue 3 静态文件)
                       → /api/*     → Uvicorn (:8000) → FastAPI
                       → /api/v1/ws → Uvicorn WebSocket
                                                       → MySQL (:3306)
                                                       → 本地文件存储 (storage/)
```

---

## 2. 环境要求

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 后端运行 |
| Node.js | 18+ | 前端构建 |
| MySQL | 8.0 | 数据库（需 InnoDB + 分区支持） |
| LibreOffice | 7.x+ | Word/Excel 转 PDF（无头模式） |
| Nginx | 1.20+ | 反向代理 + 静态文件服务 |

---

## 3. 环境变量

后端通过 `backend/.env` 文件配置：

```ini
# 应用
APP_NAME=企业流程审批系统
APP_VERSION=1.0.0
DEBUG=false

# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_strong_password
DB_NAME=workflow_approval

# JWT —— 生产环境务必修改为随机 64 字符以上
SECRET_KEY=replace-with-random-64-char-string
ACCESS_TOKEN_EXPIRE_MINUTES=480

# 文件存储（相对 backend/ 目录）
STORAGE_ROOT=storage
LIBREOFFICE_PATH=soffice

# 存储子目录（使用默认值无需配置）
# PROJECT_ARCHIVE_DIR=项目
# PROPOSAL_ARCHIVE_DIR=方案
# STORAGE_SIGNATURES_DIR=signatures
# STORAGE_DOCUMENT_TEMPLATES_DIR=document_templates

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

# 3. 配置 .env（参考上面）

# 4. 初始化数据库
mysql -u root -p -e "
  CREATE DATABASE IF NOT EXISTS workflow_approval
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"

# 5. 执行数据库迁移
alembic upgrade head

# 6. 预置角色（首次部署）
mysql -u root -p workflow_approval -e "
  INSERT INTO roles (name, code, description) VALUES
    ('系统管理员', 'system_admin', '系统维护者，不参与业务流程'),
    ('所长', 'manager', '组织管理者，负责流程设计与管理'),
    ('普通用户', 'user', '流程执行者与审批参与者');
"

# 7. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4.2 部署前端

```bash
cd frontend

# 1. 安装依赖
npm install

# 2. 配置 API 地址（.env.production）
# VITE_API_BASE_URL=http://your-domain.com/api/v1
# VITE_WS_URL=ws://your-domain.com/api/v1/ws

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

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
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

---

## 5. 数据库初始化

```sql
-- 创建数据库（首次部署）
CREATE DATABASE IF NOT EXISTS workflow_approval
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- 预置角色
INSERT INTO roles (name, code, description) VALUES
  ('系统管理员', 'system_admin', '系统维护者，不参与业务流程'),
  ('所长', 'manager', '组织管理者，负责流程设计与管理'),
  ('普通用户', 'user', '流程执行者与审批参与者');

-- 预置系统配置（可选，不配则使用代码默认值）
INSERT INTO system_configs (config_key, config_value, config_type, description) VALUES
  ('max_file_size_mb', '50', 'int', '文件上传大小限制（MB）'),
  ('access_token_expire_minutes', '480', 'int', 'Token 过期时间（分钟）'),
  ('pdf_signature_x', '400', 'float', '签名默认 X 坐标'),
  ('pdf_signature_y', '100', 'float', '签名默认 Y 坐标'),
  ('pdf_signature_offset', '150', 'int', '多签名 X 偏移量'),
  ('pdf_signature_page', '-1', 'int', '签名默认页码（-1=最后一页）'),
  ('pdf_signature_max_width', '100', 'int', '签名最大宽度'),
  ('pdf_signature_max_height', '26', 'int', '签名最大高度');
```

---

## 6. LibreOffice 安装

```bash
# Ubuntu/Debian
sudo apt-get install -y libreoffice-common libreoffice-writer

# CentOS/RHEL 7
sudo yum install -y libreoffice

# CentOS/RHEL 8+ / Fedora
sudo dnf install -y libreoffice

# Arch Linux
sudo pacman -S libreoffice-fresh

# 验证安装
soffice --headless --version
```

> 确保 `soffice` 命令在 PATH 中，或通过 `LIBREOFFICE_PATH` 指定完整路径。

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

---

## 8. 运维建议

### 8.1 监控

| 检查项 | 方式 | 频率 |
|--------|------|------|
| 服务存活 | `GET /api/v1/health` | 每分钟 |
| 磁盘使用率 | `df -h storage/` | 每天 |
| 数据库连接 | MySQL 连接数监控 | 持续 |
| LibreOffice | 转换成功率 | 每周 |

### 8.2 备份策略

| 备份内容 | 方式 | 频率 |
|----------|------|------|
| MySQL 全库 | `mysqldump` 或 xtrabackup | 每日 |
| `storage/` 目录 | rsync 到备份服务器 | 每日 |
| `.env` 配置文件 | Git 版本控制 | 每次变更 |
| Nginx 配置 | Git 版本控制 | 每次变更 |

**恢复流程**：
1. 恢复 MySQL 备份
2. 恢复 `storage/` 目录
3. 重新部署应用代码
4. 验证 `GET /api/v1/health`

### 8.3 性能参数

| 组件 | 参数 | 说明 |
|------|------|------|
| Uvicorn | `--workers 4` | Worker 数 ≈ CPU 核数 |
| LibreOffice | `asyncio.Semaphore(2)` | 最多 2 个并发转换进程 |
| 文件上传 | ≤50MB | 可配置，Nginx `client_max_body_size` 需同步调整 |
| MySQL 连接池 | SQLAlchemy 默认 | 可根据并发量调整 `pool_size` |

### 8.4 安全清单

- [ ] `SECRET_KEY` 已修改为随机强密码（≥64 字符）
- [ ] 数据库密码使用强密码
- [ ] 生产环境关闭 Swagger：`app = FastAPI(docs_url=None, redoc_url=None)`
- [ ] 数据库限制来源 IP（bind-address / firewall）
- [ ] HTTPS 通过 Nginx 反向代理层 SSL 终端实现
- [ ] CORS_ORIGINS 仅包含实际前端域名
- [ ] 定期更新依赖：`pip list --outdated` / `npm outdated`
- [ ] 防火墙仅开放 80/443 端口，8000 和 3306 仅本地访问

### 8.5 日志

- 应用日志：`backend/logs/` 目录（按天滚动）
- Nginx 访问日志：`/var/log/nginx/access.log`
- Nginx 错误日志：`/var/log/nginx/error.log`
- MySQL 慢查询日志：建议开启，阈值 1 秒
- 操作日志：`operation_logs` 表（按年分区，只写不删）

### 8.6 分区维护

`operation_logs` 按年 RANGE 分区，需定期添加未来年份分区：

```sql
-- 每年末执行一次，添加下一年的分区
ALTER TABLE operation_logs
  ADD PARTITION (PARTITION p2027 VALUES LESS THAN (2028));
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
| 数据库注释乱码 | 建库字符集不是 utf8mb4 | 确认 `CHARACTER SET utf8mb4` + 连接 URL `charset=utf8mb4`，执行 `fix_charset_comments` 迁移 |
| LibreOffice 转换失败 | soffice 未安装或不在 PATH | `which soffice`，检查 `LIBREOFFICE_PATH` 配置 |
| WebSocket 连接失败 | Nginx 未配置 Upgrade 头 | 参考上面 Nginx 配置，确保 `proxy_http_version 1.1` |
| 文件上传 413 | Nginx body size 限制 | 添加 `client_max_body_size 55m;`（比系统限制大 5MB 余量） |
| 文件上传 422 | 文件格式不支持 | 检查文件是否在 `ALLOWED_MIME_TYPES` 列表中 |
| 429 限流 | 请求过于频繁 | 等待 60 秒后重试，或检查是否误触限流阈值 |
| CORS 错误 | CORS_ORIGINS 配置不正确 | 确认包含前端实际域名（含协议和端口） |
| Alembic 迁移冲突 | 多人同时生成迁移 | 确保迁移链连续，检查 `down_revision` 指向正确的父版本 |
