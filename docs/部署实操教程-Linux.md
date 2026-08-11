# 智展研究院设计开发管理系统 — Linux 部署实操教程（从零到上线）

> 面向不熟悉 Linux 的运维/开发，跟着每步照做即可，预计 1-2 小时。
> 目标系统：Ubuntu 22.04+ / Debian 12（命令基于 apt）。
> 本教程是「逐步实操」，速查版见 `04_Deployment.md`。
> 前置：需 root 权限（或 sudo）；公司服务器内网 IP；后端代码已可用（git 仓库或打包上传）。
>
> **按公司内网部署编写**：若内网服务器**无法访问公网**（连不上 GitHub / pip / npm 源），
> 代码获取与依赖安装需改用「打包 / 离线」方式（阶段 2、3、6 有标注）。系统软件安装（阶段 1）
> 需内网有 apt 源，或由 IT 用离线包安装。

---

## 0. 开始前准备

需要确认的信息（对应 `docs/部署环境确认清单.md`）：

| 项 | 你的值 | 用途 |
|----|--------|------|
| 服务器内网 IP | 例如 `192.168.1.50` | 浏览器访问入口、写入 .env 的 CORS |
| 服务器能否访问公网 | 能 / 不能 | 决定代码获取与依赖安装方式（阶段 2/3/6） |
| 一个强数据库密码 | 自己定 | MySQL 用户密码 |
| 一个强 SECRET_KEY | 见 3.2 生成 | JWT 加密密钥 |
| 管理员初始密码 | 自己定 | 首次登录 admin 用 |

> 确认网络：`ping baidu.com`（能通 = 可访问公网；不通 = 完全内网，走离线方式）

---

## 阶段 1：安装基础环境

> **先检查再装**：服务器若已装过（公司内网服务器常预装 MySQL/Nginx），版本满足就不重复装。逐项检查：

| 软件 | 检查命令 | 满足版本 | 说明 |
|------|---------|:--:|------|
| Python | `python3 --version` | 3.10+ | — |
| Node | `node --version` | 18+ | 仅前端构建用，可不在服务器 |
| MySQL | `mysql --version` | 8.0 | 版本低于 8 需升级 |
| Redis | `redis-cli ping` | 6.x+ | 返回 PONG 即正常 |
| LibreOffice | `soffice --headless --version` | 7.x+ | 无输出则未装 |
| Nginx | `nginx -v` | 1.20+ | — |

版本满足 → 跳过对应小节；没装 → 才 apt install；版本偏低 → 升级（若升级可能影响服务器上别的在用软件，先问 IT）。

### 1.1 更新系统

```bash
sudo apt update && sudo apt upgrade -y
```
预期：终端滚动更新完成，回到提示符。

### 1.2 安装 Python 3.10+（Ubuntu 22.04 自带 3.10）

```bash
sudo apt install -y python3 python3-venv python3-pip
python3 --version
```
预期输出：`Python 3.10.x`（3.10 以上均可）。

### 1.3 安装 Node.js 18+（前端构建用，仅部署时需要）

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
node --version && npm --version
```
预期输出：`v18.x` 和 `9.x`（或更高）。

### 1.4 安装 MySQL 8

```bash
sudo apt install -y mysql-server
sudo systemctl enable --now mysql
sudo mysql_secure_installation   # 交互式：设 root 密码、删除匿名用户、禁止远程 root
```
验证：
```bash
sudo mysqladmin -u root -p status
```
能输入密码并显示 `Uptime` 即成功。

**创建业务数据库用户**（教程用独立用户，不用 root 跑业务）：
```bash
sudo mysql
```
进入 MySQL 后执行（把 `你的强密码` 换成你自己的）：
```sql
CREATE USER 'workflow'@'localhost' IDENTIFIED BY '你的强密码';
GRANT ALL PRIVILEGES ON *.* TO 'workflow'@'localhost' WITH GRANT OPTION;
FLUSH PRIVILEGES;
EXIT;
```
> 说明：deploy_db 建库需要 CREATE 权限，故这里给了 `*.*`（内网环境可接受；若要更严，可按 04 文档只授 workflow_approval 相关库，但需手动先建库）。

### 1.5 安装 Redis

```bash
sudo apt install -y redis-server
sudo systemctl enable --now redis-server
redis-cli ping
```
预期输出：`PONG`（说明 Redis 正常）。

### 1.6 安装 LibreOffice（PDF 转换，必装）

```bash
sudo apt install -y libreoffice-writer libreoffice-calc libreoffice-common
soffice --headless --version
```
预期输出：`LibreOffice 7.x ...`。

### 1.7 安装 Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable --now nginx
```
验证：浏览器访问 `http://服务器IP` 出现 Nginx 欢迎页。

---

## 阶段 2：获取代码

二选一：

**方式 A：git 拉取**（若仓库可访问）
```bash
cd /opt && sudo mkdir -p workflow && sudo chown $USER:$USER workflow
cd workflow
git clone <你的仓库地址> .
```

**方式 B：打包上传**（**内网连不上 GitHub 时用这个**）
在开发机把项目打成 tar 上传：
```bash
tar czf workflow.tar.gz --exclude=frontend/node_modules --exclude=.git backend frontend
scp workflow.tar.gz 用户@服务器IP:/opt/workflow/
```
服务器上解压：
```bash
cd /opt/workflow && tar xzf workflow.tar.gz
```
> 内网无法访问公网仓库时，一律用方式 B（开发机打包 → scp 上传）。

---

## 阶段 3：后端环境与配置

### 3.1 虚拟环境 + 依赖

```bash
cd /opt/workflow/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
> 说明：`venv` 是独立 Python 环境，避免污染系统 Python。`requirements.txt` 已精确锁版本，保证生产与开发一致。

**内网无法访问公网 pip 时的离线安装**：
```bash
# 在有网开发机的 backend 目录提前下载全部依赖
pip download -r requirements.txt -d wheels/
# 把 wheels/ 目录一起打包上传到服务器
scp -r wheels/ 用户@服务器IP:/opt/workflow/backend/
# 服务器上离线安装（不联网）
pip install --no-index --find-links=wheels/ -r requirements.txt
```

### 3.2 配置 .env

```bash
cp .env.example .env
```
逐项确认（用 `vim .env` 或 `nano .env` 编辑）：
- `ENV=prod` —— 生产必须，触发安全守卫 + 关闭 Swagger
- `DB_PASSWORD` —— 改成 1.4 步设的 MySQL 密码
- `CORS_ORIGINS=http://服务器IP` —— 前端访问地址
- `DEFAULT_ADMIN_PASSWORD` / `DEFAULT_USER_PASSWORD` —— 改强密码
- `REDIS_URL=redis://localhost:6379/0` —— 默认即可

**生成 SECRET_KEY**：
```bash
openssl rand -hex 32
```
把输出复制粘贴到 `.env` 的 `SECRET_KEY=`。

> 验证 .env 是否正确：跑一下启动守卫，应正常通过
> ```bash
> python -c "from app.core.config import settings; print('ENV:', settings.ENV)"
> ```
> 预期输出：`ENV: prod`。

---

## 阶段 4：初始化数据库

### 4.1 建库 + 建表 + 分区 + 基线（一条命令）

```bash
python -m app.core.deploy_db
```
**预期输出**：
```
[deploy] 数据库已就绪: workflow_approval
[deploy] 全部数据表已创建（当前模型结构）
[deploy] operation_logs 已按年分区（2026 起未来 10 年 + p_future 兜底）
[deploy] alembic 基线已标记（stamp head）
[deploy] 建库完成。下一步执行: python -m app.core.seed
```
> 若这里报错：多半是 MySQL 连接问题（见附录 常见错误 #1）。

### 4.2 预置数据

```bash
python -m app.core.seed
```
**预期输出**：打印「角色/组织/配置/管理员」逐步 + 末尾「种子数据写入完成」。

### 4.3 验证数据

```bash
mysql -u workflow -p -e "USE workflow_approval; SHOW TABLES; SELECT code FROM roles;"
```
应看到 24 张表 + 3 个角色（system_admin/manager/user）。

---

## 阶段 5：启动后端（前台测试）

### 5.1 启动 API

```bash
cd /opt/workflow/backend && source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
**预期输出**：`Uvicorn running on http://0.0.0.0:8000`。

### 5.2 另开一个终端，启动 PDF 转换 Worker

```bash
cd /opt/workflow/backend && source venv/bin/activate
python -m arq app.worker.WorkerSettings
```
预期输出：`Starting worker ...` 等待任务。

### 5.3 验证健康检查

新开终端：
```bash
curl http://localhost:8000/api/v1/health
```
**预期输出**：`{"code":200,"message":"ok","data":{"status":"ok","version":"...","database":"ok","redis":"ok"}}`
（database/redis 都是 ok 才算通过）

> 此时可以先在前端配置好地址做一次联通测试，确认没问题再进阶段 6。

---

## 阶段 6：前端构建与部署

```bash
cd /opt/workflow/frontend
npm install
npm run build
```
预期输出：`✓ built in x.xs`，生成 `dist/` 目录。

部署到 Nginx 静态目录：
```bash
sudo mkdir -p /var/www/workflow
sudo cp -r dist/* /var/www/workflow/
```

**内网服务器无法 npm install 时（推荐）——在开发机构建好直接上传**：
```bash
# 在有网开发机 frontend 目录
npm install && npm run build
# 只把 dist/ 上传到服务器（服务器不需要 Node/npm）
tar czf dist.tar.gz dist/
scp dist.tar.gz 用户@服务器IP:/opt/workflow/
# 服务器上解压部署
cd /opt/workflow && tar xzf dist.tar.gz
sudo cp -r dist/* /var/www/workflow/
```

---

## 阶段 7：Nginx 配置

### 7.1 写入配置

```bash
sudo vim /etc/nginx/sites-available/workflow
```
粘贴（把 `server_name` 换成你的内网 IP 或域名）：
```nginx
server {
    listen 80;
    server_name 你的服务器IP;

    client_max_body_size 55m;   # 上传 50MB，留 5MB 余量

    root /var/www/workflow;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;                 # WebSocket 必需
        proxy_set_header Upgrade $http_upgrade; # WebSocket 必需
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 7.2 启用并测试

```bash
sudo ln -s /etc/nginx/sites-available/workflow /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default   # 移除默认站点（可选）
sudo nginx -t                                # 语法检查
sudo systemctl reload nginx
```
预期：`nginx -t` 输出 `syntax is ok / test is successful`。

### 7.3 验证

浏览器访问 `http://服务器IP` → 应出现登录页。
> 登录页能出来 = Nginx + 前端 OK。能登录 = 后端 + 数据库 OK。

---

## 阶段 8：systemd 托管（开机自启 + 崩溃重启）

### 8.1 后端 API 服务

```bash
sudo vim /etc/systemd/system/workflow-api.service
```
```ini
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
User=www-data

[Install]
WantedBy=multi-user.target
```
> 若 `www-data` 无后端目录权限，先 `sudo chown -R www-data:www-data /opt/workflow/backend/storage`。

### 8.2 PDF 转换 Worker 服务

```bash
sudo vim /etc/systemd/system/workflow-worker.service
```
```ini
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

### 8.3 启用

```bash
# 先停掉阶段 5 前台跑的进程（Ctrl+C）
sudo systemctl daemon-reload
sudo systemctl enable --now workflow-api workflow-worker
sudo systemctl status workflow-api workflow-worker
```
预期：两个服务都显示 `active (running)`。
> 注意：systemd 用的是 `EnvironmentFile` 加载 .env，与阶段 5 手动 `source` 方式等价。

### 8.4 验证重启自恢复

```bash
sudo systemctl restart workflow-api
sudo systemctl status workflow-api
```
应自动恢复 running。

---

## 阶段 9：完整验收清单

| # | 验证项 | 怎么做 | 预期 |
|---|--------|--------|------|
| 1 | 健康检查 | `curl localhost:8000/api/v1/health` | 200 + database/redis ok |
| 2 | Swagger 已关 | 访问 `/docs` | 404（ENV=prod 自动关闭） |
| 3 | 登录 | admin + 初始密码 | 进系统，提示强制改密 |
| 4 | 建组织/用户 | 系统管理 → 用户 | 可建，登录成功 |
| 5 | 设计流程 | 开工项目 → 设计器 | 能保存发布 |
| 6 | 发起实例 | 上传 Word 附件 | 转 PDF（worker 生效，不卡「转换中」） |
| 7 | 校验/审批/签名 | 走一遍 | 全通过，PDF 上签名 |
| 8 | 实时通知 | 侧边栏角标 | 待办数实时刷新（WebSocket 通） |
| 9 | 服务自恢复 | `sudo reboot` 后 | 两个服务自动起，health 正常 |
| 10 | 备份 | 见阶段 10 | 能恢复 |

---

## 阶段 10：日常运维

### 10.1 每日备份（cron 定时）

```bash
crontab -e
```
添加（每天凌晨 2 点备份数据库 + 归档文件）：
```
0 2 * * * mysqldump -u workflow -p'你的密码' workflow_approval | gzip > /backup/workflow_$(date +\%Y\%m\%d).sql.gz
0 3 * * * rsync -a /opt/workflow/backend/storage/ /backup/storage_$(date +\%Y\%m\%d)/ 2>/dev/null || true
```
先 `sudo mkdir -p /backup`。

### 10.2 查看日志

```bash
journalctl -u workflow-api -f        # 后端实时日志
journalctl -u workflow-worker -f     # worker 日志
tail -f /opt/workflow/backend/logs/app.log
```

### 10.3 升级数据库结构（代码更新后）

```bash
cd /opt/workflow/backend && source venv/bin/activate
alembic upgrade head
```
> 只跑新迁移，旧数据保留。建议低峰期执行（ALTER 有锁表窗口）。

### 10.4 常见故障排查

| 现象 | 排查 |
|------|------|
| 登录不了/502 | `curl localhost:8000/api/v1/health` 看后端是否活；`systemctl status workflow-api` |
| 上传卡「转换中」 | `systemctl status workflow-worker`；`soffice --headless --version` |
| 页面白屏/404 | 看 `/var/www/workflow` 是否是最新 dist；`try_files` 配置 |
| WebSocket 断 | Nginx `Upgrade` 头是否配了；`proxy_read_timeout` |
| 传文件报 413 | Nginx `client_max_body_size 55m` |
| 报 Redis 错 | `redis-cli ping`；`.env` 的 REDIS_URL |

---

## 附录：常见错误与解决

| # | 报错 | 原因 | 解决 |
|---|------|------|------|
| 1 | `deploy_db` 连接失败 / 1045 | MySQL 密码或用户错 | 核对 `.env` DB_PASSWORD；`mysql -u workflow -p` 手动连测试 |
| 2 | `pip install` 慢/失败 | 网络或依赖 | 换国内源：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| 3 | `npm install` 慢 | 网络 | 换镜像：`npm config set registry https://registry.npmmirror.com` |
| 4 | uvicorn 启动报 SECRET_KEY 错误 | 用了已知默认值 | 用 `openssl rand -hex 32` 生成替换 |
| 5 | 启动报 DEFAULT_USER_PASSWORD 未设置 | 生产守卫 | `.env` 补上（04 文档 3 节） |
| 6 | 前端登录页出来但登录 502 | 后端没起或 CORS 错 | `systemctl status workflow-api`；CORS_ORIGINS 是否含访问域名/IP |
| 7 | 转 PDF 失败日志见 soffice 错 | LibreOffice 未装或字体缺 | `soffice --headless --version`；`sudo apt install fonts-noto-cjk` 补中文字体 |
| 8 | 内网装依赖报「无法连接」 | 服务器无公网访问 | pip/npm 走阶段 3/6 离线方式；系统软件请 IT 提供内网 apt 源或离线包 |
