from datetime import date, timedelta
from typing import Optional
import calendar
from fastapi import APIRouter, Request, Query, Response
import psycopg2.extras
from core.db import db, today_msk, now_msk
from core.auth import require_auth, require_role

router = APIRouter(prefix="/finance", tags=["finance"])

RU_MONTHS = {1:'Янв',2:'Фев',3:'Мар',4:'Апр',5:'Май',6:'Июн',
             7:'Июл',8:'Авг',9:'Сен',10:'Окт',11:'Ноя',12:'Дек'}
RU_MONTHS_FULL = {1:'Январь',2:'Февраль',3:'Март',4:'Апрель',5:'Май',6:'Июнь',
                  7:'Июль',8:'Август',9:'Сентябрь',10:'Октябрь',11:'Ноябрь',12:'Декабрь'}
CAT_NAMES = {
    'svetlana_individual': 'Светлана (инд.)',
    'svetlana_group': 'Светлана (группы)',
    'teachers_individual': 'Преподаватели (инд.)',
    'teachers_group': 'Преподаватели (группы)',
}


def ru_month(d): return f"{RU_MONTHS[d.month]} {d.year}"
def ru_month_full(d): return RU_MONTHS_FULL[d.month]


@router.get("")
def get_finance(request: Request):
    require_role(request, "admin", "teacher")
    today = today_msk()
    month_start = today.replace(day=1)

    with db() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT DATE_TRUNC('month', sc.lesson_date)::date,
                       COALESCE(SUM(s.price_per_lesson), 0),
                       COALESCE(SUM(CASE WHEN t.is_owner THEN s.price_per_lesson ELSE 0 END), 0),
                       COALESCE(SUM(CASE WHEN NOT COALESCE(t.is_owner,FALSE) THEN s.price_per_lesson ELSE 0 END), 0),
                       COUNT(*)
                FROM school_schedule sc
                JOIN school_students s ON sc.student_id = s.id
                LEFT JOIN school_teachers t ON sc.teacher_id = t.id
                WHERE sc.status = 'completed'
                  AND sc.lesson_date >= (CURRENT_DATE - INTERVAL '12 months')
                GROUP BY 1 ORDER BY 1
            """)
            by_month = [{'month': r[0].strftime('%Y-%m'), 'month_label': ru_month(r[0]),
                         'revenue': int(r[1]), 'revenue_owner': int(r[2]),
                         'revenue_hired': int(r[3]), 'lessons': r[4]}
                        for r in cur.fetchall()]

            cur.execute("""
                SELECT DATE_TRUNC('week', sc.lesson_date)::date,
                       COALESCE(SUM(s.price_per_lesson), 0), COUNT(*)
                FROM school_schedule sc
                JOIN school_students s ON sc.student_id = s.id
                WHERE sc.status = 'completed'
                  AND sc.lesson_date >= (CURRENT_DATE - INTERVAL '12 weeks')
                GROUP BY 1 ORDER BY 1
            """)
            by_week = [{'week': r[0].strftime('%d.%m'), 'revenue': int(r[1]), 'lessons': r[2]}
                       for r in cur.fetchall()]

            cur.execute("""
                SELECT t.name, t.id, COALESCE(SUM(s.price_per_lesson), 0), COUNT(*)
                FROM school_schedule sc
                JOIN school_students s ON sc.student_id = s.id
                JOIN school_teachers t ON sc.teacher_id = t.id
                WHERE sc.status = 'completed' AND sc.lesson_date >= %s AND sc.lesson_date <= %s
                GROUP BY t.name, t.id ORDER BY 3 DESC
            """, (month_start, today))
            by_teacher = [{'teacher': r[0], 'teacher_id': r[1],
                           'revenue': int(r[2]), 'lessons': r[3]}
                          for r in cur.fetchall()]

            cur.execute("""
                SELECT DATE_TRUNC('month', sc.lesson_date)::date, t.name,
                       COALESCE(SUM(s.price_per_lesson), 0), COUNT(*)
                FROM school_schedule sc
                JOIN school_students s ON sc.student_id = s.id
                JOIN school_teachers t ON sc.teacher_id = t.id
                WHERE sc.status = 'completed'
                  AND sc.lesson_date >= (CURRENT_DATE - INTERVAL '12 months')
                GROUP BY 1, 2 ORDER BY 1, 2
            """)
            by_teacher_month = [{'month': r[0].strftime('%Y-%m'), 'teacher': r[1],
                                  'revenue': int(r[2]), 'lessons': r[3]}
                                 for r in cur.fetchall()]

            cur.execute("""
                SELECT s.lesson_format, COALESCE(SUM(s.price_per_lesson), 0), COUNT(*)
                FROM school_schedule sc JOIN school_students s ON sc.student_id = s.id
                WHERE sc.status = 'completed' AND sc.lesson_date >= %s AND sc.lesson_date <= %s
                GROUP BY 1 ORDER BY 2 DESC
            """, (month_start, today))
            by_category = [{'category': r[0] or 'individual', 'revenue': int(r[1]), 'lessons': r[2]}
                           for r in cur.fetchall()]

            cur.execute("""
                SELECT COALESCE(SUM(s.price_per_lesson), 0),
                       COALESCE(SUM(CASE WHEN t.is_owner THEN s.price_per_lesson ELSE 0 END), 0),
                       COALESCE(SUM(CASE WHEN NOT COALESCE(t.is_owner,FALSE) THEN s.price_per_lesson ELSE 0 END), 0),
                       COUNT(*)
                FROM school_schedule sc JOIN school_students s ON sc.student_id = s.id
                LEFT JOIN school_teachers t ON sc.teacher_id = t.id
                WHERE sc.status = 'completed' AND sc.lesson_date >= %s AND sc.lesson_date <= %s
            """, (month_start, today))
            m = cur.fetchone()
            month_revenue, month_revenue_owner, month_revenue_hired, month_lessons = \
                int(m[0]), int(m[1]), int(m[2]), m[3]

            prev_end = month_start - timedelta(days=1)
            prev_start = prev_end.replace(day=1)
            cur.execute("""
                SELECT COALESCE(SUM(s.price_per_lesson), 0),
                       COALESCE(SUM(CASE WHEN t.is_owner THEN s.price_per_lesson ELSE 0 END), 0),
                       COALESCE(SUM(CASE WHEN NOT COALESCE(t.is_owner,FALSE) THEN s.price_per_lesson ELSE 0 END), 0),
                       COUNT(*)
                FROM school_schedule sc JOIN school_students s ON sc.student_id = s.id
                LEFT JOIN school_teachers t ON sc.teacher_id = t.id
                WHERE sc.status = 'completed' AND sc.lesson_date >= %s AND sc.lesson_date <= %s
            """, (prev_start, prev_end))
            p = cur.fetchone()
            prev_revenue, prev_revenue_owner, prev_revenue_hired, prev_lessons = \
                int(p[0]), int(p[1]), int(p[2]), p[3]

            cur.execute("""
                SELECT COALESCE(SUM(s.price_per_lesson * s.lessons_per_week * 4), 0),
                       COALESCE(SUM(CASE WHEN t.is_owner THEN s.price_per_lesson * s.lessons_per_week * 4 ELSE 0 END), 0),
                       COALESCE(SUM(CASE WHEN NOT COALESCE(t.is_owner,FALSE) THEN s.price_per_lesson * s.lessons_per_week * 4 ELSE 0 END), 0)
                FROM school_students s LEFT JOIN school_teachers t ON s.teacher_id = t.id
                WHERE s.active = TRUE AND s.price_per_lesson IS NOT NULL
            """)
            pr = cur.fetchone()
            planned, planned_owner, planned_hired = int(pr[0] or 0), int(pr[1] or 0), int(pr[2] or 0)

            cur.execute("""
                SELECT s.name, t.name, COALESCE(SUM(s.price_per_lesson), 0), COUNT(*)
                FROM school_schedule sc JOIN school_students s ON sc.student_id = s.id
                LEFT JOIN school_teachers t ON sc.teacher_id = t.id
                WHERE sc.status = 'completed' AND sc.lesson_date >= %s AND sc.lesson_date <= %s
                GROUP BY s.name, t.name ORDER BY 3 DESC LIMIT 15
            """, (month_start, today))
            top_students = [{'student': r[0], 'teacher': r[1] or '',
                             'revenue': int(r[2]), 'lessons': r[3]}
                            for r in cur.fetchall()]

            cur.execute("""
                SELECT period,
                       SUM(revenue), SUM(CASE WHEN category LIKE 'svetlana%' THEN revenue ELSE 0 END),
                       SUM(CASE WHEN category LIKE 'teachers%' THEN revenue ELSE 0 END),
                       SUM(teacher_salary), SUM(profit), SUM(students_total),
                       SUM(marketing_cost), SUM(revenue_plan), SUM(students_plan)
                FROM school_finance_history GROUP BY period ORDER BY period
            """)
            history_months = []
            for row in cur.fetchall():
                p2, rev, rev_own, rev_hir, sal, prof, stu, mkt, rev_plan, stu_plan = row
                history_months.append({
                    'month': p2.strftime('%Y-%m'), 'month_label': ru_month(p2),
                    'revenue': int(rev or 0), 'revenue_owner': int(rev_own or 0),
                    'revenue_hired': int(rev_hir or 0), 'salary': int(sal or 0),
                    'profit': int(prof or 0), 'students': int(stu or 0),
                    'marketing': int(mkt or 0), 'revenue_plan': int(rev_plan or 0),
                    'students_plan': int(stu_plan or 0),
                })

            cur.execute("""
                SELECT category, SUM(revenue), SUM(teacher_salary), SUM(profit)
                FROM school_finance_history GROUP BY category ORDER BY 2 DESC
            """)
            history_categories = [
                {'category': CAT_NAMES.get(r[0], r[0]), 'category_key': r[0],
                 'revenue': int(r[1] or 0), 'salary': int(r[2] or 0), 'profit': int(r[3] or 0)}
                for r in cur.fetchall()
            ]

            cur.execute("""
                SELECT period, category, revenue, teacher_salary, profit
                FROM school_finance_history ORDER BY period, category
            """)
            history_by_cat_month = [
                {'month': r[0].strftime('%Y-%m'), 'category': CAT_NAMES.get(r[1], r[1]),
                 'revenue': int(r[2] or 0), 'salary': int(r[3] or 0), 'profit': int(r[4] or 0)}
                for r in cur.fetchall()
            ]

            cur.execute("SELECT SUM(revenue), SUM(teacher_salary), SUM(profit), SUM(marketing_cost) FROM school_finance_history")
            h = cur.fetchone()

            cur.execute("SELECT id, name FROM school_teachers WHERE active = TRUE ORDER BY name")
            teachers = [{'id': r[0], 'name': r[1]} for r in cur.fetchall()]

    return {
        'by_month': by_month, 'by_week': by_week,
        'by_teacher': by_teacher, 'by_teacher_month': by_teacher_month,
        'by_category': by_category, 'top_students': top_students,
        'history_months': history_months, 'history_categories': history_categories,
        'history_by_cat_month': history_by_cat_month,
        'history_totals': {'revenue': int(h[0] or 0), 'salary': int(h[1] or 0),
                           'profit': int(h[2] or 0), 'marketing': int(h[3] or 0)},
        'teachers': teachers,
        'summary': {
            'month_revenue': month_revenue, 'month_revenue_owner': month_revenue_owner,
            'month_revenue_hired': month_revenue_hired, 'month_lessons': month_lessons,
            'prev_revenue': prev_revenue, 'prev_revenue_owner': prev_revenue_owner,
            'prev_revenue_hired': prev_revenue_hired, 'prev_lessons': prev_lessons,
            'planned': planned, 'planned_owner': planned_owner, 'planned_hired': planned_hired,
            'month_label': ru_month_full(month_start),
        },
        'meta': {'date': today.strftime('%d.%m.%Y'), 'time': now_msk().strftime('%H:%M')},
    }


@router.get("/subscriptions")
def get_subscriptions(request: Request, month: Optional[str] = Query(None)):
    require_role(request, "admin", "teacher")
    today = today_msk()
    if month:
        y, m = map(int, month.split("-"))
    else:
        y, m = today.year, today.month
    ms = date(y, m, 1)
    me = date(y, m, calendar.monthrange(y, m)[1])

    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT sub.id, sub.student_id, s.name AS student,
                       sub.month_start, sub.lessons_plan, sub.lessons_done,
                       sub.amount_plan, sub.amount_paid, sub.paid_at,
                       sub.status, sub.note
                FROM school_subscriptions sub
                JOIN school_students s ON sub.student_id = s.id
                WHERE sub.month_start = %s
                ORDER BY s.name
            """, (ms,))
            subs = cur.fetchall()

    return {
        'month': f"{y:04d}-{m:02d}",
        'subscriptions': [dict(r) for r in subs],
    }


@router.get("/payments")
def get_payments(request: Request, student_id: Optional[int] = Query(None), limit: int = 50):
    require_role(request, "admin", "teacher")
    filters = ["1=1"]
    params: list = []
    if student_id:
        filters.append("p.student_id=%s")
        params.append(student_id)
    params.append(limit)

    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT p.id, p.student_id, s.name AS student,
                       p.amount, p.payment_date, p.note, p.created_at
                FROM school_payments p
                JOIN school_students s ON p.student_id = s.id
                WHERE {' AND '.join(filters)}
                ORDER BY p.created_at DESC LIMIT %s
            """, params)
            rows = cur.fetchall()

    return {
        'payments': [
            {**dict(r),
             'amount': float(r['amount']),
             'payment_date': r['payment_date'].strftime('%d.%m.%Y') if r['payment_date'] else '',
             'created_at': r['created_at'].strftime('%d.%m %H:%M')}
            for r in rows
        ]
    }


@router.post("/payments/action")
def payments_action(request: Request, data: dict):
    require_role(request, "admin", "teacher")
    action = data.get("action")

    with db() as conn:
        with conn.cursor() as cur:
            if action == "mark_paid":
                cur.execute(
                    "INSERT INTO school_payments (student_id, amount, method, confirmed, confirmed_at, created_at) "
                    "VALUES (%s,%s,%s,TRUE,NOW(),NOW()) RETURNING id",
                    (data["student_id"], data.get("amount", 0), data.get("method", ""))
                )
                return {"ok": True, "id": cur.fetchone()[0]}

            if action == "cancel_payment":
                sid = data.get("student_id") or data.get("id")
                cur.execute(
                    "UPDATE school_payments SET confirmed=FALSE "
                    "WHERE id=(SELECT id FROM school_payments WHERE student_id=%s AND confirmed=TRUE ORDER BY created_at DESC LIMIT 1) "
                    "RETURNING id",
                    (sid,)
                )
                return {"ok": True}

            if action == "edit_payment":
                cur.execute(
                    "UPDATE school_payments SET amount=%s, method=%s "
                    "WHERE id=(SELECT id FROM school_payments WHERE student_id=%s AND confirmed=TRUE ORDER BY created_at DESC LIMIT 1) "
                    "RETURNING id",
                    (data.get("amount", 0), data.get("method", ""), data["student_id"])
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO school_payments (student_id, amount, method, confirmed, confirmed_at, created_at) "
                        "VALUES (%s,%s,%s,TRUE,NOW(),NOW())",
                        (data["student_id"], data.get("amount", 0), data.get("method", ""))
                    )
                return {"ok": True}

    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail=f"Неизвестное действие: {action}")


@router.get("/payments/history")
def payments_history(request: Request, student_id: Optional[int] = Query(None)):
    require_auth(request)
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if student_id:
                cur.execute(
                    "SELECT id, amount, method, confirmed, confirmed_at, created_at "
                    "FROM school_payments WHERE student_id=%s ORDER BY created_at DESC LIMIT 24",
                    (student_id,)
                )
            else:
                cur.execute(
                    "SELECT p.id, p.student_id, s.name AS student, p.amount, p.method, p.confirmed, p.created_at "
                    "FROM school_payments p JOIN school_students s ON p.student_id=s.id "
                    "ORDER BY p.created_at DESC LIMIT 50"
                )
            rows = cur.fetchall()
    return {"payments": [dict(r) for r in rows]}
