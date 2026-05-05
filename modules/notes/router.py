from fastapi import APIRouter, Request, HTTPException
import psycopg2.extras
from core.db import db
from core.auth import require_role

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("")
def get_notes(request: Request):
    require_role(request, "admin", "teacher")
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, text, priority, done, created_at
                FROM school_notes WHERE done = FALSE
                ORDER BY
                    CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
                    created_at DESC
            """)
            notes = cur.fetchall()
    return {"notes": [dict(n) for n in notes]}


@router.post("/add")
def add_note(request: Request, data: dict):
    require_role(request, "admin", "teacher")
    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст обязателен")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO school_notes (text, priority) VALUES (%s, %s) RETURNING id",
                (text, data.get("priority", "normal"))
            )
            return {"ok": True, "id": cur.fetchone()[0]}


@router.post("/done")
def mark_done(request: Request, data: dict):
    require_role(request, "admin", "teacher")
    if not data.get("id"):
        raise HTTPException(status_code=400, detail="id обязателен")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE school_notes SET done=%s WHERE id=%s",
                (bool(data.get("done", True)), data["id"])
            )
    return {"ok": True}


@router.post("/delete")
def delete_note(request: Request, data: dict):
    require_role(request, "admin", "teacher")
    if not data.get("id"):
        raise HTTPException(status_code=400, detail="id обязателен")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM school_notes WHERE id=%s", (data["id"],))
    return {"ok": True}


from core.db import today_msk, now_msk

DAYS_FULL = ['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье']


@router.get("/dashboard")
def dashboard_meta(request: Request):
    """Мета-данные для шапки страниц — дата, время, день недели."""
    require_auth(request)
    today = today_msk()
    return {
        "meta": {
            "date": today.strftime("%d.%m.%Y"),
            "weekday": DAYS_FULL[today.weekday()],
            "time": now_msk().strftime("%H:%M"),
        }
    }
