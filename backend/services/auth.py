"""
认证服务层：JWT 签发/校验 + bcrypt 密码哈希 + 当前用户解析依赖。

设计要点：
- P2 起拆为双 token：
  * access token：有效期 30 分钟（JWT_ACCESS_EXPIRE_MINUTES），用于普通业务请求，payload typ="access"。
  * refresh token：有效期 30 天（JWT_REFRESH_EXPIRE_DAYS），仅用于 /api/auth/refresh 换发新 access，payload typ="refresh"。
- payload 携带 user_id（int）与 token_version（int），后端在「改密 / 退出 / 配额」等关键路径
  查 DB 比对 token_version，使其余普通请求走 O(1) 本地解码、不查库。
- token_version 机制复用：改密与退出都 +1，旧 token 立即失效，无需黑名单/Redis。
- JWT_SECRET 由 config 提供；缺失时在开发期随机生成并打印警告（不阻断启动）。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import jwt
from fastapi import Depends, Header, HTTPException
from passlib.context import CryptContext

from backend.db import crud
from config import JWT_SECRET

logger = logging.getLogger(__name__)

# bcrypt 上下文（只启用 bcrypt 方案，避免 passlib 默认 schemes 的兼容噪声）
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_ALGORITHM = "HS256"
JWT_ACCESS_EXPIRE_MINUTES = 30
JWT_REFRESH_EXPIRE_DAYS = 30


# ---------------------------------------------------------------------------
# 密码哈希
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    """bcrypt 哈希明文密码。"""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文与 bcrypt 哈希是否匹配。"""
    try:
        return _pwd_context.verify(plain, hashed)
    except Exception:
        # 哈希串损坏或格式异常时按失败处理，不抛出
        return False


# ---------------------------------------------------------------------------
# JWT 签发 / 校验
# ---------------------------------------------------------------------------
def _build_payload(user_id: int, token_version: int, typ: str,
                   expire_delta: timedelta) -> Dict[str, Any]:
    """构造 JWT payload：typ 区分 access / refresh，便于端点按类型校验。"""
    now = datetime.now(timezone.utc)
    return {
        "sub": str(user_id),
        "uid": user_id,
        "tv": token_version,
        "typ": typ,
        "iat": int(now.timestamp()),
        "exp": int((now + expire_delta).timestamp()),
    }


def create_token(user_id: int, token_version: int) -> str:
    """签发 access token（30 分钟），payload typ="access"。"""
    payload = _build_payload(
        user_id, token_version, "access",
        timedelta(minutes=JWT_ACCESS_EXPIRE_MINUTES),
    )
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int, token_version: int) -> str:
    """签发 refresh token（30 天），payload typ="refresh"，仅用于换发 access。"""
    payload = _build_payload(
        user_id, token_version, "refresh",
        timedelta(days=JWT_REFRESH_EXPIRE_DAYS),
    )
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
    """解码并校验 JWT（签名 + 过期）。失败抛 HTTPException 401。

    expected_type：若为 "access"/"refresh"，则强制校验 payload.typ 匹配，否则 401。
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的登录凭证")
    if expected_type is not None and payload.get("typ") != expected_type:
        raise HTTPException(status_code=401, detail="令牌类型不匹配")
    return payload


def refresh_access_token(refresh_token: str) -> str:
    """用 refresh token 换发新的 access token。

    校验 refresh token（typ="refresh" + 签名 + 过期 + token_version 比库），
    通过则返回新 access token；任何一环失败均抛 401。
    """
    payload = decode_token(refresh_token, expected_type="refresh")
    user_id = payload.get("uid")
    token_version = payload.get("tv")
    if user_id is None:
        raise HTTPException(status_code=401, detail="无效的登录凭证")
    db_version = crud.get_user_token_version(user_id)
    if db_version is None:
        raise HTTPException(status_code=401, detail="账户不存在或已被注销")
    if token_version != db_version:
        raise HTTPException(status_code=401, detail="登录状态已变更，请重新登录")
    user = crud.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="账户不存在或已被注销")
    return create_token(user_id, db_version)


def _validate_version(payload: Dict[str, Any]) -> Tuple[int, int]:
    """从 payload 取出 user_id 与 token_version，并与 DB 最新值比对。

    返回 (user_id, token_version)。版本不符（改密/退出后旧 token）即 401。
    """
    user_id = payload.get("uid")
    token_version = payload.get("tv")
    if user_id is None:
        raise HTTPException(status_code=401, detail="无效的登录凭证")
    db_version = crud.get_user_token_version(user_id)
    if db_version is None:
        raise HTTPException(status_code=401, detail="账户不存在或已被注销")
    if token_version != db_version:
        raise HTTPException(status_code=401, detail="登录状态已变更，请重新登录")
    return user_id, token_version


# ---------------------------------------------------------------------------
# 当前用户依赖
# ---------------------------------------------------------------------------
def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """FastAPI 依赖：从 Authorization: Bearer <token> 解析当前用户。

    正常情况下做「本地解码 + token_version 查库比对」，保证改密/退出后旧 token 失效。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少登录凭证")
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token, expected_type="access")
    user_id, _ = _validate_version(payload)
    user = crud.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="账户不存在或已被注销")
    return user


def get_optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[Dict[str, Any]]:
    """可空版本：游客（无 token）返回 None，用于「游客路径保留」的场景。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
        user_id, _ = _validate_version(payload)
    except HTTPException:
        return None
    return crud.get_user_by_id(user_id)
