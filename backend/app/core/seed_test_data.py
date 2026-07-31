"""测试数据种子脚本 —— 覆盖全边界场景，幂等可重复运行

运行方式（在 backend 目录下执行）：
  python -m app.core.seed_test_data

所有测试数据带 [测试] 前缀标记。
脚本运行时会先清理已有测试数据，再重新插入（幂等）。
不会影响原始 seed.py 产生的数据。
"""

import asyncio
from datetime import datetime, timedelta
from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models import (
    Organization, User, UserRole, Role,
    FlowTemplate, TemplateNode, TemplateEdge,
    FlowInstance, InstanceNode, InstanceEdge,
    Task, CheckRecord, Approval, Endorsement,
)
from sqlalchemy import select, text

# ════════════════════════════════════════════
# 常量
# ════════════════════════════════════════════
PREFIX = "[测试]"
TEST_PASSWORD = "test123"
NOW = datetime.now()

# 组织占位符 —— 运行时从数据库动态获取实际组织名称后替换
# __ORG_A__, __ORG_B__, __ORG_C__, __ORG_D__

# ════════════════════════════════════════════
# 测试用户定义
# ════════════════════════════════════════════
# (username, real_name, role_code, org_key)
# org_key 映射: org_a/org_b/org_c/org_d → 数据库中的第1/2/3/4个组织
TEST_USERS = [
    ("[测试]zhang_suo",  "[测试]张所长", "manager",       "org_a"),
    ("[测试]li_suo",     "[测试]李所长", "manager",       "org_b"),
    ("[测试]wang_gong",  "[测试]王工",   "user",          "org_a"),
    ("[测试]zhao_gong",  "[测试]赵工",   "user",          "org_a"),
    ("[测试]qian_gong",  "[测试]钱工",   "user",          "org_b"),
    ("[测试]sun_gong",   "[测试]孙工",   "user",          "org_c"),
    ("[测试]zhou_gong",  "[测试]周工",   "user",          "org_d"),
    ("[测试]wu_jianyan", "[测试]吴校验", "user",          "org_a"),
    ("[测试]zheng_shenpi","[测试]郑审批","user",          "org_b"),
]

# ════════════════════════════════════════════
# 辅助：快捷创建节点定义
# ════════════════════════════════════════════
def _n(name, assignee=None, checker=None, approver=None, endorser=None,
       is_start=False, is_end=False, days=3, strategy="all_approve",
       need_sign=True, sort=None):
    """快捷创建节点定义

    sort: 可选的自定义排序序号。并行节点应设为相同值，以便进度条识别分叉/汇合。
          未指定则按节点在列表中的位置自动分配。
    """
    return dict(
        name=name, is_start=is_start, is_end=is_end,
        assignee=assignee, checker=checker, approver=approver, endorser=endorser,
        days=days, strategy=strategy, need_sign=need_sign, sort=sort,
    )


# ════════════════════════════════════════════
# 构建模板定义（运行时用实际组织名替换 __ORG_X__）
# ════════════════════════════════════════════
def build_templates_def(org_a: str, org_b: str, org_c: str, org_d: str) -> list:
    """用实际组织名称构建模板定义列表

    org_a/org_b/org_c/org_d 来自于数据库查询结果，按 ID 排序取前 4 个。
    """
    return [
        {
            "name": f"{PREFIX}标准项目流程-{org_a}",
            "type": "project",
            "org_key": "org_a",
            "created_by_user": "[测试]zhang_suo",
            "nodes": [
                _n("开始", is_start=True),
                _n("需求分析", assignee="[测试]wang_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", days=3, strategy="all_approve"),
                _n("方案设计", assignee="[测试]zhao_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", days=5, strategy="all_approve"),
                _n("审核确认", assignee="[测试]wang_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", days=2, strategy="all_approve"),
                _n("结束", is_end=True),
            ],
            "edges": [(0, 1), (1, 2), (2, 3), (3, 4)],
        },
        {
            "name": f"{PREFIX}高难度四级流程-{org_a}",
            "type": "project",
            "org_key": "org_a",
            "created_by_user": "[测试]zhang_suo",
            "nodes": [
                _n("开始", is_start=True),
                _n("关键设计", assignee="[测试]zhao_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", endorser="[测试]wang_gong",
                   days=7, strategy="all_approve"),
                _n("最终审核", assignee="[测试]wang_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", endorser="[测试]wang_gong",
                   days=5, strategy="all_approve"),
                _n("结束", is_end=True),
            ],
            "edges": [(0, 1), (1, 2), (2, 3)],
        },
        {
            "name": f"{PREFIX}快速审批流程-{org_b}",
            "type": "project",
            "org_key": "org_b",
            "created_by_user": "[测试]li_suo",
            "nodes": [
                _n("开始", is_start=True),
                _n("快速任务", assignee="[测试]qian_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", days=1, strategy="single_approve"),
                _n("结束", is_end=True),
            ],
            "edges": [(0, 1), (1, 2)],
        },
        {
            "name": f"{PREFIX}并行审查流程-{org_a}",
            "type": "project",
            "org_key": "org_a",
            "created_by_user": "[测试]zhang_suo",
            "nodes": [
                _n("开始", is_start=True),
                _n("并行任务A", assignee="[测试]wang_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", days=3, strategy="all_approve", sort=1),
                _n("并行任务B", assignee="[测试]zhao_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", days=3, strategy="all_approve", sort=1),
                _n("汇合审查", assignee="[测试]wang_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", days=2, strategy="all_approve", sort=2),
                _n("结束", is_end=True, sort=3),
            ],
            # N1 分叉到 N2、N3（sort 同为 1），然后都汇合到 N4（sort=2），再到 N5
            "edges": [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)],
        },
        {
            "name": f"{PREFIX}标准方案流程-{org_a}",
            "type": "proposal",
            "org_key": "org_a",
            "created_by_user": "[测试]zhang_suo",
            "nodes": [
                _n("开始", is_start=True),
                _n("方案编制", assignee="[测试]wang_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", days=5, strategy="all_approve"),
                _n("方案评审", assignee="[测试]zhao_gong", checker="[测试]wu_jianyan",
                   approver="[测试]zheng_shenpi", days=3, strategy="all_approve"),
                _n("结束", is_end=True),
            ],
            "edges": [(0, 1), (1, 2), (2, 3)],
        },
    ]


# ════════════════════════════════════════════
# 测试实例定义
# ════════════════════════════════════════════
# 每个实例: (name, template_index, status, priority, difficulty, scenario, extra)
# template_index = templates_def 的下标
# scenario 决定节点/任务/校验/审批的状态
# extra: deadline_offset_days / round / termination_reason
INSTANCES_DEF = [
    # ── 状态边界（4条） ──
    ("[测试]已创建-待发起",        0, "created",    "normal", "1", "created",        {}),
    ("[测试]运行中-正常",          0, "running",    "normal", "1", "running_mid",    {}),
    ("[测试]已完成-正常",          0, "completed",  "normal", "1", "completed",      {}),
    ("[测试]已终止-手动终止",      0, "terminated", "normal", "1", "terminated",
        {"termination_reason": "测试终止原因：项目取消"}),

    # ── 优先级边界（3条） ──
    ("[测试]运行中-紧急优先级",    0, "running",    "urgent", "1", "running_mid",    {}),
    ("[测试]运行中-高优先级",      0, "running",    "high",   "1", "running_mid",    {}),
    ("[测试]运行中-低优先级",      0, "running",    "low",    "1", "running_mid",    {}),

    # ── 难度边界（4条） ──
    ("[测试]运行中-难度1",         0, "running",    "normal", "1", "running_mid",    {}),
    ("[测试]运行中-难度2",         0, "running",    "normal", "2", "running_mid",    {}),
    ("[测试]运行中-难度3",         0, "running",    "normal", "3", "running_mid",    {}),
    ("[测试]运行中-难度4-需批准",  1, "running",    "normal", "4", "running_endorsement", {}),

    # ── 时间边界（3条） ──
    ("[测试]临期-1天内到期",       0, "running",    "high",   "1", "running_mid",
        {"deadline_offset_days": 1}),
    ("[测试]逾期-已超期",          2, "running",    "urgent", "1", "running_mid",
        {"deadline_offset_days": -3}),
    ("[测试]逾期-严重超期",        0, "running",    "urgent", "2", "running_approval",
        {"deadline_offset_days": -10}),

    # ── 审批策略（1条） ──
    ("[测试]运行中-一人通过策略",   2, "running",    "normal", "1", "running_approval", {}),

    # ── 驳回多轮（2条） ──
    ("[测试]运行中-驳回后重做-第2轮", 0, "running",  "high",   "2", "running_mid",
        {"round": 2}),
    ("[测试]运行中-多次驳回-第3轮",   0, "running",  "urgent", "3", "running_check",
        {"round": 3}),

    # ── 并行/跨组织/方案（4条） ──
    ("[测试]运行中-并行审查",      3, "running",    "normal", "2", "running_fork",    {}),
    ("[测试]运行中-跨组织协作",    0, "running",    "normal", "1", "running_mid",    {}),
    ("[测试]已完成-方案类型",      4, "completed",  "high",   "3", "completed",      {}),
    ("[测试]已完成-难度4-含批准",  1, "completed",  "normal", "4", "completed",      {}),

    # ── 终止类（1条） ──
    ("[测试]已终止-紧急终止",      0, "terminated", "urgent", "2", "terminated",
        {"termination_reason": "紧急终止：需求变更"}),
]


# ════════════════════════════════════════════
# 动态组织映射
# ════════════════════════════════════════════
async def get_org_mapping(session) -> dict:
    """从数据库获取实际组织，按 ID 排序，映射到 org_a/org_b/org_c/org_d

    返回: {"org_a": org_id, "org_b": org_id, ...} 和 {"org_a": org_name, ...}
    """
    result = await session.execute(
        select(Organization.id, Organization.name).order_by(Organization.id)
    )
    orgs = result.fetchall()

    if len(orgs) < 2:
        raise RuntimeError(
            f"数据库至少需要 2 个组织（当前 {len(orgs)} 个），请先运行 seed.py"
        )

    keys = ["org_a", "org_b", "org_c", "org_d"]
    org_ids = {}
    org_names = {}

    for i, key in enumerate(keys):
        if i < len(orgs):
            org_ids[key] = orgs[i][0]
            org_names[key] = orgs[i][1]
        else:
            # 组织不够，复用最后一个
            org_ids[key] = orgs[-1][0]
            org_names[key] = orgs[-1][1]

    return org_ids, org_names


# ════════════════════════════════════════════
# 清理
# ════════════════════════════════════════════
async def cleanup_test_data(session):
    """清理所有带 [测试] 前缀的数据（按外键依赖逆序删除）"""
    # Step 1: 查出所有测试实例/模板/用户 ID
    result = await session.execute(
        select(FlowInstance.id).where(FlowInstance.name.like(f"{PREFIX}%"))
    )
    test_instance_ids = [row[0] for row in result.fetchall()]

    result = await session.execute(
        select(FlowTemplate.id).where(FlowTemplate.name.like(f"{PREFIX}%"))
    )
    test_template_ids = [row[0] for row in result.fetchall()]

    result = await session.execute(
        select(User.id).where(User.username.like(f"{PREFIX}%"))
    )
    test_user_ids = [row[0] for row in result.fetchall()]

    # Step 2: 临时关闭外键检查，按任意顺序删除后重新开启
    # （测试脚本专用，避免处理复杂的 FK 依赖链）
    await session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

    try:
        for table_name, col, ids in [
            ("endorsements", "instance_id", test_instance_ids),
            ("approvals", "instance_id", test_instance_ids),
            ("check_records", "instance_id", test_instance_ids),
            ("tasks", "instance_id", test_instance_ids),
            ("files", "instance_id", test_instance_ids),
            ("notifications", "user_id", test_user_ids),
            ("operation_logs", "instance_id", test_instance_ids),
            ("instance_edges", "instance_id", test_instance_ids),
            ("instance_nodes", "instance_id", test_instance_ids),
            ("flow_instances", "id", test_instance_ids),
            ("template_edges", "template_id", test_template_ids),
            ("template_nodes", "template_id", test_template_ids),
            ("flow_templates", "id", test_template_ids),
            ("user_roles", "user_id", test_user_ids),
            ("users", "id", test_user_ids),
        ]:
            if not ids:
                continue
            placeholders = ",".join([str(int(i)) for i in ids])
            await session.execute(text(
                f"DELETE FROM {table_name} WHERE {col} IN ({placeholders})"
            ))
    finally:
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    if test_user_ids:
        print(f"  已清理 {len(test_user_ids)} 个测试用户")
    if test_template_ids:
        print(f"  已清理 {len(test_template_ids)} 个测试模板")
    if test_instance_ids:
        print(f"  已清理 {len(test_instance_ids)} 个测试实例")


# ════════════════════════════════════════════
# 创建测试用户
# ════════════════════════════════════════════
async def seed_users(session, org_ids: dict) -> dict:
    """创建测试用户，返回 {username: user_id} 映射"""
    user_ids = {}

    # 预查角色
    result = await session.execute(select(Role))
    roles = {role.code: role.id for role in result.scalars()}

    for username, real_name, role_code, org_key in TEST_USERS:
        org_id = org_ids.get(org_key)
        user = User(
            username=username,
            password_hash=hash_password(TEST_PASSWORD),
            real_name=real_name,
            organization_id=org_id,
            must_change_password=False,  # 测试用户跳过首次改密
            is_active=True,
        )
        session.add(user)
        await session.flush()
        user_ids[username] = user.id

        # 分配角色
        session.add(UserRole(user_id=user.id, role_id=roles[role_code]))
        print(f"  + 用户: {real_name} ({role_code})")

    await session.flush()
    return user_ids


# ════════════════════════════════════════════
# 创建测试模板
# ════════════════════════════════════════════
async def seed_templates(session, user_ids: dict, org_ids: dict,
                         org_names: dict) -> list:
    """创建测试模板（含节点和连线），返回模板数据列表"""
    templates_def = build_templates_def(
        org_names["org_a"], org_names["org_b"],
        org_names["org_c"], org_names["org_d"],
    )
    templates_data = []

    for tpl_def in templates_def:
        org_id = org_ids[tpl_def["org_key"]]
        created_by = user_ids[tpl_def["created_by_user"]]

        # 创建模板
        tpl = FlowTemplate(
            name=tpl_def["name"],
            description=f"测试模板 —— {tpl_def['type']}类型",
            type=tpl_def["type"],
            organization_id=org_id,
            created_by=created_by,
        )
        session.add(tpl)
        await session.flush()

        # 创建节点（sort_order 优先用自定义 sort，否则用列表索引）
        tpl_nodes = []
        for i, nd in enumerate(tpl_def["nodes"]):
            node = TemplateNode(
                template_id=tpl.id,
                name=nd["name"],
                is_start=nd["is_start"],
                is_end=nd["is_end"],
                assignee_id=user_ids.get(nd["assignee"]) if nd["assignee"] else None,
                time_limit_days=nd["days"] if not nd["is_start"] and not nd["is_end"] else None,
                require_file=not nd["is_start"] and not nd["is_end"],
                checkers=[{"id": user_ids[nd["checker"]], "name": nd["checker"]}]
                    if nd["checker"] else None,
                approvers=[{"id": user_ids[nd["approver"]], "name": nd["approver"]}]
                    if nd["approver"] else None,
                approval_strategy=nd["strategy"],
                endorser_id=user_ids.get(nd["endorser"]) if nd["endorser"] else None,
                require_assignee_signature=nd["need_sign"] and not nd["is_start"] and not nd["is_end"],
                require_checker_signature=nd["need_sign"] and not nd["is_start"] and not nd["is_end"],
                require_approver_signature=nd["need_sign"] and not nd["is_start"] and not nd["is_end"],
                require_endorser_signature=bool(nd["endorser"]),
                sort_order=nd.get("sort", i),  # 自定义 sort 或默认列表索引
                position_x=100 + i * 200,
                position_y=300,
            )
            session.add(node)
            tpl_nodes.append(node)

        await session.flush()

        # 创建连线
        for src_idx, tgt_idx in tpl_def["edges"]:
            edge = TemplateEdge(
                template_id=tpl.id,
                source_node_id=tpl_nodes[src_idx].id,
                target_node_id=tpl_nodes[tgt_idx].id,
            )
            session.add(edge)

        await session.flush()

        templates_data.append({
            "id": tpl.id,
            "name": tpl_def["name"],
            "type": tpl_def["type"],
            "org_key": tpl_def["org_key"],
            "nodes": [{
                "id": n.id, "name": n.name, "is_start": n.is_start, "is_end": n.is_end,
                "assignee_id": n.assignee_id, "checkers": n.checkers,
                "approvers": n.approvers, "endorser_id": n.endorser_id,
                "approval_strategy": n.approval_strategy,
                "time_limit_days": n.time_limit_days,
                "sort_order": n.sort_order,  # 并行节点识别关键字段
                "require_assignee_signature": n.require_assignee_signature,
                "require_checker_signature": n.require_checker_signature,
                "require_approver_signature": n.require_approver_signature,
                "require_endorser_signature": n.require_endorser_signature,
            } for n in tpl_nodes],
            "edges": tpl_def["edges"],
        })
        print(f"  + 模板: {tpl_def['name']} [{tpl_def['type']}] ({len(tpl_nodes)}节点)")

    return templates_data


# ════════════════════════════════════════════
# 辅助：创建实例节点
# ════════════════════════════════════════════
def _copy_node(instance_id: int, tpl_node: dict, sort_order: int,
               deadline: datetime | None = None) -> InstanceNode:
    """从模板节点数据创建实例节点"""
    return InstanceNode(
        instance_id=instance_id,
        name=tpl_node["name"],
        is_start=tpl_node["is_start"],
        is_end=tpl_node["is_end"],
        assignee_id=tpl_node["assignee_id"],
        time_limit_days=tpl_node["time_limit_days"],
        deadline=deadline,
        require_file=bool(tpl_node["time_limit_days"]),
        checkers=tpl_node["checkers"],
        approvers=tpl_node["approvers"],
        approval_strategy=tpl_node["approval_strategy"],
        endorser_id=tpl_node["endorser_id"],
        require_assignee_signature=tpl_node["require_assignee_signature"],
        require_checker_signature=tpl_node["require_checker_signature"],
        require_approver_signature=tpl_node["require_approver_signature"],
        require_endorser_signature=tpl_node["require_endorser_signature"],
        status="waiting",
        sort_order=sort_order,
        round=1,
    )


# ════════════════════════════════════════════
# 创建测试实例
# ════════════════════════════════════════════
async def seed_instances(session, user_ids: dict, org_ids: dict,
                         templates_data: list, org_names: dict):
    """创建测试实例及所有关联数据"""
    initiator_id = user_ids["[测试]zhang_suo"]
    org_a_id = org_ids["org_a"]
    org_b_id = org_ids["org_b"]

    instance_count = 0

    for inst_name, tpl_idx, status, priority, difficulty, scenario, extra in INSTANCES_DEF:
        tpl = templates_data[tpl_idx]
        tpl_nodes = tpl["nodes"]
        tpl_edges = tpl["edges"]
        current_round = extra.get("round", 1)
        deadline_offset = extra.get("deadline_offset_days", None)

        # ── 创建 FlowInstance ──
        # 跨组织实例使用 org_b
        inst_org_id = org_b_id if "跨组织" in inst_name else org_a_id

        instance = FlowInstance(
            name=inst_name,
            description=f"边界测试：{scenario} | 优先级{priority} | 难度{difficulty}级",
            template_id=tpl["id"],
            template_name=tpl["name"],
            template_type=tpl["type"],
            organization_id=inst_org_id,
            initiator_id=initiator_id,
            priority=priority,
            difficulty=difficulty,
            status=status,
            termination_reason=extra.get("termination_reason"),
            initiated_at=NOW - timedelta(days=14),
            completed_at=NOW if status == "completed" else None,
            terminated_at=NOW if status == "terminated" else None,
        )
        session.add(instance)
        await session.flush()

        # ── 创建 InstanceNode（使用模板节点的 sort_order，保留并行节点分组）──
        inst_nodes = []
        for i, tpl_node in enumerate(tpl_nodes):
            dl = None
            if deadline_offset is not None and not tpl_node["is_start"] and not tpl_node["is_end"]:
                dl = NOW + timedelta(days=deadline_offset)
            elif tpl_node["time_limit_days"] and not tpl_node["is_start"] and not tpl_node["is_end"]:
                dl = NOW + timedelta(days=tpl_node["time_limit_days"])

            node = _copy_node(instance.id, tpl_node, tpl_node["sort_order"], dl)
            node.round = current_round
            inst_nodes.append(node)
            session.add(node)

        await session.flush()

        # ── 计算并行节点的 incoming_count ──
        for src_idx, tgt_idx in tpl_edges:
            incoming = sum(1 for s, t in tpl_edges if t == tgt_idx)
            if incoming > 1:
                inst_nodes[tgt_idx].incoming_count = incoming

        await session.flush()

        # ── 创建 InstanceEdge ──
        for src_idx, tgt_idx in tpl_edges:
            edge = InstanceEdge(
                instance_id=instance.id,
                source_node_id=inst_nodes[src_idx].id,
                target_node_id=inst_nodes[tgt_idx].id,
            )
            session.add(edge)

        await session.flush()

        # ── 根据 scenario 设置节点/任务/校验/审批状态 ──
        await _apply_scenario(session, instance.id, inst_nodes, tpl_nodes,
                              scenario, current_round, user_ids, difficulty)

        instance_count += 1
        print(f"  + 实例: {inst_name} [{scenario}] pri={priority} diff={difficulty}")

    print(f"\n  共创建 {instance_count} 个测试实例")


# ════════════════════════════════════════════
# 场景应用
# ════════════════════════════════════════════
async def _apply_scenario(session, instance_id: int, inst_nodes: list,
                          tpl_nodes: list, scenario: str, current_round: int,
                          user_ids: dict, difficulty: str):
    """根据场景设置节点状态、任务、校验、审批、批准记录"""

    # 找出工作节点（排除开始和结束节点）
    work_nodes = [(i, n, t) for i, (n, t) in enumerate(zip(inst_nodes, tpl_nodes))
                  if not n.is_start and not n.is_end]
    if not work_nodes:
        return

    start_node = next((n for n in inst_nodes if n.is_start), None)
    end_node = next((n for n in inst_nodes if n.is_end), None)

    if scenario == "created":
        return  # 全部节点 waiting，无 task

    elif scenario == "terminated":
        if start_node:
            start_node.status = "finished"
            start_node.completed_at = NOW - timedelta(days=13)
        if work_nodes:
            n = work_nodes[0][1]
            n.status = "terminated"
            n.started_at = NOW - timedelta(days=12)
            n.completed_at = NOW
            await _make_task(session, instance_id, n.id, n.assignee_id,
                       "terminated", current_round, n.started_at, NOW)
        return

    elif scenario == "completed":
        if start_node:
            start_node.status = "finished"
            start_node.completed_at = NOW - timedelta(days=13)
        for i, (idx, node, tpl) in enumerate(work_nodes):
            node.status = "finished"
            node.started_at = NOW - timedelta(days=12 - i * 3)
            node.completed_at = NOW - timedelta(days=10 - i * 3)

            task = await _make_task(session, instance_id, node.id, node.assignee_id,
                                    "completed", current_round, node.started_at, node.completed_at)

            if tpl["checkers"]:
                checker_id = tpl["checkers"][0]["id"]
                _make_check(session, instance_id, node.id, task.id, checker_id,
                            "passed", current_round, "测试校验通过")

            if tpl["approvers"]:
                approver_id = tpl["approvers"][0]["id"]
                _make_approval(session, instance_id, node.id, task.id, approver_id,
                               "approved", current_round, "测试审批通过")

            if difficulty == "4" and tpl["endorser_id"]:
                _make_endorsement(session, instance_id, node.id, task.id,
                                  tpl["endorser_id"], "approved", current_round,
                                  "测试批准通过")

        if end_node:
            end_node.status = "finished"
            end_node.completed_at = NOW
        return

    elif scenario in ("running_mid", "running_check", "running_approval",
                      "running_endorsement", "running_fork"):
        if start_node:
            start_node.status = "finished"
            start_node.completed_at = NOW - timedelta(days=13)

        # 第一个工作节点已完成
        if len(work_nodes) >= 1:
            n0 = work_nodes[0][1]
            t0 = work_nodes[0][2]
            n0.status = "finished"
            n0.started_at = NOW - timedelta(days=12)
            n0.completed_at = NOW - timedelta(days=9)
            task0 = await _make_task(session, instance_id, n0.id, n0.assignee_id,
                               "completed", current_round, n0.started_at, n0.completed_at, "已完成")
            if t0["checkers"]:
                _make_check(session, instance_id, n0.id, task0.id,
                            t0["checkers"][0]["id"], "passed", current_round, "校验通过")
            if t0["approvers"]:
                _make_approval(session, instance_id, n0.id, task0.id,
                               t0["approvers"][0]["id"], "approved", current_round, "审批通过")
            if difficulty == "4" and t0["endorser_id"]:
                _make_endorsement(session, instance_id, n0.id, task0.id,
                                  t0["endorser_id"], "approved", current_round, "批准通过")

        # 第二个工作节点（当前活跃节点）
        if len(work_nodes) >= 2:
            n1 = work_nodes[1][1]
            t1 = work_nodes[1][2]

            if scenario == "running_mid":
                n1.status = "running"
                n1.started_at = NOW - timedelta(days=2)
                await _make_task(session, instance_id, n1.id, n1.assignee_id,
                           "processing", current_round, n1.started_at, None, "正在处理中…")

            elif scenario == "running_check":
                n1.status = "waiting_check"
                n1.started_at = NOW - timedelta(days=5)
                task1 = await _make_task(session, instance_id, n1.id, n1.assignee_id,
                                   "waiting_check", current_round, n1.started_at,
                                   NOW - timedelta(days=1), "已提交，等待校验")
                if t1["checkers"]:
                    _make_check(session, instance_id, n1.id, task1.id,
                                t1["checkers"][0]["id"], "pending", current_round)

            elif scenario == "running_approval":
                n1.status = "waiting_approval"
                n1.started_at = NOW - timedelta(days=7)
                task1 = await _make_task(session, instance_id, n1.id, n1.assignee_id,
                                   "waiting_approval", current_round, n1.started_at,
                                   NOW - timedelta(days=3), "已提交，校验通过")
                if t1["checkers"]:
                    _make_check(session, instance_id, n1.id, task1.id,
                                t1["checkers"][0]["id"], "passed", current_round, "校验通过")
                if t1["approvers"]:
                    _make_approval(session, instance_id, n1.id, task1.id,
                                   t1["approvers"][0]["id"], "pending", current_round)

            elif scenario == "running_endorsement":
                n1.status = "waiting_endorsement"
                n1.started_at = NOW - timedelta(days=10)
                task1 = await _make_task(session, instance_id, n1.id, n1.assignee_id,
                                   "waiting_endorsement", current_round, n1.started_at,
                                   NOW - timedelta(days=5), "已提交，等待批准")
                if t1["checkers"]:
                    _make_check(session, instance_id, n1.id, task1.id,
                                t1["checkers"][0]["id"], "passed", current_round, "校验通过")
                if t1["approvers"]:
                    _make_approval(session, instance_id, n1.id, task1.id,
                                   t1["approvers"][0]["id"], "approved", current_round, "审批通过")
                if t1["endorser_id"]:
                    _make_endorsement(session, instance_id, n1.id, task1.id,
                                      t1["endorser_id"], "pending", current_round)

            elif scenario == "running_fork":
                n1.status = "running"
                n1.started_at = NOW - timedelta(days=3)
                await _make_task(session, instance_id, n1.id, n1.assignee_id,
                           "processing", current_round, n1.started_at, None, "并行任务A处理中…")

                if len(work_nodes) >= 3:
                    n2 = work_nodes[2][1]
                    n2.status = "running"
                    n2.started_at = NOW - timedelta(days=3)
                    await _make_task(session, instance_id, n2.id, n2.assignee_id,
                               "processing", current_round, n2.started_at, None, "并行任务B处理中…")


# ════════════════════════════════════════════
# 辅助：Task / Check / Approval / Endorsement
# ════════════════════════════════════════════
async def _make_task(session, instance_id: int, node_id: int, assignee_id: int | None,
                     status: str, round_num: int, started_at, completed_at,
                     note: str | None = None) -> Task:
    """创建任务记录（异步，创建后立即 flush 以获取自增 ID）"""
    if assignee_id is None:
        assignee_id = 1
    task = Task(
        instance_id=instance_id, node_id=node_id, assignee_id=assignee_id,
        status=status, assignee_note=note,
        submitted_at=completed_at if status in (
            "waiting_check", "waiting_approval", "waiting_endorsement", "completed"
        ) else None,
        completed_at=completed_at if status == "completed" else None,
        created_at=started_at or NOW,
    )
    session.add(task)
    await session.flush()  # 立即 flush 以获取 task.id，后续 check/approval 依赖此 ID
    return task


def _make_check(session, instance_id: int, node_id: int, task_id: int,
                checker_id: int, status: str, round_num: int,
                opinion: str | None = None) -> CheckRecord:
    check = CheckRecord(
        instance_id=instance_id, node_id=node_id, task_id=task_id,
        checker_id=checker_id, status=status, opinion=opinion, round=round_num,
        decided_at=NOW if status in ("passed", "returned") else None,
    )
    session.add(check)
    return check


def _make_approval(session, instance_id: int, node_id: int, task_id: int,
                   approver_id: int, status: str, round_num: int,
                   opinion: str | None = None) -> Approval:
    approval = Approval(
        instance_id=instance_id, node_id=node_id, task_id=task_id,
        approver_id=approver_id, status=status, opinion=opinion, round=round_num,
        decided_at=NOW if status in ("approved", "rejected") else None,
    )
    session.add(approval)
    return approval


def _make_endorsement(session, instance_id: int, node_id: int, task_id: int,
                      endorser_id: int, status: str, round_num: int,
                      opinion: str | None = None) -> Endorsement:
    endorsement = Endorsement(
        instance_id=instance_id, node_id=node_id, task_id=task_id,
        endorser_id=endorser_id, status=status, opinion=opinion, round=round_num,
        decided_at=NOW if status in ("approved", "rejected") else None,
    )
    session.add(endorsement)
    return endorsement


# ════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════
async def seed():
    """主入口：清理旧数据 → 创建用户 → 模板 → 实例"""
    print("=" * 60)
    print("  测试数据种子脚本")
    print("=" * 60)

    async with async_session_factory() as session:
        # 0. 动态获取组织映射
        org_ids, org_names = await get_org_mapping(session)
        print(f"\n  组织映射: org_a={org_names['org_a']}, org_b={org_names['org_b']}, "
              f"org_c={org_names['org_c']}, org_d={org_names['org_d']}")

        # 1. 清理
        print("\n[1/4] 清理已有测试数据…")
        await cleanup_test_data(session)
        await session.commit()

        # 2. 用户
        print("\n[2/4] 创建测试用户…")
        user_ids = await seed_users(session, org_ids)
        await session.commit()

        # 3. 模板
        print("\n[3/4] 创建测试模板…")
        templates_data = await seed_templates(session, user_ids, org_ids, org_names)
        await session.commit()

        # 4. 实例
        print("\n[4/4] 创建测试实例…")
        await seed_instances(session, user_ids, org_ids, templates_data, org_names)
        await session.commit()

    print("\n" + "=" * 60)
    print("  测试数据写入完成！")
    print(f"  用户: {len(TEST_USERS)} 个")
    print(f"  模板: 5 个")
    print(f"  实例: {len(INSTANCES_DEF)} 个（含任务/校验/审批/批准）")
    print(f"  统一密码: {TEST_PASSWORD}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
