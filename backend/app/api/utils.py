"""工具类 API —— 工作日计算等通用能力"""

from datetime import date as date_type

from fastapi import APIRouter, Depends
from app.api.deps import get_current_active_user
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse
from app.utils.workday import add_workdays, next_workday

router = APIRouter(prefix="/api/v1", tags=["工具"])


class DeadlineCalcItem(BaseModel):
    """单个节点的截止日期计算入参"""
    node_id: int = Field(..., description="模板节点 ID")
    time_limit_days: int | None = Field(None, description="该节点的完成时限（工作日）")
    deadline: str | None = Field(None, description="已锁定的截止日期（锚点）——有此值则跳过计算直接采用，作为后续节点顺延起点")


class CalculateDeadlinesRequest(BaseModel):
    """截止日期计算请求"""
    start_date: str = Field(..., description="起始日期（发起日期），格式 YYYY-MM-DD")
    nodes: list[DeadlineCalcItem] = Field(..., description="节点列表（按流程顺序排列）")


class DeadlineCalcResult(BaseModel):
    """单个节点的截止日期计算结果 —— 含预估开始日期和截止日期"""
    node_id: int
    begin: str | None     # YYYY-MM-DD，预估开始日期
    deadline: str | None  # YYYY-MM-DD，截止日期


class CalculateDeadlinesResponse(BaseModel):
    """截止日期计算响应"""
    deadlines: list[DeadlineCalcResult]


@router.post("/utils/calculate-deadlines", response_model=ApiResponse)
async def calculate_deadlines(
    body: CalculateDeadlinesRequest,
    current_user=Depends(get_current_active_user),
):
    """计算节点预估开始/截止日期 —— 按工作日跳过法定节假日和周末

    计算规则：
    - 节点1 开始 = 发起日期，截止 = 开始 + time_limit_days 工作日
    - 节点2 开始 = 节点1截止的下一个工作日，截止 = 开始 + time_limit_days 工作日
    - 以此类推链式递推
    - time_limit_days 为 0 或 None 的节点不计算
    - 传入 deadline（锚点）的节点跳过计算直接采用，作为后续节点顺延起点
      （用于前端发起模式：用户已锁定某节点截止日，下游基于该日期级联）

    超出 chinesecalendar 支持年份时退化为仅跳过周末。
    用于发起项目设计器（FlowDesigner launch 模式）的日历预填与截止日级联。
    """
    try:
        start = date_type.fromisoformat(body.start_date)
    except (ValueError, TypeError):
        from app.core.exceptions import AppException
        from app.core.error_codes import ErrorCode
        raise AppException(ErrorCode.VALIDATION_ERROR, "start_date 格式不正确，应为 YYYY-MM-DD")

    results: list[DeadlineCalcResult] = []
    # 上一个节点的截止日期，用于计算下一个节点的开始日期
    prev_deadline: date_type | None = None

    for node in body.nodes:
        # 锚点节点：跳过计算，直接采用给定截止日（用户已在发起页锁定该日期）
        if node.deadline:
            try:
                anchor = date_type.fromisoformat(node.deadline)
            except (ValueError, TypeError):
                from app.core.exceptions import AppException
                from app.core.error_codes import ErrorCode
                raise AppException(ErrorCode.VALIDATION_ERROR, "节点截止日期格式不正确，应为 YYYY-MM-DD")
            results.append(DeadlineCalcResult(
                node_id=node.node_id, begin=None, deadline=node.deadline,
            ))
            prev_deadline = anchor
            continue

        wd = node.time_limit_days or 0
        if wd <= 0:
            results.append(DeadlineCalcResult(
                node_id=node.node_id, begin=None, deadline=None,
            ))
            continue

        # 计算本节点开始日期
        if prev_deadline is None:
            # 第一个有效节点：从发起日期开始
            begin_date = start
        else:
            # 后续节点：从前节点截止的下一个工作日开始
            begin_date = next_workday(prev_deadline)

        # 计算截止日期：begin + N 工作日
        deadline_date = add_workdays(begin_date, wd)

        results.append(DeadlineCalcResult(
            node_id=node.node_id,
            begin=begin_date.isoformat(),
            deadline=deadline_date.isoformat(),
        ))
        prev_deadline = deadline_date

    return ApiResponse.ok(CalculateDeadlinesResponse(deadlines=results).model_dump())
