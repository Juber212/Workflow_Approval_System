"""预置数据种子脚本 —— 首次部署时执行，插入角色、示例组织、系统配置"""

import asyncio
import bcrypt
from app.core.database import async_session_factory
from app.models import Role, Organization, SystemConfig, User, UserRole

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# 预置角色
ROLES = [
    {"code": "system_admin", "name": "系统管理员", "description": "维护基础数据，不参与业务"},
    {"code": "manager", "name": "所长", "description": "设计流程、发起流程、终止流程、终审"},
    {"code": "user", "name": "普通用户", "description": "执行节点、上传文件、审批"},
]

# 预置组织
ORGS = [
    {"name": "通用所", "description": "通用业务所"},
    {"name": "结构所", "description": "结构设计所"},
    {"name": "电气所", "description": "电气设计所"},
    {"name": "暖通所", "description": "暖通设计所"},
]

# 预置系统配置
CONFIGS = [
    {"config_key": "allowed_file_extensions", "config_value": ".doc,.docx,.xls,.xlsx,.pdf,.png,.jpg,.jpeg", "description": "允许上传的文件扩展名"},
    {"config_key": "max_file_size_mb", "config_value": "50", "description": "上传文件大小限制(MB)"},
    {"config_key": "pdf_signature_x", "config_value": "100", "description": "PDF签名X坐标"},
    {"config_key": "pdf_signature_y", "config_value": "50", "description": "PDF签名Y坐标"},
    {"config_key": "default_time_limit_days", "config_value": "7", "description": "节点默认完成时限(天)"},
]

# 默认管理员
DEFAULT_ADMIN = {
    "username": "admin",
    "password": "admin123",
    "real_name": "系统管理员",
}


async def seed():
    """执行种子数据插入（幂等：已存在则跳过）"""
    async with async_session_factory() as session:
        # 角色
        for role_data in ROLES:
            existing = await session.run_sync(
                lambda s, c=role_data["code"]: s.query(Role).filter_by(code=c).first()
            )
            if existing is None:
                role = Role(**role_data)
                session.add(role)
                print(f"  + 角色: {role_data['name']}")

        # 组织
        for org_data in ORGS:
            existing = await session.run_sync(
                lambda s, n=org_data["name"]: s.query(Organization).filter_by(name=n).first()
            )
            if existing is None:
                org = Organization(**org_data)
                session.add(org)
                print(f"  + 组织: {org_data['name']}")

        # 系统配置
        for cfg_data in CONFIGS:
            existing = await session.run_sync(
                lambda s, k=cfg_data["config_key"]: s.query(SystemConfig).filter_by(config_key=k).first()
            )
            if existing is None:
                cfg = SystemConfig(**cfg_data)
                session.add(cfg)
                print(f"  + 配置: {cfg_data['config_key']}")

        await session.flush()

        # 管理员用户
        admin_exists = await session.run_sync(
            lambda s: s.query(User).filter_by(username=DEFAULT_ADMIN["username"]).first()
        )
        if admin_exists is None:
            admin_role = await session.run_sync(
                lambda s: s.query(Role).filter_by(code="system_admin").first()
            )
            general_org = await session.run_sync(
                lambda s: s.query(Organization).filter_by(name="通用所").first()
            )
            admin_user = User(
                username=DEFAULT_ADMIN["username"],
                password_hash=hash_password(DEFAULT_ADMIN["password"]),
                real_name=DEFAULT_ADMIN["real_name"],
                organization_id=general_org.id,
            )
            session.add(admin_user)
            await session.flush()

            session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
            print(f"  + 管理员: {DEFAULT_ADMIN['username']} (密码: {DEFAULT_ADMIN['password']})")

        await session.commit()
        print("\n种子数据写入完成")


if __name__ == "__main__":
    asyncio.run(seed())