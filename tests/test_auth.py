from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from preauth.api.auth import hospital_user, owned_run, router
from preauth.api.cases import router as cases_router
from preauth.api.precedents import router as precedents_router
from preauth.security import hash_password
from preauth.store.database import get_session
from preauth.store.migrations import migrate
from preauth.store.models import LoginSession, RunOwner, User


class FakeRedis:
    def lock(self, *args, **kwargs):
        from contextlib import nullcontext
        return nullcontext()

    async def zcard(self, *args):
        return 0

    async def eval(self, *args):
        return [1, "4"]

    async def enqueue_job(self, *args, **kwargs):
        return None


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await migrate(conn)
        await migrate(conn)
        assert (await conn.execute(text("SELECT count(*) FROM desk_schema_versions"))).scalar() == 5
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        for id, role, hospital in [("a", "hospital", "A"), ("b", "hospital", "B"), ("r", "reviewer", None)]:
            session.add(User(id=id, email=f"{id}@desk.local", role=role, hospital_id=hospital,
                             password_hash=hash_password("test-password"), active=True))
        session.add(RunOwner(run_id="owned", hospital_id="A", user_id="a"))
        await session.commit()
    async def db():
        async with sessions() as session:
            yield session
    app = FastAPI()
    app.include_router(router)
    app.include_router(cases_router)
    app.include_router(precedents_router)
    app.state.redis = FakeRedis()
    app.dependency_overrides[get_session] = db
    @app.get("/runs/{run_id}")
    async def run(run_id: str, user=Depends(owned_run)):
        return {"id": run_id}
    @app.post("/hospital")
    async def hospital(user=Depends(hospital_user)):
        return {"id": user.id}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        yield SimpleNamespace(http=http, sessions=sessions)
    await engine.dispose()


async def login(client, account="a"):
    response = await client.http.post("/v1/auth/login", json={"email": f"{account}@desk.local", "password": "test-password"}, headers={"X-Requested-With": "desk"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    return response.json()["csrf_token"]


@pytest.mark.asyncio
async def test_session_csrf_logout_and_role(client):
    assert (await client.http.get("/v1/auth/me")).status_code == 401
    csrf = await login(client)
    assert (await client.http.post("/hospital")).status_code == 403
    assert (await client.http.post("/hospital", headers={"X-CSRF-Token": csrf})).status_code == 200
    assert (await client.http.post("/v1/auth/logout", headers={"X-CSRF-Token": csrf})).status_code == 204
    assert (await client.http.get("/v1/auth/me")).status_code == 401
    csrf = await login(client, "r")
    assert (await client.http.post("/hospital", headers={"X-CSRF-Token": csrf})).status_code == 403


@pytest.mark.asyncio
async def test_hospital_isolation_and_legacy_records(client):
    await login(client)
    assert (await client.http.get("/runs/owned")).status_code == 200
    assert (await client.http.get("/runs/legacy")).status_code == 404
    await login(client, "b")
    assert (await client.http.get("/runs/owned")).status_code == 404
    await login(client, "r")
    assert (await client.http.get("/runs/owned")).status_code == 200


@pytest.mark.asyncio
async def test_expired_sessions_and_login_validation(client):
    response = await client.http.post("/v1/auth/login", json={"email": "a@desk.local", "password": "test-password"})
    assert response.status_code == 403
    await login(client)
    async with client.sessions() as session:
        record = await session.scalar(select(LoginSession))
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()
    assert (await client.http.get("/v1/auth/me")).status_code == 401
