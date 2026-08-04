"""应用配置管理 —— 基于 Pydantic Settings 从环境变量加载"""

import urllib.parse

from pydantic_settings import BaseSettings

# 已知默认 SECRET_KEY（P1-49：非开发环境禁止使用）
KNOWN_DEFAULT_SECRETS = {"dev-secret-key-change-in-production", "change-this-to-a-random-secret-key"}


class Settings(BaseSettings):
    """应用配置（自动从环境变量 / .env 文件加载）"""

    # 应用
    APP_NAME: str = "企业项目审批系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    # 运行环境（development / test / prod）——P1-49 生产守卫、P1-50 Swagger 开关共用。
    # 生产部署须显式设为 prod，否则默认 development 不会触发生产守卫。
    ENV: str = "development"

    # 数据库
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "workflow_approval"
    # 测试库独立库名（P1-47）：MySQL 真实测试 fixture 复用主库凭据，仅库名指向独立测试库
    TEST_DB_NAME: str = "workflow_approval_test"
    # 连接池（P1-29）：多 worker 部署时须保证 worker×(pool_size+max_overflow) ≤ MySQL max_connections。
    # 默认 20+20（单进程最多 40 连接）；`--workers 4` 时应调小 pool_size 或减少 worker，防止连接数翻倍超限。
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 20

    # JWT
    SECRET_KEY: str = ""  # 必须在环境变量中设置，空值会导致启动失败
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 小时

    # 用户默认密码（必须在 .env 中配置，不允许使用源码默认值）
    DEFAULT_USER_PASSWORD: str = ""
    # 管理员初始密码（仅首次部署 seed 脚本创建 admin 时使用）
    DEFAULT_ADMIN_PASSWORD: str = ""

    # Redis（ARQ 任务队列 + Pub/Sub 桥接）
    REDIS_URL: str = "redis://localhost:6379/0"  # Redis 连接地址
    REDIS_ARQ_DB: int = 0   # ARQ 任务队列 DB
    REDIS_PUBSUB_DB: int = 1  # Pub/Sub 桥接 DB

    # 文件存储
    STORAGE_ROOT: str = "storage"  # 相对项目根目录
    LIBREOFFICE_PATH: str = "soffice"  # LibreOffice 命令行路径

    # 存储子目录（支持中文命名，按实例类型分目录）
    PROJECT_ARCHIVE_DIR: str = "项目"    # 项目归档子目录
    PROPOSAL_ARCHIVE_DIR: str = "方案"   # 方案归档子目录
    STORAGE_SIGNATURES_DIR: str = "signatures"         # 用户签名图片目录
    STORAGE_DOCUMENT_TEMPLATES_DIR: str = "document_templates"  # 文件模板目录

    # 文件上传限制
    MAX_FILE_SIZE_MB: int = 50  # 最大文件大小（MB）
    ALLOWED_MIME_TYPES: str = (
        "application/pdf,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "image/png,image/jpeg,image/jpg"
    )

    # PDF 签名默认参数
    PDF_SIGNATURE_X: int = 400       # 签名 X 坐标
    PDF_SIGNATURE_Y: int = 100       # 签名 Y 坐标
    PDF_SIGNATURE_OFFSET: int = 150  # 多签名 X 偏移量
    PDF_SIGNATURE_PAGE: int = -1     # 签名页码（-1 = 最后一页）
    PDF_SIGNATURE_MAX_WIDTH: int = 100   # 签名最大宽度
    PDF_SIGNATURE_MAX_HEIGHT: int = 26   # 签名最大高度

    # ── 角色维度签名默认值（全局配置，管理员在系统管理页配置）──
    # 负责人 (assignee) 默认签名位置
    PDF_SIGNATURE_ASSIGNEE_X: int = 400
    PDF_SIGNATURE_ASSIGNEE_Y: int = 100
    # 校验人 (checker) 默认签名位置
    PDF_SIGNATURE_CHECKER_X: int = 400
    PDF_SIGNATURE_CHECKER_Y: int = 100
    # 审批人 (approver) 默认签名位置
    PDF_SIGNATURE_APPROVER_X: int = 400
    PDF_SIGNATURE_APPROVER_Y: int = 100
    # 批准人 (endorser) 默认签名位置
    PDF_SIGNATURE_ENDORSER_X: int = 400
    PDF_SIGNATURE_ENDORSER_Y: int = 100

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def allowed_mime_types_list(self) -> list[str]:
        """允许上传的文件 MIME 类型列表"""
        return [t.strip() for t in self.ALLOWED_MIME_TYPES.split(",") if t.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        """最大文件大小（字节）"""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    def get_archive_dir(self, template_type: str = "project") -> str:
        """根据模板类型返回归档子目录名"""
        return self.PROPOSAL_ARCHIVE_DIR if template_type == "proposal" else self.PROJECT_ARCHIVE_DIR

    @property
    def database_url(self) -> str:
        """MySQL 连接 URL（charset 确保中文注释不乱码；READ COMMITTED 防止 fork-join 并发竞态）

        P1-27：DB_USER/DB_PASSWORD 经 quote_plus 编码——密码含 @ : / % 等
        特殊字符时，未编码会让 SQLAlchemy 误解析连接串（如 pa@ss 被当作用户:密码分隔）。
        """
        # 注意：isolation_level 不能放 URL 查询参数（aiomysql 不支持），
        # 需通过 create_async_engine 的 connect_args 传递
        user = urllib.parse.quote_plus(self.DB_USER, safe="")
        password = urllib.parse.quote_plus(self.DB_PASSWORD, safe="")
        return (
            f"mysql+aiomysql://{user}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
