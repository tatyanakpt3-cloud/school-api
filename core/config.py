import os
from pathlib import Path

# Загружаем .env если он есть рядом с проектом
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")

# Конфиг БД из переменных окружения — разный на каждом сервере
DB_NL = dict(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "5432")),
    user=os.getenv("DB_USER", "tatyana"),
    password=os.getenv("DB_PASSWORD", "empire2026"),
    dbname=os.getenv("DB_NAME", "tatyana_empire"),
)

DB_RU = dict(
    host=os.getenv("DB_RU_HOST", "62.84.114.156"),
    port=int(os.getenv("DB_RU_PORT", "5432")),
    user=os.getenv("DB_RU_USER", "tatyana"),
    password=os.getenv("DB_RU_PASSWORD", "empire2026"),
    dbname=os.getenv("DB_RU_NAME", "school_pd"),
    connect_timeout=8,
)
