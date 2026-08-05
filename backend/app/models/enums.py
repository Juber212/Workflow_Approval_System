"""数据库 ENUM 字段对应的 Python 枚举类"""

import enum


class InstanceStatus(str, enum.Enum):
    """流程实例主状态"""
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class Priority(str, enum.Enum):
    """优先级"""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class InstanceNodeStatus(str, enum.Enum):
    """实例节点状态"""
    WAITING = "waiting"
    RUNNING = "running"
    WAITING_CHECK = "waiting_check"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_ENDORSEMENT = "waiting_endorsement"
    FINISHED = "finished"
    TERMINATED = "terminated"


class TaskStatus(str, enum.Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    WAITING_CHECK = "waiting_check"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_ENDORSEMENT = "waiting_endorsement"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class ApprovalStatus(str, enum.Enum):
    """审批状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TERMINATED = "terminated"


class CheckStatus(str, enum.Enum):
    """校验状态"""
    PENDING = "pending"
    PASSED = "passed"
    RETURNED = "returned"
    TERMINATED = "terminated"


class OperatorType(str, enum.Enum):
    """操作者类型（仅 user —— 系统操作不记录日志，直接忽略）"""
    USER = "user"


class UploadType(str, enum.Enum):
    """文件上传类型"""
    NORMAL = "normal"
    SUPPLEMENT = "supplement"


class EndorsementStatus(str, enum.Enum):
    """批准状态（Endorsement 专用）"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TERMINATED = "terminated"


class Difficulty(str, enum.Enum):
    """项目难度等级"""
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR = "4"


class TemplateType(str, enum.Enum):
    """模板类型（模板/实例快照共用）"""
    PROJECT = "project"
    PROPOSAL = "proposal"


class ApprovalStrategy(str, enum.Enum):
    """审批策略"""
    ALL_APPROVE = "all_approve"
    SINGLE_APPROVE = "single_approve"


class ConversionStatus(str, enum.Enum):
    """文件 PDF 转换状态"""
    PENDING = "pending"
    CONVERTING = "converting"
    READY = "ready"
    FAILED = "failed"
