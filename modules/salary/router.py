from datetime import timedelta
from fastapi import APIRouter, Request
from core.db import db, today_msk, now_msk
from core.auth import require_role

router = APIRouter(prefix="/salary", tags=["salary"])

RU_MONTHS_FULL = {1:'Январь',2:'Февраль',3:'Март',4:'Апрель',5:'Май',6:'Июнь',
                  7:'Июль',8:'Август',9:'Сентябрь',10:'Октябрь',11:'Ноябрь',12:'Декабрь'}


def ru_month_full(d):
    return RU_MONTHS_FULL[d.month]


def _breakdown(cur, teacher_id, date_from, date_to, status='completed'):
    cur.execute("""
        SELECT s.lesson_format, sc.duration_min, COUNT(*)
        FROM school_schedule sc
        JOIN school_students s ON sc.student_id = s.id
        WHERE sc.teacher_id=%s AND sc.status=%s
          AND sc.lesson_date>=%s AND sc.lesson_date<=%s
        GROUP BY s.lesson_format, sc.duration_min
    """, (teacher_id, status, date_from, date_to))
    bd = {'ind_60': 0, 'ind_45': 0, 'group_60': 0, 'group_45': 0, 'total': 0}
    for fmt, dur, cnt in cur.fetchall():
        is_group = fmt and fmt != 'individual'
        is_45 = dur and dur <= 45
        key = f"{'group' if is_group else 'ind'}_{'45' if is_45 else '60'}"
        bd[key] += cnt
        bd['total'] += cnt
    return bd


def _calc(rates, bd):
    if not rates:
        rates = {}
    return (
        (rates.get('ind_60', 0) or 0) * bd.get('ind_60', 0) +
        (rates.get('ind_45', 0) or 0) * bd.get('ind_45', 0) +
        (rates.get('group_60', 0) or 0) * bd.get('group_60', 0) +
        (rates.get('group_45', 0) or 0) * bd.get('group_45', 0)
    )


@router.get("")
def get_salary(request: Request):
    require_role(request, "admin")
    today = today_msk()
    month_start = today.replace(day=1)
    prev_end = month_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    month_end = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.name, t.rate_per_lesson, t.rate_type, t.rates,
                       COALESCE(t.is_owner, FALSE)
                FROM school_teachers t WHERE t.active=TRUE ORDER BY t.name
            """)
            teacher_rows = cur.fetchall()

            teachers = []
            for tid, tname, rate, rtype, rates, is_owner in teacher_rows:
                if not rates or not any(rates.values()):
                    rates = {'ind_60': rate or 0, 'ind_45': rate or 0,
                             'group_60': 0, 'group_45': 0}

                bd       = _breakdown(cur, tid, month_start, today)
                prev_bd  = _breakdown(cur, tid, prev_start, prev_end)
                plan_bd  = _breakdown(cur, tid, today + timedelta(days=1), month_end, 'scheduled')

                cur.execute("""
                    SELECT COALESCE(SUM(s.price_per_lesson), 0)
                    FROM school_schedule sc
                    JOIN school_students s ON sc.student_id=s.id
                    WHERE sc.teacher_id=%s AND sc.status='completed'
                      AND sc.lesson_date>=%s AND sc.lesson_date<=%s
                """, (tid, month_start, today))
                revenue = int(cur.fetchone()[0])

                salary           = _calc(rates, bd)
                prev_salary      = _calc(rates, prev_bd)
                projected_salary = salary + _calc(rates, plan_bd)

                teachers.append({
                    'id': tid, 'name': tname, 'is_owner': is_owner,
                    'rates': rates,
                    'lessons': bd['total'], 'breakdown': bd, 'revenue': revenue,
                    'salary': salary,
                    'prev_lessons': prev_bd['total'], 'prev_salary': prev_salary,
                    'planned_lessons': plan_bd['total'], 'projected_salary': projected_salary,
                })

    hired = [t for t in teachers if not t['is_owner']]
    return {
        'teachers': teachers,
        'summary': {
            'total_salary':      sum(t['salary'] for t in hired),
            'total_projected':   sum(t['projected_salary'] for t in hired),
            'total_salary_all':  sum(t['salary'] for t in teachers),
            'total_projected_all': sum(t['projected_salary'] for t in teachers),
            'month_label': ru_month_full(month_start),
        },
        'meta': {
            'date': today.strftime('%d.%m.%Y'),
            'time': now_msk().strftime('%H:%M'),
        },
    }
