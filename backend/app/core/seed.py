"""预置数据种子脚本 —— 首次部署时执行，插入角色、示例组织、系统配置"""

import asyncio
from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models import Role, Organization, SystemConfig, User, UserRole

# 预置角色
ROLES = [
    {"code": "system_admin", "name": "系统管理员", "description": "维护基础数据，不参与业务"},
    {"code": "manager", "name": "所长", "description": "设计流程、发起项目、终止流程、终审"},
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
    # 注：上传大小 / 允许扩展名 / 节点默认时限由环境变量 settings 控制（M28），
    # 不再写入 SystemConfig 表——避免出现「配置页可改但对系统零效果」的假开关
    # ── PDF 签名通用 ──
    {"config_key": "pdf_signature_x", "config_value": "100", "description": "PDF签名默认X坐标"},
    {"config_key": "pdf_signature_y", "config_value": "50", "description": "PDF签名默认Y坐标"},
    {"config_key": "pdf_signature_offset", "config_value": "150", "description": "多签名X偏移量（同页多人签名时的水平间距）"},
    {"config_key": "pdf_signature_max_width", "config_value": "100", "description": "签名图片最大宽度(px)"},
    {"config_key": "pdf_signature_max_height", "config_value": "26", "description": "签名图片最大高度(px)"},
    # ── 角色维度签名默认位置 ──
    {"config_key": "pdf_signature_assignee_x", "config_value": "400", "description": "负责人签名默认X坐标"},
    {"config_key": "pdf_signature_assignee_y", "config_value": "100", "description": "负责人签名默认Y坐标"},
    {"config_key": "pdf_signature_checker_x", "config_value": "400", "description": "校验人签名默认X坐标"},
    {"config_key": "pdf_signature_checker_y", "config_value": "100", "description": "校验人签名默认Y坐标"},
    {"config_key": "pdf_signature_approver_x", "config_value": "400", "description": "审批人签名默认X坐标"},
    {"config_key": "pdf_signature_approver_y", "config_value": "100", "description": "审批人签名默认Y坐标"},
    {"config_key": "pdf_signature_endorser_x", "config_value": "400", "description": "批准人签名默认X坐标"},
    {"config_key": "pdf_signature_endorser_y", "config_value": "100", "description": "批准人签名默认Y坐标"},
]

# 默认管理员密码从配置文件读取
from app.core.config import settings
if not settings.DEFAULT_ADMIN_PASSWORD:
    raise RuntimeError("环境变量 DEFAULT_ADMIN_PASSWORD 未设置，请先设置默认管理员密码后重试")

DEFAULT_ADMIN = {
    "username": "admin",
    "password": settings.DEFAULT_ADMIN_PASSWORD,
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
            # 默认管理员不归属任何组织
            admin_user = User(
                username=DEFAULT_ADMIN["username"],
                password_hash=hash_password(DEFAULT_ADMIN["password"]),
                real_name=DEFAULT_ADMIN["real_name"],
                organization_id=None,
            )
            session.add(admin_user)
            await session.flush()

            session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
            print(f"  + 管理员: {DEFAULT_ADMIN['username']}（密码已从环境变量设置）")

        await session.commit()
        print("\n种子数据写入完成")


if __name__ == "__main__":
    asyncio.run(seed())