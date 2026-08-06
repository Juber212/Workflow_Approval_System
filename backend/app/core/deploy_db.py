"""部署建库脚本 —— 全新库一键初始化（建库 + 建表 + 分区 + 基线标记）

用法（在 backend 目录执行）：
    python -m app.core.deploy_db

流程：
1. 创建数据库（utf8mb4，幂等）
2. 用 SQLAlchemy Base.metadata.create_all 建全部表（当前模型结构 = 迁移最终态，含全部索引）
3. operation_logs 按年分区（幂等，含 p_future=MAXVALUE 兜底未来年份）
4. alembic stamp head（把当前结构标记为迁移链最新基线，后续增量迁移正常走）

背景：历史迁移链（cdc82f5bf321 起）是「假设表已存在」的增量迁移（修正注释 / 删旧表 / 加索引），
无法在全新空库上重放（实测第一步 alter approvals 即报 1146 表不存在）。因此本脚本用
create_all 建当前结构 + stamp head 替代，与 tests/mysql 的建表方式一致。
开发/生产库升级仍走 alembic upgrade head，不受本脚本影响。
"""
import asyncio
import os
import subprocess
import sys

import aiomysql
from sqlalchemy import text

from app.core.config import settings
from app.core.database import Base, engine
import app.models  # noqa: F401  确保所有模型注册到 Base.metadata


# operation_logs 分区 DDL（对齐开发库：p_future=MAXVALUE 兜底，即使忘加年份分区也不会写入失败）
_PARTITION_DDL = """
ALTER TABLE operation_logs PARTITION BY RANGE (YEAR(created_at)) (
    PARTITION p2026 VALUES LESS THAN (2027),
    PARTITION p2027 VALUES LESS THAN (2028),
    PARTITION p2028 VALUES LESS THAN (2029),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
"""


async def _create_database() -> None:
    """创建目标数据库（无库名连接，幂等）"""
    conn = await aiomysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )
    try:
        cur = await conn.cursor()
        await cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        await cur.close()
    finally:
        conn.close()
    print(f"[deploy] 数据库已就绪: {settings.DB_NAME}")


async def _create_tables() -> None:
    """用当前模型结构建全部表（模型 __table_args__ 已声明全部最终索引）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[deploy] 全部数据表已创建（当前模型结构）")


async def _create_partitions() -> None:
    """operation_logs 按年分区（幂等：已分区则跳过）

    注意：MySQL 对非分区表在 PARTITIONS 视图也保留一行 PARTITION_METHOD=NULL，
    因此必须以 PARTITION_METHOD IS NOT NULL 判断是否已分区，否则全新表会被误判为「已分区」跳过。
    """
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.PARTITIONS "
                "WHERE TABLE_SCHEMA = :db AND TABLE_NAME = 'operation_logs' "
                "AND PARTITION_METHOD IS NOT NULL"
            ),
            {"db": settings.DB_NAME},
        )
        count = result.scalar() or 0
    if count:
        print("[deploy] operation_logs 已分区，跳过")
        return
    async with engine.begin() as conn:
        await conn.execute(text(_PARTITION_DDL))
    print("[deploy] operation_logs 已按年分区（p2026-p2028 + p_future 兜底）")


def _stamp_head() -> None:
    """把当前结构标记为 alembic 迁移链最新基线（stamp head）"""
    # 定位 backend 目录（本文件在 backend/app/core/ 下）
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env = os.environ.copy()
    env["DB_NAME"] = settings.DB_NAME  # 确保 alembic 连到目标库（与 create_all 一致）
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "stamp", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    print("[deploy] alembic 基线已标记（stamp head）")


async def main() -> None:
    """建库脚本主流程"""
    await _create_database()
    await _create_tables()
    await _create_partitions()
    _stamp_head()
    # 显式释放连接池，避免事件循环关闭后 aiomysql 连接 __del__ 清理告警
    await engine.dispose()
    print("\n[deploy] 建库完成。下一步执行: python -m app.core.seed")


if __name__ == "__main__":
    asyncio.run(main())
