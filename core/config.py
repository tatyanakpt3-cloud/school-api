try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")

DB_NL = dict(host="127.0.0.1", port=5432, user="tatyana",
             password="empire2026", dbname="tatyana_empire")

DB_RU = dict(host="62.84.114.156", port=5432, user="tatyana",
             password="empire2026", dbname="school_pd", connect_timeout=8)
