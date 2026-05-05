from typing import Optional
from datetime import date
from fastapi import APIRouter, Request, Query
import psycopg2.extras
from core.db import db
from core.auth import require_auth

router = APIRouter(prefix="/reports", tags=["reports"])

HW_STATUS_SQL = """
    CASE
      WHEN EXISTS(
        SELECT 1 FROM school_homework h
        WHERE h.student_id=sc.student_id
          AND (h.schedule_id=sc.id OR h.created_at::date BETWEEN sc.lesson_date-2 AND sc.lesson_date+2)
          AND h.direction='student_to_teacher' AND h.checked_at IS NOT NULL
      ) THEN 'checked'
      WHEN EXISTS(
        SELECT 1 FROM school_homework h
        WHERE h.student_id=sc.student_id
          AND (h.schedule_id=sc.id OR h.created_at::date BETWEEN sc.lesson_date-2 AND sc.lesson_date+2)
          AND h.direction='student_to_teacher'
      ) THEN 'submitted'
      WHEN EXISTS(
        SELECT 1 FROM school_homework h
        WHERE h.student_id=sc.student_id
          AND (h.schedule_id=sc.id OR h.created_at::date BETWEEN sc.lesson_date-2 AND sc.lesson_date+2)
          AND h.direction='teacher_to_student'
      ) THEN 'sent'
      ELSE NULL
    END
"""

HW_TEXT_SQL = """
    (SELECT string_agg(h.message_text, '; ')
     FROM school_homework h
     WHERE h.student_id=sc.student_id
       AND h.direction='teacher_to_student'
       AND (h.schedule_id=sc.id OR h.created_at::date BETWEEN sc.lesson_date-2 AND sc.lesson_date+2))
"""


@router.get("")
def get_reports(
    request: Request,
    student_id: Optional[int] = Query(None),
    teacher_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(200),
):
    user = require_auth(request)
    if user["role"] == "teacher" and not teacher_id:
        teacher_id = user["ref_id"]

    filters = ["sc.status='completed'", "sc.topic IS NOT NULL", "sc.topic!=''"]
    params: list = []
    if student_id:
        filters.append("sc.student_id=%s")
        params.append(student_id)
    if teacher_id:
        filters.append("sc.teacher_id=%s")
        params.append(teacher_id)
    if date_from:
        filters.append("sc.lesson_date>=%s")
        params.append(date_from)
    if date_to:
        filters.append("sc.lesson_date<=%s")
        params.append(date_to)
    params.append(limit)

    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT sc.id, sc.lesson_date, sc.lesson_time,
                       s.name AS student, t.name AS teacher,
                       sc.topic, lc.comment,
                       {HW_TEXT_SQL} AS homework,
                       {HW_STATUS_SQL} AS hw_status
                FROM school_schedule sc
                JOIN school_students s ON sc.student_id=s.id
                LEFT JOIN school_teachers t ON sc.teacher_id=t.id
                LEFT JOIN school_lesson_comments lc
                    ON lc.schedule_id=sc.id AND lc.visible_to_parent=TRUE
                WHERE {" AND ".join(filters)}
                ORDER BY sc.lesson_date DESC, sc.lesson_time DESC
                LIMIT %s
            """, params)
            rows = cur.fetchall()

            cur.execute(
                "SELECT DISTINCT s.id, s.name FROM school_students s "
                "JOIN school_schedule sc ON sc.student_id=s.id "
                "WHERE sc.status='completed' AND sc.topic IS NOT NULL ORDER BY s.name"
            )
            students = [{"id": r["id"], "name": r["name"]} for r in cur.fetchall()]

            cur.execute(
                "SELECT DISTINCT t.id, t.name FROM school_teachers t "
                "JOIN school_schedule sc ON sc.teacher_id=t.id "
                "WHERE sc.status='completed' AND sc.topic IS NOT NULL ORDER BY t.name"
            )
            teachers = [{"id": r["id"], "name": r["name"]} for r in cur.fetchall()]

    return {
        "reports": [
            {
                "id": r["id"],
                "date": r["lesson_date"].strftime("%d.%m.%Y"),
                "time": r["lesson_time"].strftime("%H:%M") if r["lesson_time"] else "",
                "student": r["student"],
                "teacher": r["teacher"] or "",
                "topic": r["topic"],
                "comment": r["comment"] or "",
                "homework": r["homework"] or "",
                "hw_status": r["hw_status"],
            }
            for r in rows
        ],
        "students": students,
        "teachers": teachers,
    }
