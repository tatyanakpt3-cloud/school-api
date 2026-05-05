"""
Мониторинг запросов: время ответа, 5xx ошибки.
Хранитель читает метрики и алертит в Telegram.
"""
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("school-api.monitor")

SLOW_MS = 500   # алерт если > 500мс
ERROR_5XX = []  # последние 5xx — Хранитель читает


class MonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        ms = int((time.monotonic() - start) * 1000)

        path = request.url.path
        status = response.status_code

        if status >= 500:
            msg = f"{request.method} {path} → {status} ({ms}ms)"
            logger.error(f"5xx: {msg}")
            ERROR_5XX.append({"path": path, "status": status, "ms": ms,
                              "ts": time.strftime("%H:%M:%S")})
            if len(ERROR_5XX) > 50:
                ERROR_5XX.pop(0)

        elif ms > SLOW_MS:
            logger.warning(f"SLOW {ms}ms: {request.method} {path}")

        else:
            logger.info(f"{request.method} {path} → {status} {ms}ms")

        response.headers["X-Response-Time"] = f"{ms}ms"
        return response
