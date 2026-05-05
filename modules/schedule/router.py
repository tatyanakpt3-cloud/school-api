from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Request, Query
import psycopg2.extras
from core.db import db, today_msk
from core.auth import require_auth, require_role

router = APIRouter(prefix="/schedule", tags=["schedule"])

DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _lessons_query(date_from: date, date_to: date,
                   teacher_id: Optional[int] = None,
                   student_id: Optional[int] = None) -> list:
    filters = ["sc.lesson_date BETWEEN %s AND %s"]
    params: list = [date_from, date_to]
    if teacher_id:
        filters.append("sc.teacher_id = %s")
        params.append(teacher_id)
    if student_id:
        filters.append("sc.student_id = %s")
        params.append(student_id)

    sql = f"""
        SELECT sc.id, sc.lesson_date, sc.lesson_time, sc.duration_min,
               sc.status, sc.topic, sc.room_active,
               st.name AS student, st.id AS student_id,
               t.name  AS teacher, t.id  AS teacher_id
        FROM school_schedule sc
        JOIN school_students st ON sc.student_id = st.id
        LEFT JOIN school_teachers t ON sc.teacher_id = t.id
        WHERE {" AND ".join(filters)}
        ORDER BY sc.lesson_date, sc.lesson_time
    """
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {
            "id": r["id"],
            "date": r["lesson_date"].strftime("%d.%m.%Y"),
            "date_iso": r["lesson_date"].isoformat(),
            "weekday": DAYS[r["lesson_date"].weekday()],
            "time": r["lesson_time"].strftime("%H:%M"),
            "duration": r["duration_min"],
            "status": r["status"] or "scheduled",
            "topic": r["topic"] or "",
            "room_active": bool(r["room_active"]),
            "student": r["student"],
            "student_id": r["student_id"],
            "teacher": r["teacher"] or "",
            "teacher_id": r["teacher_id"],
        }
        for r in rows
    ]


@router.get("")
def get_schedule(
    request: Request,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    teacher_id: Optional[int] = Query(None),
    student_id: Optional[int] = Query(None),
):
    user = require_auth(request)
    today = today_msk()
    df = date_from or today
    dt = date_to or (today + timedelta(days=6))

    # Учитель видит только своих
    if user["role"] == "teacher" and not teacher_id:
        teacher_id = user["ref_id"]
    # Ученик видит только себя
    if user["role"] == "student" and not student_id:
        student_id = user["ref_id"]

    lessons = _lessons_query(df, dt, teacher_id, student_id)
    return {
        "lessons": lessons,
        "meta": {
            "today_iso": today.isoformat(),
            "date_from": df.isoformat(),
            "date_to": dt.isoformat(),
        },
    }


@router.post("/action")
def schedule_action(request: Request, data: dict):
    user = require_role(request, "admin", "teacher")
    action = data.get("action")

    with db() as conn:
        with conn.cursor() as cur:
            if action == "complete":
                cur.execute(
                    "UPDATE school_schedule SET status='completed', topic=%s, updated_at=NOW() "
                    "WHERE id=%s RETURNING id",
                    (data.get("topic", ""), data["id"]),
                )
                return {"ok": bool(cur.fetchone())}

            if action == "cancel":
                cur.execute(
                    "UPDATE school_schedule SET status='cancelled', cancel_reason=%s, updated_at=NOW() "
                    "WHERE id=%s RETURNING id",
                    (data.get("reason", ""), data["id"]),
                )
                return {"ok": bool(cur.fetchone())}

            if action == "add":
                cur.execute(
                    "INSERT INTO school_schedule (student_id, teacher_id, lesson_date, lesson_time, duration_min, status) "
                    "VALUES (%s, %s, %s, %s, %s, 'scheduled') RETURNING id",
                    (data["student_id"], data.get("teacher_id"),
                     data["date"], data["time"], data.get("duration", 60)),
                )
                return {"ok": True, "id": cur.fetchone()[0]}

    raise HTTPException(status_code=400, detail=f"Неизвестное действие: {action}")
