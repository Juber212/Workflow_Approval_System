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

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
