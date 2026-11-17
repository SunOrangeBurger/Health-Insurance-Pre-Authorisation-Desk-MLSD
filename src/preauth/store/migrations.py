"""Additive, versioned migrations for legacy and fresh databases.

PostgreSQL advisory lock serializes API/worker startup migrations.
"""
from sqlalchemy import text
from preauth.store.models import Base


async def migrate(connection):
    if connection.dialect.name == "postgresql":
        await connection.execute(text("SELECT pg_advisory_xact_lock(73290142)"))
    await connection.execute(text("CREATE TABLE IF NOT EXISTS desk_schema_versions (version INTEGER PRIMARY KEY)"))
    versions = set((await connection.execute(text("SELECT version FROM desk_schema_versions"))).scalars())
    groups = {
        1: ["runs", "quarantine", "run_steps", "cost_ledger", "feedback"],
        2: ["desk_users", "desk_sessions", "desk_run_owners"],
        3: ["desk_cases", "desk_case_events"],
        4: ["desk_precedents"],
        5: ["desk_submission_keys"],
    }
    for version, names in groups.items():
        if version not in versions:
            for name in names:
                await connection.run_sync(lambda sync, name=name: Base.metadata.tables[name].create(sync, checkfirst=True))
            await connection.execute(text("INSERT INTO desk_schema_versions (version) VALUES (:version)"), {"version": version})
