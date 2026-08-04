"""配置测试 —— database_url 对特殊字符账号密码的编码（P1-27）"""

from sqlalchemy.engine import make_url

from app.core.config import Settings


def test_database_url_encodes_special_password():
    """密码含 @ : / 等特殊字符 → 连接串正确编码且可还原（P1-27）"""
    s = Settings(DB_HOST="db", DB_PORT=3306, DB_USER="root",
                 DB_PASSWORD="pa@ss:word/ok", DB_NAME="wf")
    url = s.database_url
    assert url == "mysql+aiomysql://root:pa%40ss%3Aword%2Fok@db:3306/wf?charset=utf8mb4"

    # 编码后 SQLAlchemy 能正确解析还原账号密码
    parsed = make_url(url)
    assert parsed.username == "root"
    assert parsed.password == "pa@ss:word/ok"


def test_database_url_encodes_special_username():
    """用户名含特殊字符 → 同样编码"""
    s = Settings(DB_HOST="db", DB_PORT=3306, DB_USER="user@1",
                 DB_PASSWORD="secret", DB_NAME="wf")
    parsed = make_url(s.database_url)
    assert parsed.username == "user@1"


def test_database_url_normal_unchanged():
    """普通账号密码 → 连接串保持原样，不影响现有环境"""
    s = Settings(DB_HOST="localhost", DB_PORT=3306, DB_USER="root",
                 DB_PASSWORD="secret", DB_NAME="workflow_approval")
    assert s.database_url == "mysql+aiomysql://root:secret@localhost:3306/workflow_approval?charset=utf8mb4"


def test_db_pool_size_defaults():
    """连接池默认值（P1-29）：pool_size + max_overflow 可配置且默认 20/20"""
    s = Settings()
    assert s.DB_POOL_SIZE == 20
    assert s.DB_MAX_OVERFLOW == 20
    # 多 worker 场景可调小
    s2 = Settings(DB_POOL_SIZE=10, DB_MAX_OVERFLOW=5)
    assert s2.DB_POOL_SIZE == 10
    assert s2.DB_MAX_OVERFLOW == 5
