from typing import Optional
from fastapi import APIRouter, Request, HTTPException
import psycopg2.extras
from core.db import db, now_msk
from core.auth import require_auth

router = APIRouter(prefix="/chat", tags=["chat"])

VALID_CHANNELS = {"teacher_parent", "teacher_student", "family"}


@router.get("")
def get_messages(
    request: Request,
    student_id: int,
    channel: str = "teacher_parent",
    limit: int = 50,
):
    user = require_auth(request)
    if channel not in VALID_CHANNELS:
        raise HTTPException(status_code=400, detail=f"Неверный канал: {channel}")

    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, sender_role, sender_name, message_type, text, file_url, "
                "read_by_parent, read_by_teacher, created_at "
                "FROM school_chat "
                "WHERE student_id=%s AND channel=%s AND COALESCE(is_deleted,FALSE)=FALSE "
                "ORDER BY created_at DESC LIMIT %s",
                (student_id, channel, limit),
            )
            rows = cur.fetchall()

    role = user["role"]
    return {
        "messages": [
            {
                "id": r["id"],
                "role": r["sender_role"],
                "name": r["sender_name"] or "",
                "type": r["message_type"] or "text",
                "text": r["text"] or "",
                "file_url": r["file_url"],
                "time": r["created_at"].strftime("%d.%m %H:%M"),
                "read": bool(r["read_by_parent"] if role == "parent" else r["read_by_teacher"]),
            }
            for r in reversed(rows)
        ]
    }


@router.post("/send")
def send_message(request: Request, data: dict):
    user = require_auth(request)
    student_id = data.get("student_id")
    channel = data.get("channel", "teacher_parent")
    text = (data.get("message_text") or data.get("text") or "").strip()
    file_url = data.get("file") or data.get("file_url") or ""

    if not student_id or (not text and not file_url):
        raise HTTPException(status_code=400, detail="student_id и текст или файл обязательны")
    if channel not in VALID_CHANNELS:
        raise HTTPException(status_code=400, detail=f"Неверный канал: {channel}")

    # family канал — только родители, без уведомлений учителя
    if channel == "family" and user["role"] not in ("parent", "admin"):
        raise HTTPException(status_code=403, detail="family канал только для родителей")

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO school_chat "
                "(student_id, channel, sender_role, sender_name, message_type, text, file_url, "
                "read_by_parent, read_by_teacher, created_at) "
                "VALUES (%s,%s,%s,%s,'text',%s,%s,%s,%s,%s) RETURNING id",
                (student_id, channel, user["role"], user.get("name", ""),
                 text or None, file_url or None,
                 user["role"] == "parent",
                 user["role"] == "teacher",
                 now_msk()),
            )
            msg_id = cur.fetchone()[0]

    return {"ok": True, "id": msg_id}


@router.post("/read")
def mark_read(request: Request, data: dict):
    user = require_auth(request)
    student_id = data.get("student_id")
    channel = data.get("channel", "teacher_parent")
    role = user["role"]

    # Помечаем как прочитанные сообщения от другой стороны
    col = "read_by_parent" if role == "parent" else "read_by_teacher"
    exclude_role = "parent" if role != "parent" else "teacher"

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE school_chat SET {col}=TRUE "
                "WHERE student_id=%s AND channel=%s AND sender_role=%s AND NOT " + col,
                (student_id, channel, exclude_role),
            )
    return {"ok": True}


@router.post("/delete")
def delete_message(request: Request, data: dict):
    require_auth(request)
    msg_id = data.get("id")
    if not msg_id:
        raise HTTPException(status_code=400, detail="id обязателен")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE school_chat SET is_deleted=TRUE, deleted_at=NOW() WHERE id=%s RETURNING id",
                (msg_id,)
            )
            return {"ok": bool(cur.fetchone())}
