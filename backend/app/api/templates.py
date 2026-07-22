"""项目模板 API —— 简化版"""

import os
import uuid
from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.template import TemplateCreate, TemplateUpdate, DocTemplateItem, DocTemplateListResponse
from app.models import FlowTemplate, DocumentTemplate, Organization
from app.services.template_service import (
    get_organization_summaries, list_templates, create_template,
    get_template_detail, update_template, delete_template,
)
from app.api.deps import get_current_active_user, CurrentUser, require_manager, require_same_org, require_admin

router = APIRouter(prefix="/api/v1", tags=["项目模板"])

# 文件模板允许的扩展名（.doc 需要 LibreOffice 转为 .docx）
_ALLOWED_DOC_EXTENSIONS = {".doc", ".docx", ".xlsx"}
# 需要转换的旧格式
_CONVERT_FORMATS = {".doc"}
# 文件模板最大 10MB
_MAX_DOC_SIZE = 10 * 1024 * 1024


@router.get("/templates/organizations")
async def get_orgs_for_template(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """组织选择页 → 展示组织卡片"""
    summaries, total_instances = await get_organization_summaries(
        db, is_active=True, current_user_id=current_user.id
    )
    return ApiResponse.ok({
        "organizations": [s.model_dump() for s in summaries],
        "total_running_instances": total_instances,
    })


@router.get("/templates")
async def get_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    organization_id: int | None = Query(None, description="组织筛选"),
    keyword: str | None = Query(None, description="名称搜索"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """模板列表"""
    result = await list_templates(
        db, page=page, page_size=page_size,
        organization_id=organization_id, keyword=keyword,
    )
    return ApiResponse.ok(result.model_dump())


@router.post("/templates")
async def post_template(
    data: TemplateCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """创建模板 —— 仅本所所长可创建"""
    require_manager(current_user)
    require_same_org(current_user, data.organization_id)
    tpl = await create_template(db, data, current_user.id)
    await db.commit()
    return ApiResponse.ok({"id": tpl.id, "name": tpl.name}, message="模板创建成功")


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """模板详情 —— 含节点/连线"""
    detail = await get_template_detail(db, template_id)
    return ApiResponse.ok(detail.model_dump())


@router.put("/templates/{template_id}")
async def put_template(
    template_id: int, data: TemplateUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """更新模板基本信息 —— 仅本所所长可编辑"""
    require_manager(current_user)
    tpl_org = (await db.execute(
        select(FlowTemplate.organization_id).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl_org is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, tpl_org)
    tpl = await update_template(db, template_id, data)
    await db.commit()
    return ApiResponse.ok({"id": tpl.id, "name": tpl.name}, message="模板信息已更新")


@router.delete("/templates/{template_id}")
async def del_template(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除模板 —— 仅本所所长可删除"""
    require_manager(current_user)
    tpl_org = (await db.execute(
        select(FlowTemplate.organization_id).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl_org is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, tpl_org)
    await delete_template(db, template_id)
    await db.commit()
    return ApiResponse.ok(message="模板已删除")


# ─── 文件模板管理（挂在流程模板下）───────────────────────────────


async def _convert_doc_to_docx(input_path: str) -> str | None:
    """用 LibreOffice 无头模式将旧版 .doc 转为 .docx

    返回转换后的 .docx 路径，失败返回 None。
    转换成功后删除原 .doc 文件。
    """
    import asyncio
    output_dir = os.path.dirname(input_path)

    try:
        proc = await asyncio.create_subprocess_exec(
            settings.LIBREOFFICE_PATH,
            "--headless",
            "--convert-to", "docx",
            "--outdir", output_dir,
            input_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=60)

        base = os.path.splitext(os.path.basename(input_path))[0]
        docx_path = os.path.join(output_dir, f"{base}.docx")

        if os.path.exists(docx_path):
            # 删除源 .doc 文件
            os.remove(input_path)
            return docx_path

    except asyncio.TimeoutError:
        pass

    return None

# 可用变量列表（供管理员在模板中参考使用）
_AVAILABLE_VARIABLES = [
    "{{项目名称}}", "{{项目描述}}", "{{合同号}}", "{{产品型号}}",
    "{{销售经理}}", "{{模板名称}}", "{{优先级}}", "{{当前节点}}",
    "{{发起人}}", "{{发起日期}}", "{{所属部门}}", "{{当前负责人}}",
    "{{当前日期}}",
]


@router.get("/templates/{template_id}/documents")
async def list_document_templates(
    template_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取流程模板的文件模板列表（含可用变量参考）"""
    # 确认模板存在
    tpl = (await db.execute(
        select(FlowTemplate).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")

    docs = (await db.execute(
        select(DocumentTemplate)
        .where(DocumentTemplate.template_id == template_id)
        .order_by(DocumentTemplate.created_at.desc())
    )).scalars().all()

    items = [
        DocTemplateItem(
            id=d.id,
            name=d.name,
            original_name=d.original_name,
            file_size=d.file_size,
            file_type=d.file_type,
            created_at=d.created_at,
        )
        for d in docs
    ]

    return ApiResponse.ok(
        DocTemplateListResponse(
            items=items,
            available_variables=_AVAILABLE_VARIABLES,
        ).model_dump()
    )


@router.post("/templates/{template_id}/documents")
async def upload_document_template(
    template_id: int,
    file: UploadFile = File(..., description="文件模板（Word .docx / Excel .xlsx，支持 {{占位符}}）"),
    name: str | None = Query(None, description="显示名称，不传则使用原始文件名"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文件模板 —— 仅本所所长可操作"""
    require_manager(current_user)

    tpl = (await db.execute(
        select(FlowTemplate).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, tpl.organization_id)

    # 校验扩展名
    if not file.filename:
        raise AppException(ErrorCode.BAD_REQUEST, "文件名不能为空")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _ALLOWED_DOC_EXTENSIONS:
        raise AppException(
            ErrorCode.BAD_REQUEST,
            f"仅支持 {', '.join(_ALLOWED_DOC_EXTENSIONS)} 格式，当前格式：{ext or '未知'}"
        )

    # 读取 + 校验大小
    contents = await file.read()
    if len(contents) > _MAX_DOC_SIZE:
        raise AppException(ErrorCode.BAD_REQUEST, "文件模板不能超过 10MB")

    # 存储到 STORAGE_ROOT/document_templates/
    upload_dir = os.path.join(settings.STORAGE_ROOT, "document_templates")
    os.makedirs(upload_dir, exist_ok=True)

    ext_stripped = ext.lstrip(".")          # "doc" / "docx" / "xlsx"
    final_type = ext_stripped
    safe_name = f"{template_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(upload_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    # 旧版 .doc 格式：用 LibreOffice 无头模式转为 .docx
    final_path = file_path
    if ext in _CONVERT_FORMATS:
        converted = await _convert_doc_to_docx(file_path)
        if converted:
            final_path = converted
            final_type = "docx"
        else:
            # 转换失败，删除已保存的 .doc 文件，返回错误
            if os.path.exists(file_path):
                os.remove(file_path)
            raise AppException(ErrorCode.BAD_REQUEST, "旧版 .doc 文件转换失败，请手动另存为 .docx 后重新上传")

    # 保存记录（路径指向 .docx 转换结果）
    doc = DocumentTemplate(
        template_id=template_id,
        name=name or os.path.splitext(file.filename)[0],
        original_name=file.filename,
        file_path=final_path,
        file_size=os.path.getsize(final_path),
        file_type=final_type,
        created_by=current_user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return ApiResponse.ok(
        {"id": doc.id, "name": doc.name, "file_type": doc.file_type},
        message="文件模板上传成功",
    )


@router.delete("/templates/{template_id}/documents/{doc_id}")
async def delete_document_template(
    template_id: int,
    doc_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """删除文件模板 —— 仅本所所长可操作"""
    require_manager(current_user)

    tpl = (await db.execute(
        select(FlowTemplate).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, tpl.organization_id)

    doc = (await db.execute(
        select(DocumentTemplate).where(
            DocumentTemplate.id == doc_id,
            DocumentTemplate.template_id == template_id,
        )
    )).scalar_one_or_none()
    if doc is None:
        raise AppException(ErrorCode.NOT_FOUND, "文件模板不存在")

    # 删除磁盘文件
    from app.services.document_service import get_doc_template_abs_path
    abs_path = get_doc_template_abs_path(doc)
    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass  # 删不掉也不阻塞数据库操作

    await db.delete(doc)
    await db.commit()

    return ApiResponse.ok(message="文件模板已删除")


# ─── 系统管理员：跨组织文件模板管理 ───────────────────────────

admin_router = APIRouter(prefix="/api/v1/admin", tags=["系统管理-文件模板"])


@admin_router.get("/document-templates")
async def admin_list_document_templates(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    organization_id: int | None = Query(None, description="按组织筛选"),
    keyword: str | None = Query(None, description="模板名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """系统管理员查看所有文件模板 —— 按流程模板分组，支持按组织/关键词筛选"""
    require_admin(current_user)

    from sqlalchemy import func

    # 基础查询：DocumentTemplate JOIN FlowTemplate JOIN Organization
    base = (
        select(
            DocumentTemplate.id,
            DocumentTemplate.name,
            DocumentTemplate.original_name,
            DocumentTemplate.file_size,
            DocumentTemplate.file_type,
            DocumentTemplate.created_at,
            DocumentTemplate.template_id,
            FlowTemplate.name.label("template_name"),
            FlowTemplate.organization_id,
            Organization.name.label("organization_name"),
        )
        .join(FlowTemplate, DocumentTemplate.template_id == FlowTemplate.id)
        .join(Organization, FlowTemplate.organization_id == Organization.id)
    )

    conditions = []
    if organization_id:
        conditions.append(FlowTemplate.organization_id == organization_id)
    if keyword:
        conditions.append(
            (DocumentTemplate.name.like(f"%{keyword}%"))
            | (FlowTemplate.name.like(f"%{keyword}%"))
        )

    if conditions:
        base = base.where(*conditions)

    # 计数（需要 join 才能用 FlowTemplate 的条件列）
    count_base = select(func.count(DocumentTemplate.id)).join(
        FlowTemplate, DocumentTemplate.template_id == FlowTemplate.id
    ).join(
        Organization, FlowTemplate.organization_id == Organization.id
    )
    if conditions:
        count_base = count_base.where(*conditions)
    total = (await db.execute(count_base)).scalar() or 0

    stmt = base.order_by(DocumentTemplate.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.all()

    items = [
        {
            "id": row[0],
            "name": row[1],
            "original_name": row[2],
            "file_size": row[3],
            "file_type": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
            "template_id": row[6],
            "template_name": row[7],
            "organization_id": row[8],
            "organization_name": row[9],
        }
        for row in rows
    ]

    return ApiResponse.ok({"items": items, "total": total, "page": page, "page_size": page_size})


@admin_router.delete("/document-templates/{doc_id}")
async def admin_delete_document_template(
    doc_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """系统管理员删除任意文件模板"""
    require_admin(current_user)

    doc = (await db.execute(
        select(DocumentTemplate).where(DocumentTemplate.id == doc_id)
    )).scalar_one_or_none()
    if doc is None:
        raise AppException(ErrorCode.NOT_FOUND, "文件模板不存在")

    from app.services.document_service import get_doc_template_abs_path
    abs_path = get_doc_template_abs_path(doc)
    if os.path.exists(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass

    await db.delete(doc)
    await db.commit()

    return ApiResponse.ok(message="文件模板已删除")


@admin_router.get("/organizations")
async def admin_list_organizations(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """系统管理员获取所有组织列表（供筛选下拉框）"""
    require_admin(current_user)
    orgs = (await db.execute(
        select(Organization).where(Organization.is_active == True).order_by(Organization.name)
    )).scalars().all()
    return ApiResponse.ok({
        "items": [{"id": o.id, "name": o.name} for o in orgs]
    })
