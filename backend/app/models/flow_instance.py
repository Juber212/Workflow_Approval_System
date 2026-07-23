"""项目模型"""

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.core.database import Base


class FlowInstance(Base):
    __tablename__ = "flow_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="项目名称")
    description: Mapped[str | None] = mapped_column(String(500), comment="补充说明")
    template_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="使用的模板ID（冗余，无外键）")
    template_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="模板名称快照（创建时冗余存储）")
    template_type: Mapped[str] = mapped_column(String(20), default="project", comment="模板类型快照: project / proposal（用于存储分目录等）")
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False, comment="所属组织")
    initiator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="发起人")
    priority: Mapped[str] = mapped_column(String(20), default="normal", comment="优先级")
    difficulty: Mapped[str] = mapped_column(String(20), default="1", comment="难度等级: 1/2/3/4")
    contract_no: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="合同号")
    product_model: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="产品型号")
    sales_manager: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="销售经理")
    proposal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("flow_instances.id"), nullable=True, comment="关联的方案ID（仅项目类型可用）")
    status: Mapped[str] = mapped_column(String(20), default="created", comment="主状态")
    termination_reason: Mapped[str | None] = mapped_column(String(500), comment="终止原因")
    initiated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="发起时间")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="完成时间")
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime, comment="终止时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
