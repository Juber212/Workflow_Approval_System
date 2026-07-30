# 企业微信通知集成 — 设计方案

> 版本 1.0 | 2026-07-29 | 待评审
>
> 目标：系统通知通过企业微信推送到用户手机，与现有 WebSocket 浏览器通知并行。

---

## 1. 目标与范围

### 1.1 现状

```
用户收到通知的途径：
  浏览器内 WebSocket 推送 → 侧边栏角标 + 个人中心 Tab 角标
  30 秒轮询兜底        → 同上
```

### 1.2 目标

```
用户收到通知的途径（新增）：
  企业微信应用消息 → 手机通知栏 + 企微消息卡片（可点击跳转回系统）
```

### 1.3 不在范围

- 不在企微内做审批操作（V1 只通知，不交互）
- 不在企微内做 OA 审批流程集成（那是另一套体系）
- 不替代现有的 WebSocket 浏览器通知（两者并行，互为补充）

---

## 2. 架构概览

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  业务触发点   │ ──→ │ WeworkNotifier│ ──→ │ 企微 API      │
│ (task/check  │     │ (新增模块)    │     │ /cgi-bin/    │
│  /approval/  │     │              │     │  message/send│
│  endorse)    │     │ 查 user.wx_  │     │              │
│              │     │ userid → 发送 │     │              │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                                                  ▼
                                          ┌──────────────┐
                                          │ 用户手机      │
                                          │ 企微通知栏    │
                                          └──────────────┘
```

- **触发点**：复用现有通知创建点（tasks/checks/approvals/endorsements 的创建和状态变更），不侵入现有业务逻辑
- **WechatNotifier**：新增一个独立 Python 模块，异步调用企微 API，发送失败不影响主流程
- **企微 API**：使用企微自建应用的 `/cgi-bin/message/send` 接口，支持 text 和 textcard 两种消息类型

---

## 3. 企微应用配置

### 3.1 前提条件

需要企业微信管理员完成以下操作（一次性配置）：

1. 登录[企业微信管理后台](https://work.weixin.qq.com/)
2. 创建自建应用：「应用管理」→「自建」→「创建应用」
3. 获取凭证：
   - `corpid`：企业 ID（「我的企业」→ 企业信息）
   - `corpsecret`：应用 Secret（应用详情页）
   - `agentid`：应用 ID（应用详情页）
4. 配置可信域名：应用详情 → 网页授权及 JS-SDK → 设置系统域名
5. 设置应用可见范围：选择需要接收通知的部门或人员

### 3.2 系统配置项

在系统管理的「系统配置」中新增：

| 配置键 | 说明 | 示例值 |
|--------|------|--------|
| `wework_corpid` | 企业 ID | `ww1234567890abcdef` |
| `wework_corpsecret` | 应用 Secret | `abcdef...` |
| `wework_agentid` | 应用 ID | `1000002` |
| `wework_enabled` | 是否启用企微通知 | `true` / `false` |

> `wework_enabled = false` 时整个模块静默跳过，不影响现有通知逻辑。

---

## 4. 用户绑定（关键设计）

### 4.1 问题

企微的 `touser` 参数是 `userid`（如 `zhangsan`），而系统用户表用 `id`（自增数字）。需要建立映射关系。

### 4.2 方案：users 表加字段

```sql
ALTER TABLE users ADD COLUMN wx_userid VARCHAR(64) NULL COMMENT '企业微信 UserID';
```

### 4.3 绑定流程

**方式一：管理员手动绑定（V1 推荐）**

1. 管理员在「用户管理」编辑用户时，可填写「企业微信 UserID」
2. 一个系统用户对应一个企微账号

**方式二：用户自行绑定（V2）**

1. 用户在「个人信息」页面输入企微 UserID
2. 系统向该 UserID 发送一条验证消息
3. 用户确认后完成绑定

**方式三：手机号自动匹配（V2）**

1. 企微通讯录同步到系统（调用企微通讯录 API）
2. 按手机号自动匹配 `users.phone ↔ 企微通讯录.mobile`
3. 匹配成功自动写入 `wx_userid`

> V1 推荐手动绑定，V2 再做通讯录同步和用户自助绑定以降低首次实施复杂度。

### 4.4 数据结构

```python
# models/user.py 新增字段
wx_userid: Mapped[str | None] = mapped_column(
    String(64), nullable=True, comment="企业微信 UserID"
)
```

```python
# schemas/user.py UserUpdate 新增
wx_userid: str | None = Field(None, max_length=64)
```

---

## 5. 消息通知模块

### 5.1 核心类

```python
# services/wework_notifier.py

class WechatNotifier:
    """企业微信消息通知器 —— 单例，启动时初始化 access_token 缓存"""

    def __init__(self, corpid, corpsecret, agentid):
        self._corpid = corpid
        self._corpsecret = corpsecret
        self._agentid = agentid
        self._token: str | None = None
        self._token_expires_at: float = 0

    async def _get_access_token(self) -> str:
        """获取并缓存 access_token（有效期 7200 秒，提前 5 分钟刷新）"""

    async def send_text(self, userid: str, content: str) -> bool:
        """发送纯文本消息"""

    async def send_card(self, userid: str, title: str,
                        description: str, url: str, btntxt: str = "查看详情") -> bool:
        """发送卡片消息（可点击跳转）"""
```

### 5.2 消息类型选择

| 通知场景 | 消息类型 | 理由 |
|---------|---------|------|
| 新任务 | `textcard` 卡片 | 需要"查看详情"跳转到任务处理页 |
| 新校验 | `textcard` 卡片 | 同上 |
| 新审批 | `textcard` 卡片 | 同上 |
| 新批准 | `textcard` 卡片 | 同上 |
| 驳回通知 | `textcard` 卡片 | 需要提示修订后重新提交 |
| 逾期提醒 | `text` 文本 | 简单提醒，无需跳转 |

### 5.3 消息模板

```python
# 卡片消息示例
{
    "touser": "zhangsan",
    "msgtype": "textcard",
    "agentid": 1000002,
    "textcard": {
        "title": "🔔 新的审批待办",
        "description": (
            "<div class='normal'>"
            "<div class='highlight'>XX 设计图纸审核</div>"
            "<div>节点：校对</div>"
            "<div>优先级：<span style='color:red'>紧急</span></div>"
            "<div>截止时间：2026-08-01</div>"
            "</div>"
        ),
        "url": "https://your-domain.com/profile/approval/123",
        "btntxt": "查看详情"
    }
}
```

### 5.4 跳转 URL 生成

卡片的 `url` 指向系统前端页面，根据通知类型拼装：

| 通知类型 | URL 格式 | 参数来源 |
|---------|---------|---------|
| 任务 | `/profile/task/{task_id}` | `task.id` |
| 校验 | `/profile/check/{check_id}` | `check_record.id` |
| 审批 | `/profile/approval/{approval_id}` | `approval.id` |
| 批准 | `/profile/endorsement/{endorsement_id}` | `endorsement.id` |

> 基础域名从新的系统配置项 `site_base_url` 读取（如 `https://oa.example.com`），由管理员在系统配置中设置。

### 5.5 调用时机

所有企微消息发送均为**异步非阻塞**——在现有通知创建之后 fire-and-forget：

```python
# 示例：审批服务中创建审批记录后
approval = await create_approval_record(...)
await create_notification(...)  # 现有：浏览器通知

# 新增：企微通知（异步，失败不影响主流程）
background_tasks.add_task(
    wework_notifier.send_approval_pending, approval, instance, node
)
```

> 企微发送失败时记录 WARNING 日志，不抛异常、不回滚业务。

---

## 6. 前端调整

### 6.1 用户管理表单

「新增/编辑用户」弹窗中加一个字段：

```
企业微信 UserID：[________] （选填）
```

位于手机号下方，管理员手动填写。

### 6.2 个人信息页

用户可以在右上角头像 →「个人信息」中看到自己的企业微信绑定状态：

```
企业微信绑定：已绑定（zhangsan） / 未绑定
```

> V1 只显示绑定状态（不可自助修改），V2 加自助绑定和解绑功能。

---

## 7. 实施计划

### Phase 1：基础设施（1-2 天）

| 任务 | 内容 |
|------|------|
| 1.1 | 系统配置表加 4 个企微配置项（corpid/corpsecret/agentid/enabled） |
| 1.2 | `users` 表加 `wx_userid` 字段 + Alembic 迁移 |
| 1.3 | `UserUpdate` schema + 前端用户管理表单 + 个人信息页展示 |

### Phase 2：消息模块（1-2 天）

| 任务 | 内容 |
|------|------|
| 2.1 | `wework_notifier.py`：access_token 缓存 + `send_text` + `send_card` |
| 2.2 | 5 类消息模板（task/check/approval/endorsement/reject） |
| 2.3 | 配置项 `site_base_url`（卡片跳转域名） |

### Phase 3：对接业务触发点（1 天）

| 任务 | 内容 |
|------|------|
| 3.1 | `task_service.submit_task` 后加企微通知（校验人收到新校验） |
| 3.2 | `check_service.pass_check` 后加企微通知（审批人收到新审批） |
| 3.3 | `approval_service.approve` / `reject` 后加企微通知 |
| 3.4 | `endorsement_service.endorse_approve` 后加企微通知 |
| 3.5 | 各触发点包在 `if wework_enabled` 内 + try/except 兜底 |

### Phase 4：测试与上线（1 天）

| 任务 | 内容 |
|------|------|
| 4.1 | Mock 企微 API 的单元测试 |
| 4.2 | 企微沙箱环境联调 |
| 4.3 | 文档更新（本设计文档 + 用户手册补企微通知章节） |

---

## 8. 安全与风险

| 风险 | 缓解措施 |
|------|---------|
| `corpsecret` 泄露 | 存数据库不存代码，管理员可随时轮换 |
| 消息发错人 | `wx_userid` 由管理员手动维护，V1 不做自动匹配 |
| 企微 API 故障 | 异步发送 + try/except，不影响业务流程 |
| access_token 过期 | 缓存 + 提前 5 分钟刷新，每次调 API 前自动检查 |
| 频率限制 | 正常审批量远低于企微 API 限制（单应用每分钟 2000 次） |

---

## 9. 待确认事项

1. **企微管理员权限**：谁有权限创建自建应用、获取 corpid/corpsecret？
2. **用户绑定方式**：V1 用管理员手动绑定，是否接受？
3. **消息文案**：卡片标题和描述文案是否通过（5.3 节模板）？
4. **是否需要群聊通知**：除了个人通知，是否需要在企微群聊里发流程进展（如某个项目所有节点完成）？
