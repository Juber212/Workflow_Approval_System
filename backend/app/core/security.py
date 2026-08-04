"""安全工具：JWT Token 生成/校验 + 密码哈希 + 密码强度校验"""

import re
import uuid
import time as _time
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.error_codes import ErrorCode

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希值"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def ensure_password_byte_limit(password: str, label: str = "密码") -> None:
    """bcrypt 只处理前 72 字节，超长密码会被静默截断（P1-23），直接拒绝

    注意按 UTF-8 字节而非字符计数：中文字符占 3 字节，24 个中文即达 72 字节。
    """
    if len(password.encode("utf-8")) > 72:
        raise AppException(
            ErrorCode.BAD_REQUEST,
            f"{label}过长（bcrypt 最多支持 72 字节，约 72 个英文或 24 个中文字符）",
        )


def validate_password_strength(password: str, username: str) -> None:
    """密码强度校验：≥8位 + 必须包含字母和数字 + 不能与用户名相同

    用户自己改密码时调用；管理员重置密码/创建用户用默认密码，不受此限制。
    """
    ensure_password_byte_limit(password)
    if len(password) < 8:
        raise AppException(ErrorCode.BAD_REQUEST, "密码长度不能少于8位")
    if not re.search(r'[a-zA-Z]', password) or not re.search(r'\d', password):
        raise AppException(ErrorCode.BAD_REQUEST, "密码必须包含字母和数字")
    if password.lower() == username.lower():
        raise AppException(ErrorCode.BAD_REQUEST, "密码不能与用户名相同")


def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    """生成 JWT Access Token，自动注入 jti（唯一ID）和 iat（签发时间）

    jti 用于登出/禁用时的 Token 黑名单机制（Redis SET + TTL）。
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({
        "exp": expire,
        "iat": int(_time.time()),           # 签发时间（Unix 时间戳）
        "jti": uuid.uuid4().hex,            # JWT 唯一 ID，用于黑名单
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """解析 JWT Token，失败返回 None"""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
