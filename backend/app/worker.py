"""ARQ Worker 入口 —— 后台 PDF 转换任务

启动方式（在 backend 目录下执行）：
    arq app.worker.WorkerSettings

依赖：
    Redis 必须运行，ARQ_REDIS_URL 需指向正确地址
"""

from arq.connections import RedisSettings
from app.core.redis import ARQ_REDIS_URL
from app.services.pdf_queue import convert_file_job, convert_all_files_job


class WorkerSettings:
    """ARQ Worker 配置 —— arq CLI 会自动加载此类"""

    # Redis 连接（DB 0：任务队列）
    redis_settings = RedisSettings.from_dsn(ARQ_REDIS_URL)

    # 注册的任务函数
    functions = [
        convert_file_job,
        convert_all_files_job,
    ]

    # 并发任务数（对应 libsoffice 进程数）
    max_jobs = 4

    # 任务超时（秒）
    job_timeout = 120

    # 优雅关闭等待时间
    grace_period = 30
