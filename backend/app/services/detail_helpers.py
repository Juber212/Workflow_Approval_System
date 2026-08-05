"""详情接口公共 helper —— 文件列表 / 用户批量查询 / 节点签批配置

四个详情接口（任务/校验/审批/批准）重复逻辑抽取（P2-3）：
- 实例文件查询 + 所属节点名称映射（原四处逐字重复）
- 文件序列化（各接口字段集不同，参数控制，响应逐字节不变）
- 用户批量查询 + 真实姓名提取（原四处重复的三元表达式）
- 节点签名位置（signature_x/y/page）与签名图片 URL 拼接
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File, InstanceNode, User


async def is_instance_participant(db: AsyncSession, instance, user_id: int) -> bool:
    """判断用户是否为流程实例参与者（发起人/节点负责人/校验人/审批人/批准人）

    产品规则：跨所协作下参与者可跨所访问实例文件/模板包，下载前须校验参与者身份。
    （从 templates.py 提升为公共 helper，第七轮审查 M7 供文件下载复用）
    """
    if instance.initiator_id == user_id:
        return True

    def _contains_user(role_list) -> bool:
        """兼容 checkers/approvers 数组元素为 int 或 dict 两种历史格式"""
        for item in role_list or []:
            if isinstance(item, dict):
                if item.get("user_id") == user_id:
                    return True
            elif item == user_id:
                return True
        return False

    nodes = (await db.execute(
        select(InstanceNode).where(InstanceNode.instance_id == instance.id)
    )).scalars().all()
    for node in nodes:
        if node.assignee_id == user_id or node.endorser_id == user_id:
            return True
        if _contains_user(node.checkers) or _contains_user(node.approvers):
            return True
    return False


async def load_instance_files(db: AsyncSession, instance_id: int) -> tuple[list[File], dict[int, str]]:
    """查询实例全部文件 + 文件所属节点名称映射（一次 IN 查询）"""
    files = (await db.execute(
        select(File).where(File.instance_id == instance_id).order_by(File.node_id, File.id.desc())
    )).scalars().all()

    # 批量查询文件所属节点名称
    file_node_ids = list(set(f.node_id for f in files if f.node_id))
    file_node_names: dict[int, str] = {}
    if file_node_ids:
        fn_result = await db.execute(
            select(InstanceNode.id, InstanceNode.name).where(InstanceNode.id.in_(file_node_ids))
        )
        file_node_names = {row[0]: row[1] for row in fn_result.all()}
    return files, file_node_names


def serialize_files(
    files: list[File],
    file_node_names: dict[int, str],
    *,
    node_id: int | None = None,
    with_upload_meta: bool = False,
    with_folder: bool = False,
    with_conversion: bool = False,
) -> list[dict]:
    """序列化文件列表（node_id 传入时仅返回该节点文件，供签批预览 node_files）

    基础字段（四个接口均有）：id/original_name/mime_type/file_size/round/node_id/node_name
    with_upload_meta: 追加 uploader_name/upload_type/created_at（任务/校验/审批详情）
    with_folder: 追加 folder_name（仅任务详情，前端文件夹模式依赖）
    with_conversion: 追加 conversion_status（仅任务详情，PDF 转换状态）
    参数组合与各接口原始响应字段逐一对应，保证响应逐字节不变
    """
    items = files if node_id is None else [f for f in files if f.node_id == node_id]
    result: list[dict] = []
    for f in items:
        item = {
            "id": f.id,
            "original_name": f.original_name,
            "mime_type": f.mime_type,
            "file_size": f.file_size,
            "round": f.round,
            "node_id": f.node_id,
            "node_name": file_node_names.get(f.node_id, "") if f.node_id else "",
        }
        if with_upload_meta:
            item["uploader_name"] = ""
            item["upload_type"] = f.upload_type
            item["created_at"] = f.created_at.isoformat() if f.created_at else None
        if with_folder:
            item["folder_name"] = f.folder_name
        if with_conversion:
            item["conversion_status"] = f.conversion_status or "ready"
        result.append(item)
    return result


async def fetch_users_map(db: AsyncSession, user_ids: set[int]) -> dict[int, User]:
    """批量查询用户，返回 id → User 映射（自动剔除 None）"""
    ids = {uid for uid in user_ids if uid is not None}
    if not ids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(ids)))
    return {u.id: u for u in result.scalars().all()}


def user_name(users_map: dict[int, User], user_id: int) -> str:
    """取用户真实姓名（空安全，替代四处重复的三元表达式）"""
    u = users_map.get(user_id)
    return u.real_name if u else ""


def node_signature_position(node) -> dict:
    """节点签名默认位置（x/y/page）—— 四个详情接口重复"""
    return {
        "signature_x": node.signature_x,
        "signature_y": node.signature_y,
        "signature_page": node.signature_page,
    }


def signature_image_url(user: User | None) -> str | None:
    """用户签名图片 URL（未上传签名返回 None）"""
    if user and user.signature_image:
        return f"/api/v1/auth/users/{user.id}/signature-image"
    return None
