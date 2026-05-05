from fastapi import APIRouter, Request, HTTPException
import psycopg2.extras
from core.db import db
from core.auth import require_auth, require_role

router = APIRouter(prefix="/vpr", tags=["vpr"])

TOPIC_MAP = {
    '1': 'vpr6_arithmetic', '2_1': 'vpr6_drobi', '2_2': 'vpr6_drobi',
    '3': 'vpr6_drobi', '4': 'vpr6_diagrammy', '5': 'vpr6_procenty',
    '6': 'vpr6_algebra', '7': 'vpr6_koord', '8': 'vpr6_uravneniya',
    '9': 'vpr6_diagrammy', '10': 'vpr6_logika', '11': 'vpr6_geometria',
    '12': 'vpr6_zadachi', '13': 'vpr6_drobi', '14': 'vpr6_zadachi',
    '15': 'vpr6_zadachi', '16': 'vpr6_zadachi', '17': 'vpr6_procenty',
}


@router.get("/list")
def vpr_list(request: Request):
    user = require_role(request, "admin", "teacher")
    teacher_id = user.get("ref_id")

    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if teacher_id:
                cur.execute("""
                    SELECT a.*, s.name AS student_name
                    FROM student_assignments a
                    JOIN school_students s ON s.id = a.student_id
                    WHERE a.teacher_id = %s
                    ORDER BY a.created_at DESC LIMIT 50
                """, (teacher_id,))
            else:
                cur.execute("""
                    SELECT a.*, s.name AS student_name
                    FROM student_assignments a
                    JOIN school_students s ON s.id = a.student_id
                    ORDER BY a.created_at DESC LIMIT 50
                """)
            rows = cur.fetchall()

    return {"items": [dict(r) for r in rows]}


@router.post("/complete")
def vpr_complete(request: Request, data: dict):
    require_auth(request)
    student_id = data.get("student_id")
    variant    = data.get("variant")
    score      = data.get("score", 0)
    answers    = data.get("answers", {})

    if not student_id or not variant:
        raise HTTPException(status_code=400, detail="student_id и variant обязательны")

    topics_hit = list({TOPIC_MAP[k] for k in answers if k in TOPIC_MAP and answers[k]})

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO vpr_submissions
                    (student_id, variant, score, answers, topics_hit, submitted_at)
                VALUES (%s,%s,%s,%s,%s,NOW()) RETURNING id
            """, (student_id, variant, score, psycopg2.extras.Json(answers),
                  topics_hit))
            sub_id = cur.fetchone()[0]

            cur.execute("""
                UPDATE student_assignments SET status='completed', score=%s,
                    completed_at=NOW() WHERE student_id=%s AND variant=%s
                    AND status != 'completed'
            """, (score, student_id, str(variant)))

    return {"ok": True, "id": sub_id}
