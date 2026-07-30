"""项目模板 API —— 含文件模板分类和批量下载 ZIP"""

import os
import uuid
from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode
from app.schemas.common import ApiResponse
from app.schemas.template import (
    TemplateCreate, TemplateUpdate, DocTemplateItem, DocTemplateListResponse,
    TemplateCategoryCreate, TemplateCategoryUpdate,
    CategoryDocLinkRequest,
)
from app.models import (
    FlowTemplate, DocumentTemplate, TemplateDocumentLink,
    TemplateCategory, TemplateCategoryDocument, Organization,
)
from app.services.template_service import (
    get_organization_summaries, list_templates, create_template,
    get_template_detail, update_template, delete_template,
)
from app.services.category_service import (
    list_categories, create_category, update_category, delete_category,
    get_category_detail, link_documents_to_category, unlink_documents_from_category,
    batch_fill_and_zip,
)
from app.api.deps import get_current_active_user, CurrentUser, require_manager, require_same_org, require_admin, resolve_org_scope

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
    """模板列表（非管理员默认只看本所模板）"""
    organization_id = resolve_org_scope(current_user, organization_id)

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
    from app.models import FlowTemplate
    from sqlalchemy import select
    tpl = (await db.execute(select(FlowTemplate).where(FlowTemplate.id == template_id))).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    # 组织隔离：非管理员不可查看其他组织的模板
    if not current_user.is_admin() and tpl.organization_id != current_user.organization_id:
        raise AppException(ErrorCode.FORBIDDEN, "无权查看其他组织的模板")

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
    """获取流程模板的文件模板列表 —— 分「已关联」和「可关联」两组，分类和单个模板合并展示"""
    tpl = (await db.execute(
        select(FlowTemplate).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")

    org_id = tpl.organization_id

    # ── 一次性查：本组织所有分类 + 已关联的分类（去重）──
    all_org_cats = (await db.execute(
        select(TemplateCategory).where(
            TemplateCategory.organization_id == org_id,
        ).order_by(TemplateCategory.name)
    )).scalars().all()

    # 已关联分类 ID 集合
    linked_cat_links = (await db.execute(
        select(TemplateDocumentLink.category_id).where(
            TemplateDocumentLink.template_id == template_id,
            TemplateDocumentLink.category_id.isnot(None),
        )
    )).scalars().all()
    linked_cat_id_set = set(linked_cat_links)

    # 一把查所有分类的文档数
    all_cat_ids = [c.id for c in all_org_cats]
    doc_count_map: dict[int, int] = {}
    if all_cat_ids:
        rows = (await db.execute(
            select(TemplateCategoryDocument.category_id, func.count(TemplateCategoryDocument.id))
            .where(TemplateCategoryDocument.category_id.in_(all_cat_ids))
            .group_by(TemplateCategoryDocument.category_id)
        )).all()
        doc_count_map = {cid: cnt for cid, cnt in rows}

    # 拆分为 linked / available
    linked_categories = [
        {"id": c.id, "name": c.name, "description": c.description,
         "document_count": doc_count_map.get(c.id, 0)}
        for c in all_org_cats if c.id in linked_cat_id_set
    ]
    available_categories = [
        {"id": c.id, "name": c.name, "description": c.description,
         "document_count": doc_count_map.get(c.id, 0)}
        for c in all_org_cats if c.id not in linked_cat_id_set
    ]

    # ── 已关联的单个模板 ──
    linked_rows = (await db.execute(
        select(DocumentTemplate).join(
            TemplateDocumentLink, TemplateDocumentLink.document_id == DocumentTemplate.id
        ).where(
            TemplateDocumentLink.template_id == template_id,
            TemplateDocumentLink.document_id.isnot(None),
        ).order_by(DocumentTemplate.created_at.desc())
    )).scalars().all()

    linked_items = [
        DocTemplateItem(
            id=d.id, name=d.name, original_name=d.original_name,
            file_size=d.file_size, file_type=d.file_type, created_at=d.created_at,
        )
        for d in linked_rows
    ]

    # ── 可关联的单个模板（本组织且未关联）──
    linked_doc_ids = {d.id for d in linked_rows}
    available_rows = (await db.execute(
        select(DocumentTemplate).where(
            DocumentTemplate.organization_id == org_id,
            DocumentTemplate.id.notin_(linked_doc_ids) if linked_doc_ids else True,
        ).order_by(DocumentTemplate.created_at.desc())
    )).scalars().all()

    available_items = [
        DocTemplateItem(
            id=d.id, name=d.name, original_name=d.original_name,
            file_size=d.file_size, file_type=d.file_type, created_at=d.created_at,
        )
        for d in available_rows
    ]

    return ApiResponse.ok({
        "linked": [it.model_dump() for it in linked_items],
        "linked_categories": linked_categories,
        "available": [it.model_dump() for it in available_items],
        "available_categories": available_categories,
        "available_variables": _AVAILABLE_VARIABLES,
    })


@router.post("/templates/{template_id}/documents/link")
async def link_document_templates(
    template_id: int,
    body: dict | None = None,  # JSON body: {"doc_ids": [...], "category_ids": [...]}
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """关联文件模板或分类到流程模板 —— 仅本所所长可操作

    请求体（JSON）：
      - doc_ids：关联单个文件模板 ID 列表（可选）
      - category_ids：关联整个分类 ID 列表（可选）

    两者可同时传入。
    """
    require_manager(current_user)

    doc_ids: list[int] = (body or {}).get("doc_ids") or []
    category_ids: list[int] = (body or {}).get("category_ids") or []

    tpl = (await db.execute(
        select(FlowTemplate).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, tpl.organization_id)

    linked_docs = 0
    linked_cats = 0

    # 关联单个文件模板
    if doc_ids:
        for doc_id in set(doc_ids):
            doc = (await db.execute(
                select(DocumentTemplate).where(DocumentTemplate.id == doc_id)
            )).scalar_one_or_none()
            if doc is None or doc.organization_id != tpl.organization_id:
                continue

            existing = (await db.execute(
                select(TemplateDocumentLink).where(
                    TemplateDocumentLink.template_id == template_id,
                    TemplateDocumentLink.document_id == doc_id,
                )
            )).scalar_one_or_none()
            if existing:
                continue

            db.add(TemplateDocumentLink(template_id=template_id, document_id=doc_id))
            linked_docs += 1

    # 关联分类（模板包）
    if category_ids:
        for cat_id in set(category_ids):
            cat = (await db.execute(
                select(TemplateCategory).where(TemplateCategory.id == cat_id)
            )).scalar_one_or_none()
            if cat is None or cat.organization_id != tpl.organization_id:
                continue

            existing = (await db.execute(
                select(TemplateDocumentLink).where(
                    TemplateDocumentLink.template_id == template_id,
                    TemplateDocumentLink.category_id == cat_id,
                )
            )).scalar_one_or_none()
            if existing:
                continue

            db.add(TemplateDocumentLink(template_id=template_id, category_id=cat_id))
            linked_cats += 1

    await db.commit()
    total = linked_docs + linked_cats
    parts = []
    if linked_docs:
        parts.append(f"{linked_docs} 个单模板")
    if linked_cats:
        parts.append(f"{linked_cats} 个分类")
    return ApiResponse.ok(
        {"linked_docs": linked_docs, "linked_categories": linked_cats},
        message=f"已关联 {'、'.join(parts)}" if parts else "无可关联项"
    )


@router.delete("/templates/{template_id}/documents/{link_type}/{link_id}/link")
async def unlink_document_template(
    template_id: int,
    link_type: str,  # "document" | "category"
    link_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """取消文件模板或分类与流程模板的关联 —— 仅本所所长可操作"""
    require_manager(current_user)

    if link_type not in ("document", "category"):
        raise AppException(ErrorCode.BAD_REQUEST, "link_type 必须是 document 或 category")

    tpl = (await db.execute(
        select(FlowTemplate).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "模板不存在")
    require_same_org(current_user, tpl.organization_id)

    if link_type == "document":
        link = (await db.execute(
            select(TemplateDocumentLink).where(
                TemplateDocumentLink.template_id == template_id,
                TemplateDocumentLink.document_id == link_id,
            )
        )).scalar_one_or_none()
    else:
        link = (await db.execute(
            select(TemplateDocumentLink).where(
                TemplateDocumentLink.template_id == template_id,
                TemplateDocumentLink.category_id == link_id,
            )
        )).scalar_one_or_none()

    if link is None:
        raise AppException(ErrorCode.NOT_FOUND, "未关联")

    await db.delete(link)
    await db.commit()
    return ApiResponse.ok(message="已取消关联")


# ─── 批量下载：模板包 ZIP ─────────────────────────────────


@router.get("/templates/{template_id}/download-zip")
async def download_template_zip(
    template_id: int,
    doc_ids: str = Query(..., description="文件模板 ID 逗号分隔，如 1,2,3"),
    instance_id: int = Query(..., description="流程实例 ID，用于填充占位符"),
    node_id: int | None = Query(None, description="指定节点 ID"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """批量填充并打包下载文件模板 ZIP

    从逗号分隔的 doc_ids 列表中读取模板，逐个填充占位符后打包为 ZIP。
    ZIP 文件名使用模板 original_name。

    也支持传入 category_id（分类下的全部模板）：
      传 doc_ids 时用具体模板列表
      传 category_id 时自动获取分类下全部模板
    """
    # 解析 doc_ids
    try:
        ids = [int(x.strip()) for x in doc_ids.split(",") if x.strip()]
    except ValueError:
        raise AppException(ErrorCode.BAD_REQUEST, "doc_ids 格式不正确，需为逗号分隔的数字")

    if not ids:
        raise AppException(ErrorCode.BAD_REQUEST, "至少需要一个文件模板 ID")

    # 验证流程模板存在
    tpl = (await db.execute(
        select(FlowTemplate).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    if tpl is None:
        raise AppException(ErrorCode.NOT_FOUND, "流程模板不存在")

    # 生成 ZIP
    zip_buffer = await batch_fill_and_zip(db, ids, instance_id, node_id)

    # 返回流式响应
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=templates.zip"},
    )


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
    """系统管理员查看所有文件模板 —— 按组织分组，支持按组织/关键词筛选"""
    require_admin(current_user)

    from sqlalchemy import func

    # 基础查询：DocumentTemplate JOIN Organization
    base = (
        select(
            DocumentTemplate.id,
            DocumentTemplate.name,
            DocumentTemplate.original_name,
            DocumentTemplate.file_size,
            DocumentTemplate.file_type,
            DocumentTemplate.created_at,
            DocumentTemplate.organization_id,
            Organization.name.label("organization_name"),
        )
        .join(Organization, DocumentTemplate.organization_id == Organization.id)
    )

    conditions = []
    if organization_id:
        conditions.append(DocumentTemplate.organization_id == organization_id)
    if keyword:
        conditions.append(DocumentTemplate.name.like(f"%{keyword}%"))

    if conditions:
        base = base.where(*conditions)

    # 计数
    count_base = select(func.count(DocumentTemplate.id)).join(
        Organization, DocumentTemplate.organization_id == Organization.id
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
            "organization_id": row[6],
            "organization_name": row[7],
        }
        for row in rows
    ]

    return ApiResponse.ok({"items": items, "total": total, "page": page, "page_size": page_size})


@admin_router.post("/document-templates")
async def admin_upload_document_template(
    file: UploadFile = File(..., description="文件模板（Word .docx / Excel .xlsx，支持 {{占位符}}）"),
    name: str | None = Query(None, description="显示名称，不传则使用原始文件名"),
    organization_id: int = Query(..., description="所属组织 ID"),
    category_ids: str | None = Query(None, description="所属分类 ID 列表，逗号分隔，如 1,2,3"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """系统管理员上传文件模板 —— 归入指定组织，可选归入分类"""
    require_admin(current_user)

    # 校验组织存在
    org = (await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )).scalar_one_or_none()
    if org is None:
        raise AppException(ErrorCode.NOT_FOUND, "组织不存在")

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

    # 存储
    upload_dir = os.path.join(settings.STORAGE_ROOT, settings.STORAGE_DOCUMENT_TEMPLATES_DIR)
    os.makedirs(upload_dir, exist_ok=True)

    ext_stripped = ext.lstrip(".")
    final_type = ext_stripped
    safe_name = f"org{organization_id}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(upload_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    # 旧版 .doc 转换
    final_path = file_path
    if ext in _CONVERT_FORMATS:
        converted = await _convert_doc_to_docx(file_path)
        if converted:
            final_path = converted
            final_type = "docx"
        else:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise AppException(ErrorCode.BAD_REQUEST, "旧版 .doc 文件转换失败，请手动另存为 .docx 后重新上传")

    doc = DocumentTemplate(
        organization_id=organization_id,
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

    # 可选：归入分类
    linked_cats = 0
    if category_ids:
        try:
            cat_id_list = [int(x.strip()) for x in category_ids.split(",") if x.strip()]
            for cat_id in set(cat_id_list):
                cat = (await db.execute(
                    select(TemplateCategory).where(TemplateCategory.id == cat_id)
                )).scalar_one_or_none()
                if cat and cat.organization_id == organization_id:
                    existing = (await db.execute(
                        select(TemplateCategoryDocument).where(
                            TemplateCategoryDocument.category_id == cat_id,
                            TemplateCategoryDocument.document_id == doc.id,
                        )
                    )).scalar_one_or_none()
                    if not existing:
                        db.add(TemplateCategoryDocument(category_id=cat_id, document_id=doc.id))
                        linked_cats += 1
            if linked_cats:
                await db.commit()
        except ValueError:
            pass  # 分类 ID 格式不对则忽略

    return ApiResponse.ok(
        {"id": doc.id, "name": doc.name, "file_type": doc.file_type, "organization_id": doc.organization_id},
        message="文件模板上传成功",
    )


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


# ─── 模板分类（模板包）管理 — 管理员维护 ────────────────────


@admin_router.get("/template-categories")
async def admin_list_categories(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    organization_id: int | None = Query(None, description="按组织筛选"),
    keyword: str | None = Query(None, description="分类名称搜索"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员查看所有分类 —— 支持按组织和关键词筛选"""
    require_admin(current_user)
    result = await list_categories(
        db, organization_id=organization_id,
        page=page, page_size=page_size, keyword=keyword,
    )
    return ApiResponse.ok(result.model_dump())


@admin_router.post("/template-categories")
async def admin_create_category(
    data: TemplateCategoryCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员创建模板分类"""
    require_admin(current_user)
    cat = await create_category(db, data, current_user.id)
    await db.commit()
    return ApiResponse.ok({"id": cat.id, "name": cat.name}, message="分类创建成功")


@admin_router.get("/template-categories/{category_id}")
async def admin_get_category(
    category_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员获取分类详情 —— 含内部文件模板列表"""
    require_admin(current_user)
    detail = await get_category_detail(db, category_id)
    return ApiResponse.ok(detail.model_dump())


# ─── 分类详情（非管理员只读）───

@router.get("/template-categories/{category_id}")
async def get_category_public(
    category_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取分类详情 —— 含内部文件模板列表，仅本组织用户可查看"""
    from app.core.exceptions import AppException
    from app.core.error_codes import ErrorCode
    detail = await get_category_detail(db, category_id)
    # 组织隔离：非管理员只能查看本组织的分类
    if "system_admin" not in current_user.roles and detail.organization_id != current_user.organization_id:
        raise AppException(ErrorCode.FORBIDDEN, "无权查看其他组织的分类")
    return ApiResponse.ok(detail.model_dump())


@admin_router.put("/template-categories/{category_id}")
async def admin_update_category(
    category_id: int,
    data: TemplateCategoryUpdate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员更新分类基本信息"""
    require_admin(current_user)
    cat = await update_category(db, category_id, data)
    await db.commit()
    return ApiResponse.ok({"id": cat.id, "name": cat.name}, message="分类已更新")


@admin_router.delete("/template-categories/{category_id}")
async def admin_delete_category(
    category_id: int,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员删除分类 —— 级联删除与模板的关联"""
    require_admin(current_user)
    await delete_category(db, category_id)
    await db.commit()
    return ApiResponse.ok(message="分类已删除")


@admin_router.post("/template-categories/{category_id}/documents")
async def admin_link_docs_to_category(
    category_id: int,
    data: CategoryDocLinkRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员将文件模板加入分类"""
    require_admin(current_user)
    linked = await link_documents_to_category(db, category_id, data.doc_ids)
    await db.commit()
    return ApiResponse.ok({"linked": linked}, message=f"已加入 {linked} 个文件模板")


@admin_router.delete("/template-categories/{category_id}/documents")
async def admin_unlink_docs_from_category(
    category_id: int,
    data: CategoryDocLinkRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """管理员从分类中移除文件模板（不删除文件模板本身）"""
    require_admin(current_user)
    removed = await unlink_documents_from_category(db, category_id, data.doc_ids)
    await db.commit()
    return ApiResponse.ok({"removed": removed}, message=f"已移除 {removed} 个文件模板")
