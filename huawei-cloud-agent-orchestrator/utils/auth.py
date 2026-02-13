"""
用户认证模块 - 基于签名Cookie的Session认证
"""

import hashlib
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Boolean, DateTime
from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse

from utils.database import Base, get_session


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(128), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


def hash_password(plain: str) -> str:
    """SHA-256 哈希密码"""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码"""
    return hash_password(plain) == hashed


def init_default_user():
    """首次启动时创建默认管理员账号 admin / robo@123"""
    with get_session() as session:
        existing = session.query(User).filter_by(username="admin").first()
        if not existing:
            user = User(
                username="admin",
                password_hash=hash_password("robo@123"),
            )
            session.add(user)
            session.commit()
            print("已创建默认管理员账号: admin")


def authenticate(username: str, password: str) -> Optional[User]:
    """验证登录，返回 user 或 None"""
    with get_session() as session:
        user = session.query(User).filter_by(username=username, is_active=True).first()
        if user and verify_password(password, user.password_hash):
            # 分离对象，避免 session 关闭后无法访问属性
            session.expunge(user)
            return user
    return None


def get_current_user(request: Request) -> Optional[User]:
    """从 session 读取 user_id，查库返回用户"""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    with get_session() as session:
        user = session.get(User, user_id)
        if user:
            session.expunge(user)
        return user


from starlette.middleware.base import BaseHTTPMiddleware

# 不需要认证的路径前缀
AUTH_WHITELIST = ["/login", "/logout", "/api/auth/login", "/static", "/favicon.ico"]


class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件：未登录时页面请求重定向到 /login，API请求返回 401"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 白名单路径不需要认证
        if any(path == p or path.startswith(p + "/") or path.startswith(p + "?")
               for p in AUTH_WHITELIST):
            return await call_next(request)

        user = get_current_user(request)
        if user:
            request.state.user = user
            return await call_next(request)

        # 未登录
        if path.startswith("/api/"):
            return JSONResponse(
                {"success": False, "error": "未登录", "redirect": "/login"},
                status_code=401,
            )
        return RedirectResponse(url="/login", status_code=302)
