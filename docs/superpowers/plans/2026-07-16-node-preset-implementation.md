# 节点预设功能 — 实现计划

> **For agentic workers:** 按任务顺序执行，每步使用 checkbox (`- [ ]`) 跟踪进度。

**目标：** 让用户把常用节点配置保存为个人预设，设计流程时从节点库拖出即用

**架构：** 后端新建 `node_presets` 表 + 4 个 CRUD 端点；前端新建 PresetEditor 组件 + 改造 NodePanel/PropertyPanel/FlowCanvas/FlowDesigner

**技术栈：** FastAPI + SQLAlchemy 2.0 + Vue 3 + Element Plus + LogicFlow

## 全局约束

- 仅已登录用户可操作预设 API
- PUT/DELETE 校验 `user_id == current_user.id`
- 不修改现有数据库表结构
- 不破坏现有流程设计器功能
- 预设中人员存储 ID 快照，拖出时前端检测失效人员
- 所有关键代码添加中文注释

---

### Task 1: 后端 —— 数据模型 + 迁移

**文件：**
- 创建: `backend/app/models/node_preset.py`
- 创建: `backend/alembic/versions/2026_07_16_add_node_presets.py`
- 修改: `backend/app/models/__init__.py`

**接口：**
- 产出: `NodePreset` SQLAlchemy 模型，表名 `node_presets`

- [ ] **Step 1: 创建 NodePreset 模型**

```python
# backend/app/models/node_preset.py
"""节点预设模型 —— 用户保存常用节点配置以便复用"""

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class NodePreset(Base):
    __tablename__ = "node_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="所属用户")
    name: Mapped[str] = mapped_column(String(30), nullable=False, comment="预设名称（列表中显示）")
    node_name: Mapped[str] = mapped_column(String(30), nullable=False, comment="拖出后默认节点名称")
    assignee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), comment="负责人 ID")
    checkers: Mapped[dict | None] = mapped_column(JSON, comment="校验人列表 [{\"user_id\": N}]")
    approvers: Mapped[dict | None] = mapped_column(JSON, comment="审批人列表 [{\"user_id\": N}]")
    time_limit_days: Mapped[int | None] = mapped_column(Integer, comment="完成时限（天）")
    require_file: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否必须上传文件")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序序号（预留拖拽排序）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
```

- [ ] **Step 2: 注册模型到 `__init__.py`**

在 `backend/app/models/__init__.py` 中添加：

```python
from app.models.node_preset import NodePreset
```

并在 `__all__` 列表末尾加上 `"NodePreset"`。

- [ ] **Step 3: 创建 Alembic 迁移**

运行命令生成迁移：

```bash
cd backend && alembic revision --autogenerate -m "add node_presets"
```

确认生成的迁移文件内容包含 `create_table` 操作。

- [ ] **Step 4: 运行迁移验证**

```bash
cd backend && alembic upgrade head
```

预期：`node_presets` 表创建成功，`mysql> DESCRIBE node_presets;` 显示 11 列。

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/node_preset.py backend/app/models/__init__.py backend/alembic/versions/*add_node_presets*
git commit -m "feat: 新建 node_presets 模型与迁移"
```

---

### Task 2: 后端 —— Schema

**文件：**
- 创建: `backend/app/schemas/preset.py`

**接口：**
- 消耗: `NodePreset` 模型
- 产出: `PresetCreate`, `PresetUpdate`, `PresetResponse`, `PresetListResponse` Pydantic 模型

- [ ] **Step 1: 创建 Schema 文件**

```python
# backend/app/schemas/preset.py
"""节点预设 Schema —— 请求/响应模型"""

from datetime import datetime
from pydantic import BaseModel, Field


class PresetCreate(BaseModel):
    """创建预设请求"""
    name: str = Field(..., min_length=1, max_length=30, description="预设名称")
    node_name: str = Field(..., min_length=1, max_length=30, description="拖出后的默认节点名称")
    assignee_id: int | None = Field(None, description="负责人 ID")
    checkers: list[dict] | None = Field(None, description="校验人列表 [{\"user_id\": N}]")
    approvers: list[dict] | None = Field(None, description="审批人列表 [{\"user_id\": N}]")
    time_limit_days: int | None = Field(None, description="完成时限（天）")
    require_file: bool = Field(False, description="是否必须上传文件")


class PresetUpdate(BaseModel):
    """更新预设请求 —— 所有字段选填"""
    name: str | None = Field(None, min_length=1, max_length=30, description="预设名称")
    node_name: str | None = Field(None, min_length=1, max_length=30, description="拖出后的默认节点名称")
    assignee_id: int | None = Field(None, description="负责人 ID")
    checkers: list[dict] | None = Field(None, description="校验人列表")
    approvers: list[dict] | None = Field(None, description="审批人列表")
    time_limit_days: int | None = Field(None, description="完成时限（天）")
    require_file: bool | None = Field(None, description="是否必须上传文件")


class PresetResponse(BaseModel):
    """预设响应（单条）"""
    id: int
    name: str
    node_name: str
    assignee_id: int | None = None
    assignee_name: str | None = None
    checkers: list[dict] | None = None
    checkers_names: list[str] | None = None
    approvers: list[dict] | None = None
    approvers_names: list[str] | None = None
    time_limit_days: int | None = None
    require_file: bool = False
    sort_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PresetListResponse(BaseModel):
    """预设列表响应"""
    items: list[PresetResponse]
    total: int
```

- [ ] **Step 2: 验证语法**

```bash
cd backend && python -c "from app.schemas.preset import PresetCreate, PresetUpdate, PresetResponse, PresetListResponse; print('OK')"
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/schemas/preset.py
git commit -m "feat: 新增节点预设 Schema"
```

---

### Task 3: 后端 —— Service 层

**文件：**
- 创建: `backend/app/services/preset_service.py`

**接口：**
- 消耗: `AsyncSession`, `CurrentUser`, `PresetCreate`, `PresetUpdate`
- 产出: `create_preset()`, `list_presets()`, `update_preset()`, `delete_preset()` 异步函数

- [ ] **Step 1: 创建 Service 文件**

```python
# backend/app/services/preset_service.py
"""节点预设服务 —— CRUD + 人员姓名填充"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.node_preset import NodePreset
from app.models.user import User
from app.schemas.preset import PresetCreate, PresetUpdate, PresetResponse, PresetListResponse
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode


async def list_presets(db: AsyncSession, user_id: int) -> PresetListResponse:
    """获取当前用户的预设列表（按 sort_order + 创建时间排序）"""
    count_stmt = select(func.count()).select_from(NodePreset).where(NodePreset.user_id == user_id)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(NodePreset)
        .where(NodePreset.user_id == user_id)
        .order_by(NodePreset.sort_order, NodePreset.created_at.desc())
    )
    result = await db.execute(stmt)
    presets = result.scalars().all()

    # 批量收集所有 user_id，一次性查询姓名
    name_map = await _batch_resolve_names(db, presets)

    items = [PresetResponse(**_preset_to_response(p, name_map)) for p in presets]
    return PresetListResponse(items=items, total=total)


async def create_preset(db: AsyncSession, data: PresetCreate, user_id: int) -> PresetResponse:
    """创建预设"""
    preset = NodePreset(
        user_id=user_id,
        name=data.name,
        node_name=data.node_name,
        assignee_id=data.assignee_id,
        checkers=data.checkers,
        approvers=data.approvers,
        time_limit_days=data.time_limit_days,
        require_file=data.require_file,
    )
    db.add(preset)
    await db.flush()
    return await _preset_to_response_async(db, preset)


async def update_preset(db: AsyncSession, preset_id: int, data: PresetUpdate, user_id: int) -> PresetResponse:
    """更新预设 —— 仅所有者可修改"""
    preset = await _get_owned_preset(db, preset_id, user_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(preset, key, val)
    await db.flush()
    return await _preset_to_response_async(db, preset)


async def delete_preset(db: AsyncSession, preset_id: int, user_id: int) -> None:
    """删除预设 —— 仅所有者可删除"""
    preset = await _get_owned_preset(db, preset_id, user_id)
    await db.delete(preset)


async def _get_owned_preset(db: AsyncSession, preset_id: int, user_id: int) -> NodePreset:
    """获取预设并校验所有权"""
    stmt = select(NodePreset).where(NodePreset.id == preset_id)
    result = await db.execute(stmt)
    preset = result.scalar_one_or_none()
    if not preset:
        raise AppException(ErrorCode.NOT_FOUND, "预设不存在")
    if preset.user_id != user_id:
        raise AppException(ErrorCode.FORBIDDEN, "无权操作此预设")
    return preset


async def _preset_to_response_async(db: AsyncSession, preset: NodePreset) -> PresetResponse:
    """异步版：模型 → 响应（填充人员姓名）—— 用于创建/更新后返回单条"""
    name_map = await _batch_resolve_names(db, [preset])
    return _build_preset_response(preset, name_map)


async def _batch_resolve_names(db: AsyncSession, presets: list[NodePreset]) -> dict[int, str]:
    """批量查询预设中所有引用用户的姓名"""
    user_ids: set[int] = set()
    for preset in presets:
        if preset.assignee_id:
            user_ids.add(preset.assignee_id)
        for item in (preset.checkers or []):
            if isinstance(item, dict) and "user_id" in item:
                user_ids.add(item["user_id"])
        for item in (preset.approvers or []):
            if isinstance(item, dict) and "user_id" in item:
                user_ids.add(item["user_id"])

    name_map: dict[int, str] = {}
    if user_ids:
        user_stmt = select(User.id, User.real_name).where(User.id.in_(user_ids))
        user_result = await db.execute(user_stmt)
        for uid, name in user_result:
            name_map[uid] = name
    return name_map


def _preset_to_response(preset: NodePreset, name_map: dict[int, str] | None = None) -> dict:
    """同步版：模型 → dict（用于列表批量转换，避免每个 preset 都查一次）"""
    return {
        "id": preset.id,
        "name": preset.name,
        "node_name": preset.node_name,
        "assignee_id": preset.assignee_id,
        "assignee_name": name_map.get(preset.assignee_id) if name_map and preset.assignee_id else None,
        "checkers": preset.checkers,
        "checkers_names": _extract_names(preset.checkers, name_map) if name_map else None,
        "approvers": preset.approvers,
        "approvers_names": _extract_names(preset.approvers, name_map) if name_map else None,
        "time_limit_days": preset.time_limit_days,
        "require_file": preset.require_file,
        "sort_order": preset.sort_order,
        "created_at": preset.created_at.isoformat() if preset.created_at else None,
        "updated_at": preset.updated_at.isoformat() if preset.updated_at else None,
    }


def _build_preset_response(preset: NodePreset, name_map: dict[int, str]) -> PresetResponse:
    """构建 PresetResponse（含姓名）"""
    return PresetResponse(
        id=preset.id,
        name=preset.name,
        node_name=preset.node_name,
        assignee_id=preset.assignee_id,
        assignee_name=name_map.get(preset.assignee_id) if preset.assignee_id else None,
        checkers=preset.checkers,
        checkers_names=_extract_names(preset.checkers, name_map),
        approvers=preset.approvers,
        approvers_names=_extract_names(preset.approvers, name_map),
        time_limit_days=preset.time_limit_days,
        require_file=preset.require_file,
        sort_order=preset.sort_order,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


def _extract_names(items: list[dict] | None, name_map: dict[int, str]) -> list[str]:
    """从 [{\"user_id\": N}] 列表提取姓名"""
    if not items:
        return []
    names = []
    for item in items:
        if isinstance(item, dict) and "user_id" in item:
            name = name_map.get(item["user_id"])
            if name:
                names.append(name)
    return names
```

- [ ] **Step 2: 验证语法**

```bash
cd backend && python -c "from app.services.preset_service import list_presets, create_preset, update_preset, delete_preset; print('OK')"
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/preset_service.py
git commit -m "feat: 新增节点预设 Service 层"
```

---

### Task 4: 后端 —— API 路由

**文件：**
- 创建: `backend/app/api/presets.py`

**接口：**
- 消耗: `preset_service` 层函数, `get_current_active_user`, `get_db`
- 产出: 4 个 REST 端点注册到 `prefix="/api/v1"`

- [ ] **Step 1: 创建 API 路由文件**

```python
# backend/app/api/presets.py
"""节点预设 API —— CRUD"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user, CurrentUser
from app.schemas.common import ApiResponse
from app.schemas.preset import PresetCreate, PresetUpdate
from app.services import preset_service

router = APIRouter(prefix="/api/v1", tags=["节点预设"])


@router.get("/node-presets")
async def get_presets(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的节点预设列表"""
    result = await preset_service.list_presets(db, current_user.id)
    return ApiResponse.ok(result)


@router.post("/node-presets")
async def create_preset(
    body: PresetCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """创建节点预设"""
    result = await preset_service.create_preset(db, body, current_user.id)
    await db.commit()
    return ApiResponse.ok(result, message="预设已创建")


@router.put("/node-presets/{preset_id}")
async def update_preset(
    preset_id: int,
    body: PresetUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """更新节点预设 —— 仅所有者可修改"""
    result = await preset_service.update_preset(db, preset_id, body, current_user.id)
    await db.commit()
    return ApiResponse.ok(result, message="预设已更新")


@router.delete("/node-presets/{preset_id}")
async def delete_preset(
    preset_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除节点预设 —— 仅所有者可删除"""
    await preset_service.delete_preset(db, preset_id, current_user.id)
    await db.commit()
    return ApiResponse.ok(message="预设已删除")
```

- [ ] **Step 2: 注册路由到 FastAPI app**

检查 `backend/app/main.py`（或路由注册文件）是否需要手动注册。通常项目会通过 `app.api.__init__.py` 自动发现，如果不自动发现，需要在主应用文件中添加：

```python
from app.api.presets import router as presets_router
app.include_router(presets_router)
```

验证：

```bash
cd backend && grep -r "include_router" app/ --include="*.py" -l
```

按项目现有模式注册。

- [ ] **Step 3: 验证 API 可用**

启动后端后测试：

```bash
# 创建预设
curl -X POST http://localhost:8000/api/v1/node-presets \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"测试预设","node_name":"测试节点","time_limit_days":3,"require_file":true}'

# 获取列表
curl http://localhost:8000/api/v1/node-presets -H "Authorization: Bearer <token>"
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/presets.py
git commit -m "feat: 新增节点预设 API 路由"
```

---

### Task 5: 前端 —— API 封装

**文件：**
- 创建: `frontend/src/api/presets.ts`

**接口：**
- 产出: `PresetItem`, `PresetFormData` 类型 + `getPresets`, `createPreset`, `updatePreset`, `deletePreset` 函数

- [ ] **Step 1: 创建 API 封装文件**

```typescript
// frontend/src/api/presets.ts
/** 节点预设 API */
import request from './request'

/** 预设列表项 */
export interface PresetItem {
  id: number
  name: string
  node_name: string
  assignee_id: number | null
  assignee_name: string | null
  checkers: Array<{ user_id: number }> | null
  checkers_names: string[] | null
  approvers: Array<{ user_id: number }> | null
  approvers_names: string[] | null
  time_limit_days: number | null
  require_file: boolean
  sort_order: number
  created_at: string | null
}

/** 预设表单数据（创建/编辑用） */
export interface PresetFormData {
  name: string
  node_name: string
  assignee_id?: number | null
  checkers?: Array<{ user_id: number }> | null
  approvers?: Array<{ user_id: number }> | null
  time_limit_days?: number | null
  require_file?: boolean
}

/** 获取当前用户的预设列表 */
export async function getPresets(): Promise<{ items: PresetItem[]; total: number }> {
  const res = await request.get('/node-presets')
  return res.data.data
}

/** 创建预设 */
export async function createPreset(data: PresetFormData): Promise<PresetItem> {
  const res = await request.post('/node-presets', data)
  return res.data.data
}

/** 更新预设 */
export async function updatePreset(id: number, data: Partial<PresetFormData>): Promise<PresetItem> {
  const res = await request.put(`/node-presets/${id}`, data)
  return res.data.data
}

/** 删除预设 */
export async function deletePreset(id: number): Promise<void> {
  await request.delete(`/node-presets/${id}`)
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/presets.ts
git commit -m "feat: 新增节点预设前端 API 封装"
```

---

### Task 6: 前端 —— PresetEditor 组件

**文件：**
- 创建: `frontend/src/views/flows/designer/PresetEditor.vue`

**接口：**
- Props: `modelValue: boolean`（显隐）, `initial?: PresetFormData`（编辑时预填）
- Emits: `update:modelValue`, `saved`

- [ ] **Step 1: 创建 PresetEditor.vue**

```vue
<template>
  <!-- 预设编辑弹窗 —— 新建/编辑节点预设 -->
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    :title="isEdit ? '编辑预设' : '新建预设'"
    width="460px"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px" label-position="top">
      <el-form-item label="预设名称" prop="name">
        <el-input v-model="form.name" placeholder="列表中显示的名称" maxlength="30" show-word-limit />
      </el-form-item>
      <el-form-item label="节点名称" prop="node_name">
        <el-input v-model="form.node_name" placeholder="拖出后节点的默认名称" maxlength="30" show-word-limit />
      </el-form-item>
      <el-form-item label="负责人" prop="assignee_id">
        <UserSelector
          v-model="form.assignee_id"
          :initial-options="assigneeInitialOptions"
          placeholder="搜索并选择负责人"
          @update:model-value="handleAssigneeChange"
          @options-loaded="handleOptionsLoaded"
        />
      </el-form-item>
      <el-form-item label="校验人">
        <UserSelector
          v-model="form.checkers"
          :multiple="true"
          :initial-options="checkerInitialOptions"
          placeholder="搜索并选择校验人（可多选）"
          @update:model-value="handleCheckersChange"
          @options-loaded="handleOptionsLoaded"
        />
      </el-form-item>
      <el-form-item label="审批人">
        <UserSelector
          v-model="form.approvers"
          :multiple="true"
          :initial-options="approverInitialOptions"
          placeholder="搜索并选择审批人（可多选）"
          @update:model-value="handleApproversChange"
          @options-loaded="handleOptionsLoaded"
        />
      </el-form-item>
      <el-form-item label="时限（天）">
        <el-input-number v-model="form.time_limit_days" :min="1" :max="365" placeholder="1~365" style="width:100%" />
      </el-form-item>
      <el-form-item label="文件上传">
        <el-switch v-model="form.require_file" active-text="必须上传" inactive-text="可不上传" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/** 预设编辑弹窗 —— 新建/编辑节点预设配置 */
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import UserSelector from '@/components/UserSelector.vue'
import type { UserSearchItem } from '@/api/admin'
import { createPreset, updatePreset, type PresetFormData } from '@/api/presets'

const props = defineProps<{
  modelValue: boolean
  initial?: PresetFormData | null  // 编辑时传入已有数据
  editingId?: number | null        // 编辑时传预设 ID
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  saved: []
}>()

const formRef = ref<FormInstance>()
const saving = ref(false)
const isEdit = computed(() => !!props.initial)

/** 用户名称缓存 */
const userNameCache = reactive<Record<number, string>>({})

const form = reactive({
  name: '',
  node_name: '',
  assignee_id: undefined as number | undefined,
  checkers: [] as number[],
  approvers: [] as number[],
  time_limit_days: 3,
  require_file: true,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入预设名称', trigger: 'blur' }],
  node_name: [{ required: true, message: '请输入节点名称', trigger: 'blur' }],
}

/** 初始选项 —— 让 UserSelector 显示已有姓名 */
const assigneeInitialOptions = computed<UserSearchItem[]>(() => {
  if (form.assignee_id) {
    const name = userNameCache[form.assignee_id] || ''
    return [{ id: form.assignee_id, username: '', real_name: name, organization_id: null, organization_name: null }]
  }
  return []
})

const checkerInitialOptions = computed<UserSearchItem[]>(() => {
  return (form.checkers || []).map(id => ({
    id, username: '', real_name: userNameCache[id] || '', organization_id: null, organization_name: null,
  }))
})

const approverInitialOptions = computed<UserSearchItem[]>(() => {
  return (form.approvers || []).map(id => ({
    id, username: '', real_name: userNameCache[id] || '', organization_id: null, organization_name: null,
  }))
})

/** 加载初始数据 */
function loadInitial() {
  if (props.initial) {
    form.name = props.initial.name || ''
    form.node_name = props.initial.node_name || ''
    form.assignee_id = props.initial.assignee_id ?? undefined
    form.checkers = (props.initial.checkers || []).map((c: any) => c.user_id)
    form.approvers = (props.initial.approvers || []).map((a: any) => a.user_id)
    form.time_limit_days = props.initial.time_limit_days ?? 3
    form.require_file = props.initial.require_file ?? true
  } else {
    form.name = ''
    form.node_name = ''
    form.assignee_id = undefined
    form.checkers = []
    form.approvers = []
    form.time_limit_days = 3
    form.require_file = true
  }
}

/** 弹窗打开/切换时重置 */
watch(() => props.modelValue, (visible) => {
  if (visible) loadInitial()
})

/** UserSelector 加载完成 */
function handleOptionsLoaded(users: Array<{ id: number; real_name: string }>) {
  for (const u of users) userNameCache[u.id] = u.real_name
}

function handleAssigneeChange(_val: number | undefined) { /* 不需要额外处理 */ }
function handleCheckersChange(_val: number[]) { /* 不需要额外处理 */ }
function handleApproversChange(_val: number[]) { /* 不需要额外处理 */ }

/** 关闭时重置表单 */
function handleClose() {
  formRef.value?.resetFields()
  loadInitial()
}

/** 保存 */
async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const data: PresetFormData = {
      name: form.name.trim(),
      node_name: form.node_name.trim(),
      assignee_id: form.assignee_id || null,
      checkers: form.checkers.length > 0 ? form.checkers.map(id => ({ user_id: id })) : null,
      approvers: form.approvers.length > 0 ? form.approvers.map(id => ({ user_id: id })) : null,
      time_limit_days: form.time_limit_days,
      require_file: form.require_file,
    }

    if (props.editingId) {
      await updatePreset(props.editingId, data)
      ElMessage.success('预设已更新')
    } else {
      await createPreset(data)
      ElMessage.success('预设已创建')
    }
    emit('update:modelValue', false)
    emit('saved')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>
```

> **注意：** 编辑功能需要知道预设 ID。方案：给 PresetEditor 增加 `editingId?: number` prop。详见 Task 8 FlowDesigner 组合逻辑。

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/flows/designer/PresetEditor.vue
git commit -m "feat: 新增预设编辑弹窗组件"
```

---

### Task 7: 前端 —— NodePanel 改造

**文件：**
- 修改: `frontend/src/views/flows/designer/NodePanel.vue`

**接口：**
- Props: 新增 `presets: PresetItem[]`
- Emits: `add` 改为带参 `add: [preset?: PresetItem]`；新增 `edit-preset: [PresetItem]`；新增 `delete-preset: [PresetItem]`
- 消耗: `PresetItem` 类型

- [ ] **Step 1: 重写 NodePanel.vue**

```vue
<template>
  <div class="node-panel">
    <div class="panel-title">节点库</div>
    <div class="panel-desc">拖拽或点击添加到画布</div>

    <!-- 基础工作节点（置顶） -->
    <div
      class="node-card node-card--base"
      draggable="true"
      @click="emit('add')"
      @dragstart="onBaseDragStart"
    >
      <div class="node-icon" style="background: #ecf5ff; border-color: #1a6fb5" />
      <div class="node-info">
        <div class="node-label">工作节点</div>
        <div class="node-hint">空白审批/校验节点</div>
      </div>
    </div>

    <!-- 预设节点列表 -->
    <div
      v-for="preset in presets"
      :key="preset.id"
      class="node-card node-card--preset"
      draggable="true"
      @click="emit('add', preset)"
      @dragstart="onPresetDragStart($event, preset)"
      @mouseenter="hoveredId = preset.id"
      @mouseleave="hoveredId = null"
    >
      <div class="node-icon" style="background: #f0f9eb; border-color: #67c23a" />
      <div class="node-info">
        <div class="node-label">💾 {{ preset.name }}</div>
        <div class="node-hint">
          {{ preset.assignee_name || '未设负责人' }} · {{ preset.time_limit_days || '不限' }}天
        </div>
      </div>
      <!-- hover 操作图标 -->
      <Transition name="fade">
        <span v-show="hoveredId === preset.id" class="node-card__actions">
          <el-button text size="small" @click.stop="emit('edit-preset', preset)" title="编辑">
            <el-icon :size="14"><EditPen /></el-icon>
          </el-button>
          <el-button text size="small" @click.stop="emit('delete-preset', preset)" title="删除">
            <el-icon :size="14"><Delete /></el-icon>
          </el-button>
        </span>
      </Transition>
    </div>

    <!-- 新建预设按钮 -->
    <el-button class="add-preset-btn" @click="emit('edit-preset')">
      <el-icon><Plus /></el-icon>
      新建预设
    </el-button>
  </div>
</template>

<script setup lang="ts">
/** 节点库面板 —— 基础节点 + 预设节点列表 */
import { ref } from 'vue'
import { EditPen, Delete, Plus } from '@element-plus/icons-vue'
import type LogicFlow from '@logicflow/core'
import type { PresetItem } from '@/api/presets'

const emit = defineEmits<{
  /** 添加节点：无参 = 空白工作节点；传 preset = 预设节点 */
  add: [preset?: PresetItem]
  /** 编辑预设：无参 = 新建；传 preset = 编辑 */
  'edit-preset': [preset?: PresetItem]
  /** 删除预设 */
  'delete-preset': [preset: PresetItem]
}>()

const props = defineProps<{
  lf: LogicFlow | null
  presets: PresetItem[]
}>()

const hoveredId = ref<number | null>(null)

/** 基础工作节点 DnD */
function onBaseDragStart(e: DragEvent) {
  startDnD(e, {
    name: '新节点',
    is_start: false, is_end: false,
    require_file: true,
    approval_strategy: 'all_approve',
    time_limit_days: 3,
  })
}

/** 预设节点 DnD */
function onPresetDragStart(e: DragEvent, preset: PresetItem) {
  startDnD(e, {
    name: preset.node_name,
    is_start: false, is_end: false,
    assignee_id: preset.assignee_id,
    assignee_name: preset.assignee_name,
    checkers: preset.checkers?.map(c => c.user_id) || null,
    checkers_names: preset.checkers_names || null,
    approvers: preset.approvers?.map(a => a.user_id) || null,
    approvers_names: preset.approvers_names || null,
    time_limit_days: preset.time_limit_days,
    require_file: preset.require_file,
    approval_strategy: 'all_approve',
  })
}

/** LogicFlow DnD 启动 */
function startDnD(event: DragEvent, properties: Record<string, any>) {
  if (!props.lf || !event.dataTransfer) return
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', 'work-node')
  props.lf.dnd.startDrag({ type: 'work-node', properties })
}
</script>

<style lang="scss" scoped>
.node-panel {
  width: 160px; height: 100%;
  background: #fff;
  border-right: 1px solid var(--el-border-color-light);
  padding: 12px; display: flex;
  flex-direction: column; gap: 8px;
  flex-shrink: 0;
  overflow-y: auto;

  .panel-title { font-size: 14px; font-weight: 600; color: var(--el-text-color-primary); }
  .panel-desc { font-size: 11px; color: var(--el-text-color-placeholder); margin-bottom: 4px; }
}

.node-card {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border: 1px solid var(--el-border-color-light);
  border-radius: 6px; cursor: grab;
  transition: box-shadow 0.2s; user-select: none;
  position: relative;

  &:hover { box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); border-color: var(--el-color-primary); }
  &:active { cursor: grabbing; }

  &--base { border-style: dashed; }
  &--preset { border-color: #e1f3d8; }
}

.node-icon { width: 32px; height: 32px; border-radius: 4px; border: 2px solid; flex-shrink: 0; }

.node-info {
  flex: 1; min-width: 0;
  .node-label { font-size: 13px; color: var(--el-text-color-primary); }
  .node-hint { font-size: 11px; color: var(--el-text-color-placeholder); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
}

/* hover 操作图标 */
.node-card__actions {
  position: absolute; top: 2px; right: 4px;
  display: flex; align-items: center; gap: 0;
  background: rgba(255,255,255,0.92);
  border-radius: 4px; padding: 0 2px;
}

.add-preset-btn {
  width: 100%;
  margin-top: 4px;
  border-style: dashed;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/flows/designer/NodePanel.vue
git commit -m "feat: NodePanel 改造 —— 支持预设列表 + hover 编辑删除 + DnD"
```

---

### Task 8: 前端 —— FlowCanvas 扩展 + PropertyPanel 按钮 + FlowDesigner 组装

**文件：**
- 修改: `frontend/src/views/flows/designer/FlowCanvas.vue`
- 修改: `frontend/src/views/flows/designer/PropertyPanel.vue`
- 修改: `frontend/src/views/flows/FlowDesigner.vue`

**接口：**
- FlowCanvas: `addWorkNode(x?, y?, presetProperties?)` 扩展
- PropertyPanel: 新增 `save-as-preset` emit + 按钮
- FlowDesigner: 组装 PresetEditor + 预设数据流

- [ ] **Step 1: 扩展 FlowCanvas.vue `addWorkNode()`**

修改 `FlowCanvas.vue` 的 `addWorkNode` 函数，接受可选的预设参数：

```typescript
/** 添加工作节点（可选预设配置） */
function addWorkNode(x?: number, y?: number, presetProperties?: Record<string, any>) {
  const instance = lf.value
  if (!instance) return

  if (x === undefined || y === undefined) {
    const { SCALE_X, TRANSLATE_X, TRANSLATE_Y } = instance.getTransform()
    const container = canvasRef.value!
    const cx = (container.clientWidth / 2 - TRANSLATE_X) / SCALE_X
    const cy = (container.clientHeight / 2 - TRANSLATE_Y) / SCALE_X
    x = cx + (Math.random() - 0.5) * 100
    y = cy + (Math.random() - 0.5) * 100
  }

  // 默认属性
  const defaults = {
    name: `节点 ${workNodeCounter++}`,
    is_start: false, is_end: false,
    require_file: true,
    approval_strategy: 'all_approve',
    time_limit_days: 3,
  }

  // 合并预设属性（预设优先），preset name 不自动加计数器
  const merged = { ...defaults, ...(presetProperties || {}) }

  instance.addNode({
    id: `work-${Date.now()}`,
    type: 'work-node', x, y,
    properties: merged,
  })
}
```

**注意：** `defineExpose` 中已经暴露了 `addWorkNode`，不需要修改。

- [ ] **Step 2: PropertyPanel 添加"保存为预设"按钮**

在 `PropertyPanel.vue` template 中，`panel-title` 区域增加按钮：

```html
<!-- 在 .panel-title 内，node-label 和 el-tag 之后 -->
<div class="panel-title">
  <span class="node-label">工作节点配置</span>
  <div class="panel-title__right">
    <el-tag size="small" :type="isConfigured ? 'success' : 'warning'">
      {{ isConfigured ? '已配置' : '未配置' }}
    </el-tag>
    <el-button
      v-show="isConfigured"
      text
      size="small"
      type="primary"
      @click="emit('save-as-preset', form)"
      style="margin-left: 6px"
    >
      💾 保存为预设
    </el-button>
  </div>
</div>
```

在 script 中新增 emit：

```typescript
const emit = defineEmits<{
  'save-as-preset': [formData: typeof form]
}>()
```

在 `<style>` 中添加 `.panel-title__right`：

```scss
.panel-title {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;
  &__right { display: flex; align-items: center; }
  .node-label { font-size: 15px; font-weight: 600; color: var(--el-text-color-primary); }
}
```

- [ ] **Step 3: FlowDesigner.vue 组装所有模块**

核心改动（按位置描述）：

**3a. 引入新模块：**

```typescript
import PresetEditor from './designer/PresetEditor.vue'
import { getPresets, createPreset, updatePreset, deletePreset, type PresetItem, type PresetFormData } from '@/api/presets'
```

**3b. 新增状态变量：**

```typescript
/** 预设列表 */
const presets = ref<PresetItem[]>([])
/** 预设编辑弹窗状态 */
const presetEditorVisible = ref(false)
const editingPreset = ref<PresetItem | null>(null)  // null = 新建，有值 = 编辑
```

**3c. 获取预设列表：**

```typescript
/** 加载当前用户的预设列表 */
async function fetchPresets() {
  try {
    const res = await getPresets()
    presets.value = res.items || []
  } catch { /* 静默失败，预设列表为空 */ }
}
```

在 `onMounted` 中调用 `fetchPresets()`。

**3d. 事件处理函数：**

```typescript
/** 处理 NodePanel 的 add 事件 —— 普通节点 / 预设节点 */
function handleAddNode(preset?: PresetItem) {
  if (!preset) {
    // 空白工作节点
    canvasRef.value?.addWorkNode()
  } else {
    // 预设节点：构建 properties
    const props = buildPresetProperties(preset)
    // 人员失效检测
    validatePresetUsers(preset)
    canvasRef.value?.addWorkNode(undefined, undefined, props)
  }
  updateUndoRedoState()
}

/** 从 PresetItem 构建节点 properties */
function buildPresetProperties(preset: PresetItem): Record<string, any> {
  return {
    name: preset.node_name,
    is_start: false, is_end: false,
    assignee_id: preset.assignee_id ?? null,
    assignee_name: preset.assignee_name || null,
    checkers: preset.checkers?.map(c => c.user_id) || null,
    checkers_names: preset.checkers_names || null,
    approvers: preset.approvers?.map(a => a.user_id) || null,
    approvers_names: preset.approvers_names || null,
    time_limit_days: preset.time_limit_days ?? null,
    require_file: preset.require_file ?? true,
    approval_strategy: 'all_approve',
  }
}

/** 检测预设中的人员是否在当前系统中有效 */
function validatePresetUsers(preset: PresetItem) {
  // 从 UserSelector 缓存中检查（简单方案：根据 *_name 是否为空判断）
  const missing: string[] = []
  if (preset.assignee_id && !preset.assignee_name) {
    missing.push(`负责人(ID:${preset.assignee_id})`)
  }
  // 校验人检测
  if (preset.checkers) {
    for (let i = 0; i < preset.checkers.length; i++) {
      const name = preset.checkers_names?.[i]
      if (!name) missing.push(`校验人(ID:${preset.checkers[i].user_id})`)
    }
  }
  // 审批人检测
  if (preset.approvers) {
    for (let i = 0; i < preset.approvers.length; i++) {
      const name = preset.approvers_names?.[i]
      if (!name) missing.push(`审批人(ID:${preset.approvers[i].user_id})`)
    }
  }
  // toast 提示
  if (missing.length > 0) {
    import('element-plus').then(({ ElMessage }) => {
      ElMessage.warning(`预设「${preset.name}」中的以下人员已不可用：${missing.join('、')}`)
    })
  }
}

/** 打开预设编辑弹窗（新建 / 编辑） */
function handleEditPreset(preset?: PresetItem) {
  editingPreset.value = preset || null
  presetEditorVisible.value = true
}

/** 删除预设 */
async function handleDeletePreset(preset: PresetItem) {
  try {
    await import('element-plus').then(({ ElMessageBox }) =>
      ElMessageBox.confirm(`确定删除预设「${preset.name}」？`, '删除确认', { type: 'warning' })
    )
    await deletePreset(preset.id)
    import('element-plus').then(({ ElMessage }) => ElMessage.success('预设已删除'))
    await fetchPresets()
  } catch { /* 取消或失败 */ }
}

/** PropertyPanel "保存为预设"事件 */
function handleSaveAsPreset(formData: any) {
  editingPreset.value = null  // 新建模式
  presetEditorVisible.value = true
  // 通过 PresetEditor 的 initial 传递数据
  // 传参方式：将 formData 暂存，下次 PresetEditor 打开时预填
  pendingPresetData.value = {
    name: formData.name || '',
    node_name: formData.name || '',
    assignee_id: formData.assignee_id,
    checkers: formData.checkers?.map((id: number) => ({ user_id: id })) || null,
    approvers: formData.approvers?.map((id: number) => ({ user_id: id })) || null,
    time_limit_days: formData.time_limit_days,
    require_file: formData.require_file,
  }
}

/** 待传递给 PresetEditor 的预填数据 */
const pendingPresetData = ref<PresetFormData | null>(null)

/** PresetEditor 保存成功回调 */
async function onPresetSaved() {
  await fetchPresets()
  pendingPresetData.value = null
}
```

**3e. Template 区域新增 PresetEditor 弹窗：**

在 `<el-dialog>`（发起项目弹窗）之后添加：

```html
<!-- 预设编辑弹窗 -->
<PresetEditor
  v-model="presetEditorVisible"
  :initial="editingPreset ? editPresetToFormData(editingPreset) : pendingPresetData"
  :editing-id="editingPreset?.id"
  @saved="onPresetSaved"
/>
```

**3f. NodePanel 更新 props 和 emit 绑定：**

```html
<NodePanel
  :lf="canvasRef?.getLf() ?? null"
  :presets="presets"
  @add="handleAddNode"
  @edit-preset="handleEditPreset"
  @delete-preset="handleDeletePreset"
/>
```

**3g. PropertyPanel 绑定 save-as-preset 事件：**

```html
<PropertyPanel
  :lf="canvasRef?.getLf() ?? null"
  :node-data="selectedNodeData"
  @save-as-preset="handleSaveAsPreset"
/>
```

- [ ] **Step 4: 验证前端编译**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：零类型错误。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/flows/designer/FlowCanvas.vue frontend/src/views/flows/designer/PropertyPanel.vue frontend/src/views/flows/FlowDesigner.vue frontend/src/views/flows/designer/PresetEditor.vue
git commit -m "feat: FlowCanvas 预设支持 + PropertyPanel 保存为预设 + FlowDesigner 组装"
```

---

### Task 9: 端到端验证 + 修复

- [ ] **Step 1: 启动后端，确认 API 正常**

```bash
cd backend && python main.py
# 另开终端：
# POST /api/v1/node-presets → 创建预设成功
# GET /api/v1/node-presets → 返回预设列表含 *_names
# PUT /api/v1/node-presets/1 → 更新成功
# DELETE /api/v1/node-presets/1 → 删除成功
```

- [ ] **Step 2: 启动前端，确认全部功能**

| 测试场景 | 预期结果 |
|----------|----------|
| 打开设计器 → 节点库显示基础节点 + 预设列表 | 预设为空时不报错 |
| 点击"新建预设" → 弹出 PresetEditor | 表单正常展示 |
| 填写预设 → 保存 | 节点库出现新预设卡片 |
| 点击预设卡片 → 画布新增节点 | 节点已预填负责人/校验人/审批人/时限 |
| 拖拽预设卡片到画布 | 同上 |
| 配置画布节点 → 点击"保存为预设" | 弹出 PresetEditor 且预填数据 |
| hover 预设卡片 → 编辑/删除图标 | 编辑弹窗 + 删除二次确认 |
| 拖出含失效人员的预设 | toast 警告 |
| 点击空白工作节点 | 保持原有行为（空白节点） |

- [ ] **Step 3: 修复发现的问题**

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "fix: 端到端验证修复"
```
