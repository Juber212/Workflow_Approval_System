"""模板分类（模板包）业务逻辑 —— 按组织隔离的模板分类管理

支持：
  - 分类 CRUD（管理员创建/编辑/删除）
  - 文件模板与分类的多对多关联
  - 批量 ZIP 下载（填充占位符后打包）
"""

import io
import os
import re
import zipfile
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode


def _safe_zip_name(name: str) -> str:
    """清洗 ZIP 条目名，防 Zip Slip 路径穿越（M5）

    只保留 basename，把路径分隔符/穿越段/Windows 保留字符替换为下划线。
    上传的 original_name 可能含路径穿越段（../ 或 ..\\）或完整盘符路径，
    直接作 ZIP 条目名会被解压到目录之外或破坏解压。
    """
    base = os.path.basename((name or "").replace("\\", "/"))
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", base)
    return safe or "file"
from app.models import (
    TemplateCategory, TemplateCategoryDocument,
    DocumentTemplate, TemplateDocumentLink,
    FlowTemplate, Organization, User,
)
from app.schemas.template import (
    TemplateCategoryCreate, TemplateCategoryUpdate,
    TemplateCategoryItem, TemplateCategoryDetail, DocTemplateItem,
)
from app.schemas.common import PaginatedData
from app.services.document_service import resolve_template_variables, fill_template, get_doc_template_abs_path

logger = logging.getLogger(__name__)


# ─── 分类 CRUD ───


async def list_categories(
    db: AsyncSession, *,
    organization_id: int | None = None,
    page: int = 1, page_size: int = 50,
    keyword: str | None = None,
) -> PaginatedData:
    """分页查询分类列表（按组织隔离，管理员看到全局或筛选）"""
    conditions = []
    if organization_id:
        conditions.append(TemplateCategory.organization_id == organization_id)
    if keyword:
        conditions.append(TemplateCategory.name.like(f"%{keyword}%"))

    base = select(TemplateCategory)
    if conditions:
        base = base.where(*conditions)

    count_base = select(func.count()).select_from(TemplateCategory)
    if conditions:
        count_base = count_base.where(*conditions)
    total = (await db.execute(count_base)).scalar() or 0

    stmt = base.order_by(TemplateCategory.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    categories = result.scalars().all()

    if not categories:
        return PaginatedData(items=[], total=total, page=page, page_size=page_size)

    cat_ids = [c.id for c in categories]

    # 批量：组织名
    org_ids = list(set(c.organization_id for c in categories))
    org_rows = (await db.execute(select(Organization.id, Organization.name).where(Organization.id.in_(org_ids)))).all()
    org_map = {oid: name for oid, name in org_rows}

    # 批量：创建人名
    creator_ids = list(set(c.created_by for c in categories))
    creator_rows = (await db.execute(select(User.id, User.real_name).where(User.id.in_(creator_ids)))).all()
    creator_map = {uid: name for uid, name in creator_rows}

    # 批量：每个分类下的模板数量
    doc_count_stmt = (
        select(TemplateCategoryDocument.category_id, func.count(TemplateCategoryDocument.id))
        .where(TemplateCategoryDocument.category_id.in_(cat_ids))
        .group_by(TemplateCategoryDocument.category_id)
    )
    doc_count_rows = (await db.execute(doc_count_stmt)).all()
    doc_count_map = {cid: cnt for cid, cnt in doc_count_rows}

    items = [
        TemplateCategoryItem(
            id=c.id,
            organization_id=c.organization_id,
            organization_name=org_map.get(c.organization_id),
            name=c.name,
            description=c.description,
            document_count=doc_count_map.get(c.id, 0),
            created_by=c.created_by,
            created_by_name=creator_map.get(c.created_by),
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in categories
    ]
    return PaginatedData(items=items, total=total, page=page, page_size=page_size)


async def create_category(db: AsyncSession, data: TemplateCategoryCreate, user_id: int) -> TemplateCategory:
    """创建模板分类"""
    # 校验组织存在
    org = (await db.execute(
        select(Organization).where(Organization.id == data.organization_id)
    )).scalar_one_or_none()
    if org is None:
        raise AppException(ErrorCode.NOT_FOUND, "组织不存在")

    cat = TemplateCategory(
        organization_id=data.organization_id,
        name=data.name,
        description=data.description,
        created_by=user_id,
    )
    db.add(cat)
    await db.flush()
    return cat


async def update_category(db: AsyncSession, category_id: int, data: TemplateCategoryUpdate) -> TemplateCategory:
    """更新分类基本信息"""
    cat = (await db.execute(
        select(TemplateCategory).where(TemplateCategory.id == category_id)
    )).scalar_one_or_none()
    if cat is None:
        raise AppException(ErrorCode.NOT_FOUND, "分类不存在")

    cat.name = data.name
    cat.description = data.description
    await db.flush()
    return cat


async def delete_category(db: AsyncSession, category_id: int) -> None:
    """删除分类 —— 级联删除与模板的关联"""
    cat = (await db.execute(
        select(TemplateCategory).where(TemplateCategory.id == category_id)
    )).scalar_one_or_none()
    if cat is None:
        raise AppException(ErrorCode.NOT_FOUND, "分类不存在")
    await db.delete(cat)
    await db.flush()


async def get_category_detail(db: AsyncSession, category_id: int) -> TemplateCategoryDetail:
    """获取分类详情 —— 含内部文件模板列表"""
    cat = (await db.execute(
        select(TemplateCategory).where(TemplateCategory.id == category_id)
    )).scalar_one_or_none()
    if cat is None:
        raise AppException(ErrorCode.NOT_FOUND, "分类不存在")

    # 组织名
    org_name = (await db.execute(
        select(Organization.name).where(Organization.id == cat.organization_id)
    )).scalar_one_or_none()

    # 创建人名
    creator_name = (await db.execute(
        select(User.real_name).where(User.id == cat.created_by)
    )).scalar_one_or_none()

    # 分类下的文件模板
    doc_rows = (await db.execute(
        select(DocumentTemplate).join(
            TemplateCategoryDocument, TemplateCategoryDocument.document_id == DocumentTemplate.id
        ).where(
            TemplateCategoryDocument.category_id == category_id,
        ).order_by(DocumentTemplate.created_at.desc())
    )).scalars().all()

    documents = [
        DocTemplateItem(
            id=d.id, name=d.name, original_name=d.original_name,
            file_size=d.file_size, file_type=d.file_type, created_at=d.created_at,
        )
        for d in doc_rows
    ]

    return TemplateCategoryDetail(
        id=cat.id,
        organization_id=cat.organization_id,
        organization_name=org_name,
        name=cat.name,
        description=cat.description,
        document_count=len(documents),
        created_by=cat.created_by,
        created_by_name=creator_name,
        created_at=cat.created_at,
        updated_at=cat.updated_at,
        documents=documents,
    )


# ─── 分类 ↔ 文件模板 关联 ───


async def link_documents_to_category(
    db: AsyncSession, category_id: int, doc_ids: list[int],
) -> int:
    """将文件模板关联到分类（跳过已存在和跨组织的）"""
    cat = (await db.execute(
        select(TemplateCategory).where(TemplateCategory.id == category_id)
    )).scalar_one_or_none()
    if cat is None:
        raise AppException(ErrorCode.NOT_FOUND, "分类不存在")

    linked = 0
    for doc_id in set(doc_ids):
        doc = (await db.execute(
            select(DocumentTemplate).where(DocumentTemplate.id == doc_id)
        )).scalar_one_or_none()
        if doc is None or doc.organization_id != cat.organization_id:
            continue

        existing = (await db.execute(
            select(TemplateCategoryDocument).where(
                TemplateCategoryDocument.category_id == category_id,
                TemplateCategoryDocument.document_id == doc_id,
            )
        )).scalar_one_or_none()
        if existing:
            continue

        db.add(TemplateCategoryDocument(category_id=category_id, document_id=doc_id))
        linked += 1

    await db.flush()
    return linked


async def unlink_documents_from_category(
    db: AsyncSession, category_id: int, doc_ids: list[int],
) -> int:
    """从分类中移除文件模板"""
    removed = 0
    for doc_id in set(doc_ids):
        link = (await db.execute(
            select(TemplateCategoryDocument).where(
                TemplateCategoryDocument.category_id == category_id,
                TemplateCategoryDocument.document_id == doc_id,
            )
        )).scalar_one_or_none()
        if link:
            await db.delete(link)
            removed += 1

    await db.flush()
    return removed


# ─── 批量 ZIP 下载 ───


async def batch_fill_and_zip(
    db: AsyncSession,
    doc_ids: list[int],
    instance_id: int,
    node_id: int | None = None,
) -> io.BytesIO:
    """批量填充模板占位符并打包为 ZIP。

    对每个模板：通过该流程实例的某个 Task 解析占位符 → 填充 → 加入 ZIP。
    返回内存中的 ZIP BytesIO 对象。

    参数：
      - doc_ids：要下载的文件模板 ID 列表
      - instance_id：流程实例 ID，用于解析占位符
      - node_id：可选，指定节点 ID（用于 resolve_template_variables）
    """
    from app.models import FlowInstance, Task, InstanceNode

    instance = (await db.execute(
        select(FlowInstance).where(FlowInstance.id == instance_id)
    )).scalar_one_or_none()
    if instance is None:
        raise AppException(ErrorCode.NOT_FOUND, "流程实例不存在")

    # 找到该实例下任意一个 Task 用于解析占位符
    task = None
    if node_id:
        task = (await db.execute(
            select(Task).where(Task.instance_id == instance_id, Task.node_id == node_id)
        )).scalars().first()
    if task is None:
        # 取该实例下任意 Task
        task = (await db.execute(
            select(Task).where(Task.instance_id == instance_id).order_by(Task.id)
        )).scalars().first()
    if task is None:
        raise AppException(ErrorCode.NOT_FOUND, "该实例下无可用任务，无法解析模板变量")

    # 创建内存 ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc_id in doc_ids:
            doc = (await db.execute(
                select(DocumentTemplate).where(DocumentTemplate.id == doc_id)
            )).scalar_one_or_none()
            if doc is None:
                logger.warning(f"批量下载：文件模板 {doc_id} 不存在，跳过")
                continue

            try:
                # 解析占位符
                replacements = await resolve_template_variables(db, doc.id, task.id)
                # 填充模板
                abs_path = get_doc_template_abs_path(doc)
                file_stream = fill_template(abs_path, doc.file_type, replacements)
                # 写入 ZIP（M5：条目名清洗防 Zip Slip，文件名保持原始名语义）
                zf.writestr(_safe_zip_name(doc.original_name), file_stream.read())
            except Exception as e:
                logger.warning(f"批量下载：文件模板 {doc.name} 填充失败：{e}，跳过")
                continue

    zip_buffer.seek(0)
    return zip_buffer
