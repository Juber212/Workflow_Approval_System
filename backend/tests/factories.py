"""测试数据工厂 —— 快速创建带默认值的模型实例，减少测试样板代码"""

from datetime import datetime
from app.models import (
    FlowInstance, InstanceNode, Task, CheckRecord, Approval, Endorsement,
    User,
)
from app.models.enums import (
    InstanceStatus, InstanceNodeStatus, TaskStatus, CheckStatus,
    ApprovalStatus, EndorsementStatus, Difficulty, Priority,
)


# ============================================================
# User
# ============================================================

def make_user(**overrides) -> User:
    """创建测试用户，默认拥有所有常用属性"""
    defaults = dict(
        id=1,
        username="testuser",
        real_name="测试用户",
        password_hash="hashed_xxx",
        organization_id=1,
        is_active=True,
        signature_image=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return User(**defaults)


# ============================================================
# FlowInstance
# ============================================================

def make_instance(**overrides) -> FlowInstance:
    """创建测试流程实例"""
    defaults = dict(
        id=1,
        name="测试项目",
        description="用于测试的项目",
        template_id=1,
        template_name="测试模板",
        template_type="project",
        organization_id=1,
        initiator_id=1,
        priority=Priority.NORMAL,
        difficulty=Difficulty.ONE,
        status=InstanceStatus.RUNNING,
        initiated_at=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return FlowInstance(**defaults)


# ============================================================
# InstanceNode
# ============================================================

def make_node(**overrides) -> InstanceNode:
    """创建一个非开始/非结束的中间工作节点"""
    defaults = dict(
        id=1,
        instance_id=1,
        name="设计阶段",
        is_start=False,
        is_end=False,
        assignee_id=1,
        time_limit_days=5,
        checkers=[{"user_id": 3, "name": "校验人A"}],
        approvers=[{"user_id": 4, "name": "审批人A"}],
        approval_strategy="all_approve",
        status=InstanceNodeStatus.RUNNING,
        sort_order=2,
        round=1,
        incoming_count=1,
        arrived_count=1,
        signature_x=400,
        signature_y=100,
        signature_page=-1,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return InstanceNode(**defaults)


def make_start_node(**overrides) -> InstanceNode:
    """创建一个开始节点"""
    return make_node(
        id=10, name="发起", is_start=True, is_end=False,
        status=InstanceNodeStatus.FINISHED, sort_order=1,
        assignee_id=None, checkers=[], approvers=[],
        **overrides,
    )


def make_end_node(**overrides) -> InstanceNode:
    """创建一个结束节点"""
    return make_node(
        id=20, name="终审", is_start=False, is_end=True,
        status=InstanceNodeStatus.WAITING, sort_order=3,
        assignee_id=None, checkers=[], approvers=[{"user_id": 1, "name": "发起人"}],
        **overrides,
    )


# ============================================================
# Task
# ============================================================

def make_task(**overrides) -> Task:
    """创建测试任务"""
    defaults = dict(
        id=1,
        instance_id=1,
        node_id=1,
        assignee_id=2,
        status=TaskStatus.PROCESSING,
        assignee_note=None,
        submitted_at=None,
        completed_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return Task(**defaults)


# ============================================================
# CheckRecord
# ============================================================

def make_check(**overrides) -> CheckRecord:
    """创建测试校验记录"""
    defaults = dict(
        id=1,
        instance_id=1,
        node_id=1,
        task_id=1,
        checker_id=3,
        status=CheckStatus.PENDING,
        opinion=None,
        round=1,
        decided_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return CheckRecord(**defaults)


# ============================================================
# Approval
# ============================================================

def make_approval(**overrides) -> Approval:
    """创建测试审批记录"""
    defaults = dict(
        id=1,
        instance_id=1,
        node_id=1,
        task_id=1,
        approver_id=4,
        status=ApprovalStatus.PENDING,
        opinion=None,
        round=1,
        reject_target_node_id=None,
        signature_applied=False,
        signature_x=None,
        signature_y=None,
        signature_page=None,
        decided_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return Approval(**defaults)


# ============================================================
# Endorsement
# ============================================================

def make_endorsement(**overrides) -> Endorsement:
    """创建测试批准记录"""
    defaults = dict(
        id=1,
        instance_id=1,
        node_id=1,
        task_id=1,
        endorser_id=5,
        status=EndorsementStatus.PENDING,
        opinion=None,
        round=1,
        signature_applied=False,
        decided_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return Endorsement(**defaults)
