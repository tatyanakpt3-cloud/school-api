from typing import Optional
from fastapi import APIRouter, Request
import psycopg2.extras
from core.db import db
from core.auth import require_auth, require_role

router = APIRouter(prefix="/homework", tags=["homework"])


@router.get("")
def get_homework(request: Request, student_id: Optional[int] = None):
    user = require_auth(request)
    if user["role"] == "student":
        student_id = user["ref_id"]

    filters = ["direction = 'teacher_to_student'"]
    params: list = []
    if student_id:
        filters.append("student_id = %s")
        params.append(student_id)

    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT id, student_id, teacher_id, direction, message_text, "
                f"file_id, file_type, status, schedule_id, created_at, checked_at "
                f"FROM school_homework WHERE {' AND '.join(filters)} "
                f"ORDER BY created_at DESC LIMIT 50",
                params,
            )
            rows = cur.fetchall()

    return {
        "homework": [
            {
                "id": r["id"],
                "text": r["message_text"] or "",
                "file_id": r["file_id"],
                "file_type": r["file_type"],
                "status": r["status"] or "sent",
                "created": r["created_at"].strftime("%d.%m %H:%M"),
                "checked": r["checked_at"].strftime("%d.%m %H:%M") if r["checked_at"] else None,
            }
            for r in rows
        ]
    }


@router.post("/send")
def send_homework(request: Request, data: dict):
    user = require_role(request, "admin", "teacher")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO school_homework "
                "(student_id, teacher_id, direction, message_text, status, schedule_id) "
                "VALUES (%s, %s, 'teacher_to_student', %s, 'new', %s) RETURNING id",
                (data["student_id"], user["ref_id"],
                 data.get("text", ""), data.get("schedule_id")),
            )
            hw_id = cur.fetchone()[0]
    return {"ok": True, "id": hw_id}


@router.post("/check")
def check_homework(request: Request, data: dict):
    user = require_role(request, "admin", "teacher")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE school_homework SET status='checked', checked_at=NOW(), "
                "checked_comment=%s WHERE id=%s RETURNING id",
                (data.get("comment", ""), data["id"]),
            )
            return {"ok": bool(cur.fetchone())}


import os
import uuid
from fastapi import UploadFile, File, Form
from typing import Optional as Opt


@router.post("/upload")
async def upload_homework(
    request: Request,
    student_id: int = Form(...),
    teacher_id: Opt[int] = Form(None),
    text: str = Form(""),
    direction: Opt[str] = Form(None),
    file: Opt[UploadFile] = File(None),
):
    user = require_auth(request)

    # Определяем направление по роли
    if not direction:
        direction = "student_to_teacher" if user["role"] in ("parent", "student") else "teacher_to_student"

    # Если учитель не указан — берём из карточки ученика
    if not teacher_id:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT teacher_id FROM school_students WHERE id=%s", (student_id,))
                row = cur.fetchone()
                teacher_id = row[0] if row else None

    file_path = ""
    file_type = ""
    if file and file.filename:
        upload_dir = "/var/www/school-dashboard/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(file.filename)[1]
        fname = f"{uuid.uuid4().hex}{ext}"
        fpath = os.path.join(upload_dir, fname)
        content = await file.read()
        with open(fpath, "wb") as f:
            f.write(content)
        file_path = f"/school-dashboard/uploads/{fname}"
        file_type = ext.lstrip(".") or "file"

    msg_text = text or f"(файл: {file_type})"

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO school_homework (student_id, teacher_id, direction, message_text, file_id, file_type, status, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,'new',NOW()) RETURNING id",
                (student_id, teacher_id, direction, msg_text, file_path, file_type)
            )
            hw_id = cur.fetchone()[0]

            if direction == "student_to_teacher":
                cur.execute(
                    "UPDATE school_homework SET status='submitted' "
                    "WHERE id=(SELECT id FROM school_homework WHERE student_id=%s AND direction='teacher_to_student' "
                    "AND status='new' ORDER BY created_at DESC LIMIT 1) RETURNING id",
                    (student_id,)
                )

    return {"ok": True, "id": hw_id, "file_url": file_path}
