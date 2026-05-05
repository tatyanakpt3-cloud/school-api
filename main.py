"""
School API — модульное ядро платформы.
Порт 3515 (параллельно старому 3512 — Strangler Fig).
Подключение в nginx постепенно, модуль за модулем.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.monitoring import MonitoringMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)

from modules.schedule.router import router as schedule_router
from modules.homework.router import router as homework_router
from modules.chat.router     import router as chat_router
from modules.finance.router  import router as finance_router
from modules.reports.router  import router as reports_router
from modules.auth.router     import router as auth_router
from modules.students.router import router as students_router
from modules.lessons.router  import router as lessons_router
from modules.salary.router   import router as salary_router
from modules.notes.router       import router as notes_router
from modules.staff.router       import router as staff_router
from modules.vpr.router         import router as vpr_router
from modules.onboarding.router  import router as onboarding_router

app = FastAPI(
    title="School API",
    description="Модульное ядро Маминой Школы и Mira",
    version="2.0.0",
)

app.add_middleware(MonitoringMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aha-moment.online", "https://mira.school",
                   "https://schetova.mira.school"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schedule_router, prefix="/api/v2")
app.include_router(homework_router, prefix="/api/v2")
app.include_router(chat_router,     prefix="/api/v2")
app.include_router(finance_router,  prefix="/api/v2")
app.include_router(reports_router,  prefix="/api/v2")
app.include_router(auth_router,     prefix="/api/v2")
app.include_router(students_router, prefix="/api/v2")
app.include_router(lessons_router,  prefix="/api/v2")
app.include_router(salary_router,   prefix="/api/v2")
app.include_router(notes_router,      prefix="/api/v2")
app.include_router(staff_router,      prefix="/api/v2")
app.include_router(vpr_router,        prefix="/api/v2")
app.include_router(onboarding_router, prefix="/api/v2")


@app.get("/api/v2/health")
def health():
    import time
    from core.db import get_conn
    try:
        t = time.monotonic()
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        db_ms = int((time.monotonic() - t) * 1000)
        db_ok = True
    except Exception as e:
        db_ms = -1
        db_ok = False
    return {"status": "ok", "version": "2.0.0", "db_ok": db_ok, "db_ms": db_ms}


@app.get("/api/v2/metrics")
def metrics():
    from core.monitoring import ERROR_5XX
    return {
        "recent_errors": ERROR_5XX[-10:],
        "error_count": len(ERROR_5XX),
    }
