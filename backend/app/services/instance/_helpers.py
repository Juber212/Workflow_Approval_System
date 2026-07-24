"""实例服务公共辅助函数"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    FlowTemplate,
    InstanceNode,
    User,
)



async def _get_type_label(db: AsyncSession, template_id: int) -> str:
    """根据模板 ID 返回中文类型标签：'项目' 或 '方案'"""
    tpl_type = (await db.execute(
        select(FlowTemplate.type).where(FlowTemplate.id == template_id)
    )).scalar_one_or_none()
    return "方案" if tpl_type == "proposal" else "项目"



async def _batch_get_node_stats(db: AsyncSession, instance_ids: list[int]) -> dict[int, dict]:
    """批量查询实例节点统计（替代逐条 N+1）"""
    if not instance_ids:
        return {}
    stmt = select(
        InstanceNode.instance_id,
        func.count(InstanceNode.id).label("total"),
        func.sum(
            func.if_(func.lower(InstanceNode.status) == "finished", 1, 0)
        ).label("processed"),
    ).where(
        InstanceNode.instance_id.in_(instance_ids),
        InstanceNode.is_start == False,  # 排除开始节点
        InstanceNode.is_end == False,    # 排除结束节点
    ).group_by(InstanceNode.instance_id)

    result = await db.execute(stmt)
    return {
        row.instance_id: {"total": int(row.total or 0), "processed": int(row.processed or 0)}
        for row in result.all()
    }


async def _batch_get_active_node_info(db: AsyncSession, instance_ids: list[int]) -> dict[int, dict]:
    """批量查询实例当前活跃节点的处理人信息（替代逐条 N+1）

    与旧版 _batch_get_current_assignees 不同：
    - 不只查 running 节点，也查 waiting_check/waiting_approval/waiting_endorsement/pending/processing
    - 返回节点状态 + 各类处理人信息，供调用方按状态动态选择显示
    - 最终格式化为 "当前处理人" 列（注意不同节点状态显示不同角色）

    返回结构：{instance_id: {"node_status": str, "assignee_name": str|None,
                          "checker_ids": list[int], "approver_ids": list[int],
                          "endorser_id": int|None, "endorser_name": str|None}}
    """
    if not instance_ids:
        return {}

    # 活跃状态：排除 finished / terminated / waiting（等待上游尚未激活）
    active_statuses = ["running", "pending", "processing",
                       "waiting_check", "waiting_approval", "waiting_endorsement"]

    # 查询每个实例的第一个活跃工作节点（按 sort_order 升序）
    stmt = (
        select(InstanceNode)
        .where(
            InstanceNode.instance_id.in_(instance_ids),
            InstanceNode.is_start == False,
            InstanceNode.is_end == False,
            InstanceNode.status.in_(active_statuses),
        )
        .order_by(InstanceNode.instance_id, InstanceNode.sort_order)
    )
    result = await db.execute(stmt)
    all_active_nodes = result.scalars().all()

    # 每个实例只保留 sort_order 最小的活跃节点
    node_by_instance: dict[int, InstanceNode] = {}
    for node in all_active_nodes:
        if node.instance_id not in node_by_instance:
            node_by_instance[node.instance_id] = node

    # 收集所有需要查姓名的 user_id
    assignee_ids: set[int] = set()
    endorser_ids: set[int] = set()
    all_checker_ids: set[int] = set()
    all_approver_ids: set[int] = set()

    for node in node_by_instance.values():
        if node.assignee_id:
            assignee_ids.add(node.assignee_id)
        if node.endorser_id:
            endorser_ids.add(node.endorser_id)
        if node.checkers:
            for c in node.checkers:
                uid = c.get("user_id") if isinstance(c, dict) else c
                if uid:
                    all_checker_ids.add(uid)
        if node.approvers:
            for a in node.approvers:
                uid = a.get("user_id") if isinstance(a, dict) else a
                if uid:
                    all_approver_ids.add(uid)

    # 批量查用户名
    all_user_ids = assignee_ids | endorser_ids | all_checker_ids | all_approver_ids
    user_name_map: dict[int, str] = {}
    if all_user_ids:
        users_result = await db.execute(
            select(User.id, User.real_name).where(User.id.in_(list(all_user_ids)))
        )
        user_name_map = {uid: name for uid, name in users_result.all()}

    # 组装返回
    info_map: dict[int, dict] = {}
    for inst_id, node in node_by_instance.items():
        checker_ids = []
        if node.checkers:
            for c in node.checkers:
                uid = c.get("user_id") if isinstance(c, dict) else c
                if uid:
                    checker_ids.append(uid)

        approver_ids = []
        if node.approvers:
            for a in node.approvers:
                uid = a.get("user_id") if isinstance(a, dict) else a
                if uid:
                    approver_ids.append(uid)

        info_map[inst_id] = {
            "node_status": node.status.lower() if node.status else "running",
            "assignee_name": user_name_map.get(node.assignee_id) if node.assignee_id else None,
            "checker_ids": checker_ids,
            "approver_ids": approver_ids,
            "endorser_id": node.endorser_id,
            "endorser_name": user_name_map.get(node.endorser_id) if node.endorser_id else None,
        }

    return info_map


def format_current_handlers(node_info: dict | None) -> str:
    """根据节点状态和人员信息，生成"当前处理人"列显示文本

    显示规则：
    - running / pending / processing → "张三"（负责人姓名）
    - waiting_check → "李四等3人"（校验人列表，取首人姓名 + 等N人）
    - waiting_approval → "王五等2人"（审批人列表，取首人姓名 + 等N人）
    - waiting_endorsement → "赵六"（批准人姓名）
    - 其他状态或 node_info 为空 → "—"
    """
    if not node_info:
        return "—"

    status = node_info.get("node_status", "")
    assignee_name = node_info.get("assignee_name") or ""
    checker_ids = node_info.get("checker_ids") or []
    approver_ids = node_info.get("approver_ids") or []
    endorser_name = node_info.get("endorser_name") or ""

    if status in ("running", "pending", "processing"):
        return assignee_name or "—"

    if status == "waiting_check":
        if not checker_ids:
            return "—"
        cnt = len(checker_ids)
        # 首人姓名从外部传入（需要 user_name_map），此处仅使用已知信息
        first_name = node_info.get("checker_first_name", "")
        if cnt == 1:
            return first_name or "—"
        return f"{first_name}等{cnt}人" if first_name else f"{cnt}人校验中"

    if status == "waiting_approval":
        if not approver_ids:
            return "—"
        cnt = len(approver_ids)
        first_name = node_info.get("approver_first_name", "")
        if cnt == 1:
            return first_name or "—"
        return f"{first_name}等{cnt}人" if first_name else f"{cnt}人审批中"

    if status == "waiting_endorsement":
        return endorser_name or "—"

    return "—"


def enrich_handler_info_with_names(node_info: dict, user_name_map: dict[int, str]) -> dict:
    """填充 checker/approver 首人姓名到 node_info 中，供 format_current_handlers 使用

    在调用方先批量查好 user_name_map，再调用此函数填充。
    """
    if not node_info:
        return node_info

    checker_ids = node_info.get("checker_ids") or []
    if checker_ids and checker_ids[0] in user_name_map:
        node_info["checker_first_name"] = user_name_map[checker_ids[0]]

    approver_ids = node_info.get("approver_ids") or []
    if approver_ids and approver_ids[0] in user_name_map:
        node_info["approver_first_name"] = user_name_map[approver_ids[0]]

    return node_info


# ==================== 实例详情 ====================



