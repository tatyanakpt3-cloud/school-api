"""
Smoke tests — запускаются после каждого деплоя.
Зелёный = можно деплоить. Красный = стоп.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

BASE = "http://test"
VALID_TOKEN = "66dCDaYockw1ecnV79r6_A"  # тестовый токен Ангелины


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        yield c


@pytest.fixture
async def auth_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE,
                           cookies={"school_token": VALID_TOKEN}) as c:
        yield c


# === HEALTH ===

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/v2/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# === AUTH — закрытость ===

@pytest.mark.asyncio
async def test_schedule_requires_auth(client):
    assert (await client.get("/api/v2/schedule")).status_code == 401

@pytest.mark.asyncio
async def test_homework_requires_auth(client):
    assert (await client.get("/api/v2/homework")).status_code == 401

@pytest.mark.asyncio
async def test_chat_requires_auth(client):
    assert (await client.get("/api/v2/chat?student_id=1")).status_code == 401

@pytest.mark.asyncio
async def test_reports_requires_auth(client):
    assert (await client.get("/api/v2/reports")).status_code == 401

@pytest.mark.asyncio
async def test_finance_requires_auth(client):
    assert (await client.get("/api/v2/finance")).status_code == 401


# === SCHEDULE ===

@pytest.mark.asyncio
async def test_schedule_returns_data(auth_client):
    r = await auth_client.get("/api/v2/schedule")
    assert r.status_code == 200
    data = r.json()
    assert "lessons" in data
    assert "meta" in data

@pytest.mark.asyncio
async def test_schedule_lesson_shape(auth_client):
    r = await auth_client.get("/api/v2/schedule")
    for lesson in r.json()["lessons"]:
        assert "id" in lesson
        assert "date" in lesson
        assert "time" in lesson
        assert "student" in lesson
        assert ":" in lesson["time"]

@pytest.mark.asyncio
async def test_schedule_date_filter(auth_client):
    r = await auth_client.get("/api/v2/schedule?date_from=2026-05-01&date_to=2026-05-31")
    assert r.status_code == 200


# === HOMEWORK ===

@pytest.mark.asyncio
async def test_homework_returns_data(auth_client):
    r = await auth_client.get("/api/v2/homework")
    assert r.status_code == 200
    assert "homework" in r.json()


# === REPORTS ===

@pytest.mark.asyncio
async def test_reports_returns_data(auth_client):
    r = await auth_client.get("/api/v2/reports")
    assert r.status_code == 200
    data = r.json()
    assert "reports" in data
    assert "students" in data
    assert "teachers" in data

@pytest.mark.asyncio
async def test_reports_hw_status_valid(auth_client):
    r = await auth_client.get("/api/v2/reports")
    valid = {None, "sent", "submitted", "checked"}
    for rep in r.json()["reports"]:
        assert rep["hw_status"] in valid


# === ИЗОЛЯЦИЯ — чат не знает про финансы ===

@pytest.mark.asyncio
async def test_students_requires_auth(client):
    assert (await client.get("/api/v2/students")).status_code == 401

@pytest.mark.asyncio
async def test_lesson_comments_requires_auth(client):
    assert (await client.get("/api/v2/lesson/comments")).status_code == 401

@pytest.mark.asyncio
async def test_lesson_report_requires_auth(client):
    assert (await client.post("/api/v2/lesson/report", json={})).status_code == 401

@pytest.mark.asyncio
async def test_salary_requires_auth(client):
    assert (await client.get("/api/v2/salary")).status_code == 401


@pytest.mark.asyncio
async def test_modules_are_independent(auth_client):
    # Финансы не ломаются если чат недоступен
    r_finance = await auth_client.get("/api/v2/finance")
    # finance требует admin/teacher — 403 для student, не 500
    assert r_finance.status_code in (200, 403)

    # Auth check работает независимо
    r_auth = await auth_client.get("/api/v2/auth/check")
    assert r_auth.status_code == 200
    assert "role" in r_auth.json()
