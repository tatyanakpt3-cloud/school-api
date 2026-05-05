from fastapi import APIRouter, Request, Query
from typing import Optional
import psycopg2.extras
from core.db import db, today_msk
from core.auth import require_auth, require_role

router = APIRouter(prefix="/students", tags=["students"])


@router.get("")
def get_students(request: Request):
    require_role(request, "admin", "teacher")
    today = today_msk()

    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT s.id, s.name, s.grade, s.parent_name, s.parent_telegram_id,
                       s.student_telegram_id, s.active, s.price_per_lesson,
                       s.lessons_per_week, s.lesson_format, s.lesson_duration,
                       s.payment_period, s.hw_to_student, s.notes,
                       t.id AS teacher_id, t.name AS teacher_name
                FROM school_students s
                LEFT JOIN school_teachers t ON s.teacher_id = t.id
                ORDER BY s.active DESC, s.name
            """)
            students = cur.fetchall()

            cur.execute("""
                SELECT t.id, t.name, t.active, t.is_owner
                FROM school_teachers t ORDER BY t.name
            """)
            teachers = cur.fetchall()

            cur.execute("SELECT COUNT(*) FROM school_students WHERE active=TRUE")
            active = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) FROM school_students")
            total = cur.fetchone()["count"]

            # Следующий урок для каждого ученика
            cur.execute("""
                SELECT DISTINCT ON (student_id)
                    student_id, lesson_date, lesson_time
                FROM school_schedule
                WHERE status='scheduled' AND lesson_date >= %s
                ORDER BY student_id, lesson_date, lesson_time
            """, (today,))
            next_lessons = {r["student_id"]: {
                "date": r["lesson_date"].strftime("%d.%m.%Y"),
                "time": r["lesson_time"].strftime("%H:%M")
            } for r in cur.fetchall()}

    return {
        "students": [
            {**dict(s),
             "teacher": s["teacher_name"] or "",
             "next_lesson": next_lessons.get(s["id"])}
            for s in students
        ],
        "teachers": [dict(t) for t in teachers],
        "active": active,
        "total": total,
        "meta": {"today": today.strftime("%d.%m.%Y")},
    }


@router.post("/action")
def students_action(request: Request, data: dict):
    require_role(request, "admin", "teacher")
    action = data.get("action")

    with db() as conn:
        with conn.cursor() as cur:
            if action == "archive":
                cur.execute(
                    "UPDATE school_students SET active=FALSE WHERE id=%s RETURNING id",
                    (data["student_id"],)
                )
                return {"ok": bool(cur.fetchone())}

            if action == "restore":
                cur.execute(
                    "UPDATE school_students SET active=TRUE WHERE id=%s RETURNING id",
                    (data["student_id"],)
                )
                return {"ok": bool(cur.fetchone())}

            if action == "update":
                fields = []
                values = []
                allowed = ["name", "grade", "price_per_lesson", "lessons_per_week",
                          "lesson_format", "lesson_duration", "payment_period",
                          "teacher_id", "notes", "hw_to_student"]
                for k in allowed:
                    if k in data:
                        fields.append(f"{k}=%s")
                        values.append(data[k])
                if fields:
                    values.append(data["student_id"])
                    cur.execute(
                        f"UPDATE school_students SET {', '.join(fields)} WHERE id=%s RETURNING id",
                        values
                    )
                return {"ok": bool(cur.fetchone())}

    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail=f"Неизвестное действие: {action}")
