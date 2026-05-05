from contextlib import contextmanager
from datetime import datetime
import psycopg2
import psycopg2.extras
from .config import DB_NL, DB_RU, MSK

# Отдельные credentials для API-роли (попадает под RLS)
DB_API = {**DB_NL, "user": "school_api", "password": "api2026school"}


def get_conn(ru: bool = False, tenant_id: int = 1):
    cfg = DB_RU if ru else DB_API
    conn = psycopg2.connect(**cfg)
    if not ru:
        with conn.cursor() as cur:
            cur.execute(f"SET app.tenant_id = '{tenant_id}'")
        conn.commit()
    return conn


@contextmanager
def db(ru: bool = False, tenant_id: int = 1):
    conn = get_conn(ru, tenant_id)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_msk() -> datetime:
    return datetime.now(MSK)


def today_msk():
    return now_msk().date()
