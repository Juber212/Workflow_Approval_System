"""业务异常类 —— 统一抛出，由全局异常处理器捕获"""

from app.core.error_codes import ErrorCode


class AppException(Exception):
    """统一业务异常"""

    def __init__(self, code: ErrorCode, message: str | None = None, data: dict | None = None):
        self.code = code
        self.message = message or _DEFAULT_MESSAGES.get(code, "未知错误")
        self.data = data
        super().__init__(self.message)


# 错误码 → 默认中文提示
_DEFAULT_MESSAGES: dict[ErrorCode, str] = {
    # 通用
    ErrorCode.BAD_REQUEST: "请求参数错误",
    ErrorCode.VALIDATION_ERROR: "参数校验失败",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.INTERNAL_ERROR: "服务器内部错误",
    # 认证
    ErrorCode.UNAUTHORIZED: "未登录或登录已过期",
    ErrorCode.TOKEN_EXPIRED: "Token 已过期，请重新登录",
    ErrorCode.TOKEN_INVALID: "Token 无效",
    ErrorCode.LOGIN_FAILED: "用户名或密码错误",
    # 权限
    ErrorCode.FORBIDDEN: "无权限执行此操作",
    ErrorCode.NOT_INITIATOR: "仅流程发起人可执行此操作",
    ErrorCode.NOT_ASSIGNEE: "仅当前节点负责人可执行此操作",
    ErrorCode.NOT_APPROVER: "仅当前节点审批人可执行此操作",
    ErrorCode.NOT_CHECKER: "仅当前节点校验人可执行此操作",
    # 资源冲突
    ErrorCode.CONFLICT: "资源冲突，操作无法继续",
    ErrorCode.TEMPLATE_NAME_EXISTS: "流程名称已存在",
    ErrorCode.INSTANCE_ALREADY_TERMINATED: "流程已终止，不可重复操作",
    ErrorCode.ALREADY_PROCESSED: "该记录已处理，不可重复操作",
    ErrorCode.NOT_RUNNING: "仅运行中流程可执行此操作",
    ErrorCode.REJECT_TARGET_INVALID: "驳回目标节点必须在当前节点之前",
    ErrorCode.PRIORITY_ONLY_RUNNING: "仅运行中流程可修改优先级",
    # 文件
    ErrorCode.FILE_TYPE_UNSUPPORTED: "不支持的文件类型",
    ErrorCode.FILE_TOO_LARGE: "文件大小超过限制",
    ErrorCode.PDF_CONVERSION_FAILED: "PDF 转换失败",
}
