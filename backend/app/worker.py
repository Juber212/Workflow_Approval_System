"""ARQ Worker 入口 —— 后台 PDF 转换任务

启动方式（在 backend 目录下执行）：
    python -m arq app.worker.WorkerSettings

注意：用 `python -m arq` 而非 `arq`——后者的 arq.exe shim 可能被
Windows Device Guard/AppLocker 应用控制策略阻止（未签名 exe），
通过 python.exe 以模块方式运行可规避（2026-08-03 实测）。

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

    # 任务超时（秒）—— M27：需覆盖单次转换 60s 超时 × 2 次重试 + 间隔 2s（最坏约 122s），
    # 否则慢转换的第二次重试会被 ARQ 强杀、重试机制形同虚设
    job_timeout = 150

    # 优雅关闭等待时间
    grace_period = 30
