from fastapi import APIRouter, Request, HTTPException
import psycopg2.extras
from core.db import db, now_msk
from core.auth import require_role, require_auth

router = APIRouter(prefix="/lesson", tags=["lessons"])


@router.post("/report")
def lesson_report(request: Request, data: dict):
    user = require_role(request, "admin", "teacher")
    schedule_id = data.get("schedule_id")
    student_id  = data.get("student_id")
    topic       = (data.get("topic") or "").strip()
    comment     = (data.get("comment") or "").strip()
    hw_text     = (data.get("homework_text") or "").strip()
    hw_file     = (data.get("homework_file") or "").strip()
    hw_ftype    = (data.get("homework_file_type") or "").strip()
    teacher_id  = user["ref_id"]

    if not schedule_id or not topic:
        raise HTTPException(status_code=400, detail="schedule_id и topic обязательны")

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE school_schedule SET status='completed', topic=%s, updated_at=NOW() WHERE id=%s RETURNING student_id",
                (topic, schedule_id)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Урок не найден")
            if not student_id:
                student_id = row[0]

            if comment:
                cur.execute(
                    "INSERT INTO school_lesson_comments (schedule_id, teacher_id, student_id, comment, visible_to_parent) "
                    "VALUES (%s,%s,%s,%s,TRUE)",
                    (schedule_id, teacher_id, student_id, comment)
                )

            hw_id = None
            if hw_text or hw_file:
                text = hw_text or f"(файл: {hw_ftype})"
                cur.execute(
                    "INSERT INTO school_homework (student_id, teacher_id, direction, message_text, file_id, file_type, status, schedule_id) "
                    "VALUES (%s,%s,'teacher_to_student',%s,%s,%s,'new',%s) RETURNING id",
                    (student_id, teacher_id, text, hw_file or None, hw_ftype or None, schedule_id)
                )
                hw_id = cur.fetchone()[0]

    return {"ok": True, "hw_id": hw_id}


@router.post("/comment")
def lesson_comment(request: Request, data: dict):
    user = require_role(request, "admin", "teacher")
    schedule_id = data.get("schedule_id")
    student_id  = data.get("student_id")
    comment     = (data.get("comment") or "").strip()

    if not schedule_id or not comment:
        raise HTTPException(status_code=400, detail="schedule_id и comment обязательны")

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO school_lesson_comments (schedule_id, teacher_id, student_id, comment, visible_to_parent) "
                "VALUES (%s,%s,%s,%s,TRUE) RETURNING id",
                (schedule_id, user["ref_id"], student_id, comment)
            )
            return {"ok": True, "id": cur.fetchone()[0]}


@router.post("/start")
def lesson_start(request: Request, data: dict):
    require_role(request, "admin", "teacher")
    schedule_id = data.get("schedule_id")
    if not schedule_id:
        raise HTTPException(status_code=400, detail="schedule_id обязателен")

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE school_schedule SET room_active=TRUE, room_started_at=NOW() WHERE id=%s RETURNING id",
                (schedule_id,)
            )
            return {"ok": bool(cur.fetchone())}


@router.get("/comments")
def get_comments(request: Request):
    require_role(request, "admin", "teacher")
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT lc.id, lc.comment, lc.created_at,
                       s.name AS student, t.name AS teacher,
                       sc.lesson_date, sc.topic
                FROM school_lesson_comments lc
                JOIN school_students s ON lc.student_id = s.id
                LEFT JOIN school_teachers t ON lc.teacher_id = t.id
                LEFT JOIN school_schedule sc ON lc.schedule_id = sc.id
                WHERE lc.visible_to_parent = TRUE
                ORDER BY lc.created_at DESC LIMIT 30
            """)
            rows = cur.fetchall()

    return {
        "comments": [
            {
                "id": r["id"],
                "comment": r["comment"],
                "student": r["student"],
                "teacher": r["teacher"] or "",
                "date": r["lesson_date"].strftime("%d.%m.%Y") if r["lesson_date"] else "",
                "topic": r["topic"] or "",
                "created": r["created_at"].strftime("%d.%m %H:%M"),
            }
            for r in rows
        ]
    }
