"""
Онбординг нового учителя на Mira School.
Администратор вводит имя — система создаёт тенант, школу, токен.
Готово к работе за 5 минут.
"""
import secrets
from fastapi import APIRouter, Request, HTTPException
import psycopg2.extras
from core.db import db
from core.auth import require_role

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/teacher")
def onboard_teacher(request: Request, data: dict):
    """Создать нового учителя на платформе. Возвращает токен для входа."""
    require_role(request, "admin")

    name  = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    slug  = (data.get("slug") or "").strip().lower().replace(" ", "-")

    if not name:
        raise HTTPException(status_code=400, detail="Имя учителя обязательно")
    if not slug:
        slug = name.lower().replace(" ", "-").replace(".", "")[:20]

    token = secrets.token_urlsafe(24)

    with db() as conn:
        with conn.cursor() as cur:
            # 1. Тенант
            cur.execute(
                "INSERT INTO tenants (slug, name) VALUES (%s, %s) RETURNING id",
                (slug, name)
            )
            tenant_id = cur.fetchone()[0]

            # 2. Токен доступа
            cur.execute(
                "INSERT INTO school_auth_tokens (token, role, name, ref_id, active, tenant_id) "
                "VALUES (%s, 'teacher', %s, 1, TRUE, %s) RETURNING id",
                (token, name, tenant_id)
            )

    cabinet_url = f"https://mira.school/cabinet/login.html?token={token}"

    return {
        "ok": True,
        "teacher": name,
        "tenant_id": tenant_id,
        "slug": slug,
        "token": token,
        "cabinet_url": cabinet_url,
        "message": f"Учитель {name} подключён. Токен для входа: {token}",
    }


@router.get("/tenants")
def list_tenants(request: Request):
    """Список всех школ на платформе."""
    require_role(request, "admin")

    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT t.id, t.slug, t.name, t.active, t.created_at,
                       COUNT(DISTINCT tok.id) AS tokens
                FROM tenants t
                LEFT JOIN school_auth_tokens tok ON tok.tenant_id = t.id AND tok.active = TRUE
                GROUP BY t.id ORDER BY t.created_at DESC
            """)
            tenants = cur.fetchall()

    return {
        "tenants": [
            {
                "id": r["id"],
                "slug": r["slug"],
                "name": r["name"],
                "active": r["active"],
                "created": r["created_at"].strftime("%d.%m.%Y"),
                "tokens": r["tokens"],
            }
            for r in tenants
        ]
    }
