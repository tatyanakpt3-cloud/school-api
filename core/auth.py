from fastapi import Request, HTTPException
import psycopg2
from .db import get_conn


def get_token(request: Request) -> str:
    # Cookie
    token = request.cookies.get("school_token", "") or request.cookies.get("mira_token", "")
    if token:
        return token
    # Authorization: Bearer <token>
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    # X-School-Token header
    return request.headers.get("X-School-Token", "")


def require_auth(request: Request) -> dict:
    token = get_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT token, role, name, ref_id, telegram_id "
                "FROM school_auth_tokens WHERE token=%s AND active=TRUE",
                (token,)
            )
            row = cur.fetchone()
        conn.close()
    except Exception:
        raise HTTPException(status_code=500, detail="Ошибка БД")
    if not row:
        raise HTTPException(status_code=401, detail="Токен недействителен")
    return dict(row)


def require_role(request: Request, *roles: str) -> dict:
    user = require_auth(request)
    if user["role"] not in roles:
        raise HTTPException(status_code=403, detail="Нет доступа")
    return user
