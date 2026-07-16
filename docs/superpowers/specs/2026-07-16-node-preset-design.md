# 节点预设功能 — 设计文档

> 2026-07-16 | 状态：待用户审阅

---

## 一、背景与问题

### 现状

流程设计器左侧"节点库"面板（`NodePanel.vue`）中只有一个硬编码的空白"工作节点"卡片。用户每次设计流程时，需要逐个手动配置每个节点的负责人、校验人、审批人、时限等字段。如果多个流程模板中反复出现相同节点配置（例如"财务审批：张三 + 李四校验 + 王五审批 + 3天"），每次都要重新输入。

### 目标

让用户把常用节点配置保存为**个人预设**，设计流程时从节点库拖出即用，无需重复配置。

---

## 二、范围与边界

### 包含

- 个人级节点预设 CRUD
- 从画布已配置节点"保存为预设"
- 从预设编辑弹窗新建/编辑
- 拖出预设节点到画布（所有配置预填）
- 预设引用人员失效时的 toast 提示

### 不包含

- 组织级共享预设（留待后续）
- 预设拖拽排序（sort_order 字段预留，UI 不做）
- 预设分类/标签
- 预设中人员的自动同步（预设保存的是快照）

---

## 三、数据模型

### 新表 `node_presets`

```sql
CREATE TABLE node_presets (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    user_id         INT          NOT NULL COMMENT '所属用户',
    name            VARCHAR(30)  NOT NULL COMMENT '预设名称（在列表中显示）',
    node_name       VARCHAR(30)  NOT NULL COMMENT '拖出后的默认节点名称',
    assignee_id     INT          NULL     COMMENT '负责人 ID',
    checkers        JSON         NULL     COMMENT '校验人列表 [{"user_id": N}]',
    approvers       JSON         NULL     COMMENT '审批人列表 [{"user_id": N}]',
    time_limit_days INT          NULL     COMMENT '完成时限（天）',
    require_file    BOOLEAN      NOT NULL DEFAULT FALSE COMMENT '是否必须上传文件',
    sort_order      INT          NOT NULL DEFAULT 0 COMMENT '排序序号（预留）',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_user_id (user_id),
    CONSTRAINT fk_preset_user FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 设计要点

- 人员存 **ID 快照**，不跟随用户表变更。失效检测由前端在拖出时比对。
- `name` 是预设名称（如"财务审批模板"），`node_name` 是拖到画布后节点的 `name` 属性（如"财务审批"），两者可相同也可不同。
- `sort_order` 字段预留未来拖拽排序，当前版本不暴露 UI。

---

## 四、API 设计

### 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/node-presets` | 获取当前用户的预设列表 |
| POST | `/api/v1/node-presets` | 创建预设 |
| PUT | `/api/v1/node-presets/{id}` | 更新预设 |
| DELETE | `/api/v1/node-presets/{id}` | 删除预设 |

### 请求/响应

#### POST / PUT Body

```json
{
  "name": "财务审批模板",
  "node_name": "财务审批",
  "assignee_id": 3,
  "checkers": [{"user_id": 5}],
  "approvers": [{"user_id": 7}],
  "time_limit_days": 3,
  "require_file": true
}
```

#### GET Response

```json
{
  "items": [
    {
      "id": 1,
      "name": "财务审批模板",
      "node_name": "财务审批",
      "assignee_id": 3,
      "assignee_name": "张三",
      "checkers": [{"user_id": 5}],
      "checkers_names": ["李四"],
      "approvers": [{"user_id": 7}],
      "approvers_names": ["王五"],
      "time_limit_days": 3,
      "require_file": true,
      "sort_order": 0,
      "created_at": "2026-07-16T10:00:00"
    }
  ],
  "total": 1
}
```

> 列表接口附带 `*_names` 字段，方便面板直接渲染；`_names` 仅用于展示，不参与保存。

### 权限

- 仅已登录用户可访问（`get_current_active_user`）
- PUT/DELETE 校验 `user_id == current_user.id`，防止跨用户修改

---

## 五、前端设计

### 5.1 NodePanel.vue 改造

**改造点：**

1. 基础"工作节点"卡片保留，置顶显示，样式与预设卡片一致但使用褪色边框以区分
2. 预设列表从 `GET /api/v1/node-presets` 获取，动态渲染在基础卡片下方
3. 预设卡片 hover 时右上角浮动编辑(✏️)和删除(🗑️)小图标
4. 底部"新建预设"按钮（`+ 新建预设`），点击打开 PresetEditor 弹窗
5. 预设卡片点击 → 调用 `addWorkNode()` 并传入预设 properties
6. 预设卡片拖拽 → DnD 时传入预设 properties

**预设卡片模板：**

```html
<div class="preset-card" @click="emit('add', preset)" draggable="true" @dragstart="startDnD($event, preset)">
  <div class="preset-card__header">
    <span class="preset-card__name">💾 {{ preset.name }}</span>
    <span class="preset-card__actions" v-show="hovered === preset.id">
      <el-icon @click.stop="editPreset(preset)"><Edit /></el-icon>
      <el-icon @click.stop="deletePreset(preset)" style="margin-left:4px"><Delete /></el-icon>
    </span>
  </div>
  <div class="preset-card__meta">
    {{ preset.assignee_name || '未设负责人' }} · {{ preset.time_limit_days || '不限' }}天
  </div>
</div>
```

### 5.2 PresetEditor.vue（新建）

`el-dialog` 弹窗，字段与 PropertyPanel 一致：

| 字段 | 组件 | 说明 |
|------|------|------|
| 预设名称 | `el-input` max 30 | 列表显示用 |
| 节点名称 | `el-input` max 30 | 拖出后节点 name |
| 负责人 | `UserSelector` 单选 | |
| 校验人 | `UserSelector` 多选 | 至少 1 人 |
| 审批人 | `UserSelector` 多选 | 至少 1 人 |
| 时限 | `el-input-number` 1-365 | |
| 需文件 | `el-switch` | |

Props：
- `modelValue: boolean` — 控制弹窗显隐
- `initial?: PresetFormData` — 编辑时传入已有数据

Emits：
- `update:modelValue`
- `saved` — 保存成功后通知父组件刷新列表

### 5.3 PropertyPanel.vue 加按钮

右上角 header 区域新增"保存为预设"按钮：

```
节点配置       [💾 保存为预设]  ← 仅在选中工作节点且已配置时显示
```

点击 → emit `save-as-preset` 到 FlowDesigner → 打开 PresetEditor（预填当前节点数据）。

### 5.4 FlowCanvas.vue —— addWorkNode 扩展

```typescript
// 改前
function addWorkNode(x?: number, y?: number)

// 改后
function addWorkNode(x?: number, y?: number, presetProperties?: Partial<WorkNodeProperties>)
```

合并逻辑：presetProperties 覆盖默认值。人员 name 字段（`assignee_name`、`checkers_names`、`approvers_names`）由预设的 `*_names` 直接带入。

### 5.5 人员失效检测

拖出节点时（`addWorkNode` 内），对预设中的 `assignee_id`、`checkers` 中每个 `user_id`、`approvers` 中每个 `user_id`，检查是否存在于当前 UserSelector 用户列表中。

缺失的人员字段置空，`toast.warning("预设「{name}」中的人员「{user_name}」已不可用，请重新选择")`。

检测逻辑封装为 `validatePresetUsers(preset)` 工具函数。

---

## 六、文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/models/node_preset.py` | **新建** | SQLAlchemy 模型 |
| `backend/app/schemas/preset.py` | **新建** | Pydantic Schema |
| `backend/app/api/presets.py` | **新建** | FastAPI 路由 |
| `backend/app/services/preset_service.py` | **新建** | 业务逻辑（CRUD + 人员姓名填充） |
| `backend/alembic/versions/xxx_add_node_presets.py` | **新建** | 迁移 |
| `backend/app/models/__init__.py` | 修改 | 注册 NodePreset 模型 |
| `frontend/src/api/presets.ts` | **新建** | 前端 API 封装 |
| `frontend/src/views/flows/designer/PresetEditor.vue` | **新建** | 预设编辑弹窗 |
| `frontend/src/views/flows/designer/NodePanel.vue` | 修改 | 动态预设列表 + 管理操作 |
| `frontend/src/views/flows/designer/PropertyPanel.vue` | 修改 | 新增"保存为预设"按钮 |
| `frontend/src/views/flows/designer/FlowCanvas.vue` | 修改 | addWorkNode 支持预设参数 + 失效检测 |
| `frontend/src/views/flows/FlowDesigner.vue` | 修改 | 组合 PresetEditor + 事件透传 |

---

## 七、边界与异常处理

| 场景 | 处理 |
|------|------|
| 预设数量过多（>50） | 面板内滚动，不做虚拟化（50 个以内 DOM 可承受） |
| 预设中人员已被管理员删除 | toast 提示，对应字段置空，其他正常填充 |
| 删除预设时有确认 | `ElMessageBox.confirm` 二次确认 |
| 编辑预设时取消 | 弹窗关闭，不保存 |
| 并发创建同名预设 | 允许，不做唯一约束（用户自己区分） |
| 保存为预设时节点未配置 | 按钮置灰，tooltip 提示"请先完成节点配置" |

---

## 八、不影响现有功能

- 基础工作节点卡片保留，点击/拖拽行为不变
- FlowCanvas 的 `addWorkNode()` 向后兼容，不传预设参数时与原来完全一致
- PropertyPanel 的配置逻辑不受影响，仅增加一个按钮
- 后端不修改任何现有表
