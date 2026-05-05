from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")

DB_NL = dict(host="127.0.0.1", port=5432, user="tatyana",
             password="empire2026", dbname="saas_platform")

DB_RU = DB_NL  # на Mira — одна БД, ПД хранятся локально
