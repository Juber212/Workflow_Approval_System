"""应用日志配置 —— 控制台 + 按日滚动的文件日志"""

import logging
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

from app.core.config import settings


def setup_logging() -> None:
    """初始化日志系统：控制台彩色输出 + 文件按日归档"""

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    console.setFormatter(fmt)

    # 文件 handler —— 每天滚动，保留 30 天
    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    root_logger.addHandler(console)
    root_logger.addHandler(file_handler)

    # 减少第三方库日志噪音
    logging.getLogger("aiomysql").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
