from fastapi import APIRouter, Request
import psycopg2.extras
from core.db import db, today_msk, now_msk
from core.auth import require_role

router = APIRouter(prefix="/staff", tags=["staff"])

RU_MONTHS_FULL = {1:'Январь',2:'Февраль',3:'Март',4:'Апрель',5:'Май',6:'Июнь',
                  7:'Июль',8:'Август',9:'Сентябрь',10:'Октябрь',11:'Ноябрь',12:'Декабрь'}


@router.get("")
def get_staff(request: Request):
    require_role(request, "admin")
    today = today_msk()

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, role, phone, rate_type, rate_amount,
                       active, started_at, sheet_url, balance_cutoff
                FROM school_staff WHERE active=TRUE ORDER BY id
            """)
            rows = cur.fetchall()

    staff = []
    for r in rows:
        item = {
            'id': r[0], 'name': r[1], 'role': r[2], 'phone': r[3] or '',
            'rate_type': r[4] or 'monthly', 'rate': r[5] or 0,
            'active': r[6],
            'started': r[7].strftime('%d.%m.%Y') if r[7] else '',
            'sheet_url': r[8] or '',
            'balance_cutoff': r[9].isoformat() if r[9] else None,
        }
        staff.append(item)

    total_monthly = sum(s['rate'] for s in staff if s['rate_type'] == 'monthly')

    return {
        'staff': staff,
        'total_monthly': total_monthly,
        'hourly_month': 0,
        'hourly_paid': 0,
        'hourly_due': 0,
        'payroll_month': total_monthly,
        'meta': {
            'date': today.strftime('%d.%m.%Y'),
            'time': now_msk().strftime('%H:%M'),
            'month_label': RU_MONTHS_FULL[today.month],
        },
    }


@router.post("/action")
def staff_action(request: Request, data: dict):
    require_role(request, "admin")
    action = data.get("action")

    with db() as conn:
        with conn.cursor() as cur:
            if action == "update":
                fields, values = [], []
                for k in ("name", "role", "phone", "sheet_url", "rate_type", "rate_amount", "active"):
                    if k in data:
                        fields.append(f"{k}=%s")
                        values.append(data[k])
                if fields:
                    values.append(data["id"])
                    cur.execute(f"UPDATE school_staff SET {', '.join(fields)} WHERE id=%s RETURNING id", values)
                return {"ok": bool(cur.fetchone())}

            if action == "add":
                cur.execute(
                    "INSERT INTO school_staff (name, role, phone, rate_type, rate_amount, active) "
                    "VALUES (%s,%s,%s,%s,%s,TRUE) RETURNING id",
                    (data.get("name"), data.get("role"), data.get("phone"),
                     data.get("rate_type", "monthly"), data.get("rate", 0))
                )
                return {"ok": True, "id": cur.fetchone()[0]}

            if action == "remove":
                cur.execute("UPDATE school_staff SET active=FALSE WHERE id=%s RETURNING id", (data["id"],))
                return {"ok": bool(cur.fetchone())}

    from fastapi import HTTPException
    raise HTTPException(status_code=400, detail=f"Неизвестное действие: {action}")
