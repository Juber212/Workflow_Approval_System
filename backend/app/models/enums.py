"""数据库 ENUM 字段对应的 Python 枚举类"""

import enum


class TemplateStatus(str, enum.Enum):
    """项目模板状态"""
    DRAFT = "draft"
    PUBLISHED = "published"
    DISABLED = "disabled"


class VersionStatus(str, enum.Enum):
    """版本状态"""
    PUBLISHED = "published"
    DISABLED = "disabled"


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
    FINISHED = "finished"
    REJECTED = "rejected"
    TERMINATED = "terminated"


class TaskStatus(str, enum.Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    WAITING_CHECK = "waiting_check"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    REJECTED = "rejected"
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
    """操作者类型"""
    USER = "user"
    SYSTEM = "system"


class UploadType(str, enum.Enum):
    """文件上传类型"""
    NORMAL = "normal"
    SUPPLEMENT = "supplement"
