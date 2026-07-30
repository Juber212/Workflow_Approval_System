"""业务错误码枚举 —— 对应 03_API_Design.md 附录：错误码"""

from enum import IntEnum


class ErrorCode(IntEnum):
    """统一错误码"""

    # 通用
    BAD_REQUEST = 40000
    VALIDATION_ERROR = 40001
    NOT_FOUND = 40400
    METHOD_NOT_ALLOWED = 40500   # 预留（HTTP 405，FastAPI 自动处理）
    INTERNAL_ERROR = 50000

    # 认证 (401xx)
    UNAUTHORIZED = 40100
    TOKEN_EXPIRED = 40101      # 预留（JWT 中间件可切换至此精确码）
    TOKEN_INVALID = 40102       # 预留（JWT 中间件可切换至此精确码）
    LOGIN_FAILED = 40103

    # 权限 (403xx)
    FORBIDDEN = 40300
    NOT_INITIATOR = 40301
    NOT_ASSIGNEE = 40302        # 预留（Service 层可替换泛型 FORBIDDEN）
    NOT_APPROVER = 40303        # 预留（Service 层可替换泛型 FORBIDDEN）
    NOT_CHECKER = 40304         # 预留（Service 层可替换泛型 FORBIDDEN）
    MUST_CHANGE_PASSWORD = 40310  # 首次登录/重置密码后必须修改密码

    # 资源冲突 (409xx)
    CONFLICT = 40900
    TEMPLATE_NAME_EXISTS = 40901
    INSTANCE_ALREADY_TERMINATED = 40902
    ALREADY_PROCESSED = 40903     # 预留
    NOT_RUNNING = 40904
    CANNOT_TERMINATE_SELF = 40905  # 预留
    FILE_NOT_CONVERTED = 40906     # 预留
    REJECT_TARGET_INVALID = 40907
    PRIORITY_ONLY_RUNNING = 40908

    # 文件相关 (415xx)
    FILE_TYPE_UNSUPPORTED = 41500
    FILE_TOO_LARGE = 41501
    PDF_CONVERSION_FAILED = 50001

    # 限流 (429xx)
    RATE_LIMITED = 42900
