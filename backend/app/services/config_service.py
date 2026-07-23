"""系统配置服务 —— 内存缓存 + 定期刷新"""
import logging

from sqlalchemy import select

from app.models import SystemConfig

logger = logging.getLogger("app")


class ConfigService:
    """系统配置内存缓存（单例）"""

    def __init__(self):
        self._cache: dict[str, SystemConfig] = {}
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def get(self, key: str, default: str = "") -> str:
        """从缓存读取配置值"""
        item = self._cache.get(key)
        return item.config_value if item else default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, str(default)))
        except ValueError:
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key, str(default)))
        except ValueError:
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key, "").lower()
        return val in ("true", "1", "yes")

    def get_all(self) -> dict[str, str]:
        """返回所有配置项 key→value 映射"""
        return {k: v.config_value for k, v in self._cache.items()}

    def get_all_items(self) -> list:
        """返回所有配置项原始对象列表（供 API 层使用）"""
        return list(self._cache.values())

    async def load(self, session_factory) -> None:
        """从数据库加载全部配置到缓存"""
        async with session_factory() as session:
            result = await session.execute(select(SystemConfig))
            rows = result.scalars().all()
            self._cache = {row.config_key: row for row in rows}
        self._loaded = True
        logger.info(f"ConfigService: 已加载 {len(self._cache)} 项配置")

    async def refresh(self, session_factory) -> None:
        """刷新缓存（从数据库重新加载）"""
        await self.load(session_factory)

    async def update(self, session_factory, updates: dict[int, str]) -> list[str]:
        """批量更新配置值 → 写入 DB → 刷新缓存 → 返回变更的 key 列表

        先更新内存缓存（DB 提交前），再提交 DB。如果 DB 提交失败，
        下次 load() 或 refresh() 会从 DB 重新加载，自动修复缓存。
        如果 DB 提交成功但后续 load 失败，缓存已包含新值，不受影响。
        """
        updated_keys = []
        async with session_factory() as session:
            result = await session.execute(
                select(SystemConfig).where(SystemConfig.id.in_(updates.keys()))
            )
            rows = {r.id: r for r in result.scalars().all()}

            for cfg_id, new_value in updates.items():
                cfg = rows.get(cfg_id)
                if cfg is None:
                    continue
                old_value = cfg.config_value
                cfg.config_value = new_value
                # 同步更新内存缓存（在 DB 提交前更新，避免缓存-DB 不一致）
                if cfg.config_key in self._cache:
                    self._cache[cfg.config_key] = cfg
                updated_keys.append(cfg.config_key)
                logger.info(f"ConfigService: {cfg.config_key} 变更 ({old_value} → {new_value})")

            await session.commit()
            self._loaded = True
            logger.info(f"ConfigService: 已更新 {len(updated_keys)} 项配置")

        return updated_keys


# 全局单例
config_service = ConfigService()
