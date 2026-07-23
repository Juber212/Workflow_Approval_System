"""应用配置管理 —— 基于 Pydantic Settings 从环境变量加载"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置（自动从环境变量 / .env 文件加载）"""

    # 应用
    APP_NAME: str = "企业项目审批系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # 数据库
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "workflow_approval"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 小时

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
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
