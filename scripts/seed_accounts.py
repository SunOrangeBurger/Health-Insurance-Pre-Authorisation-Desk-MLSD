"""Create demo accounts without resetting existing passwords.

Set DESK_HOSPITAL_PASSWORD and DESK_REVIEWER_PASSWORD before running.
"""
import asyncio
import os
from uuid import uuid4

from sqlalchemy import select

from preauth.security import hash_password
from preauth.store.database import init_database, session_factory, close_database
from preauth.store.models import User


async def main():
    hospital_password = os.environ["DESK_HOSPITAL_PASSWORD"]
    reviewer_password = os.environ["DESK_REVIEWER_PASSWORD"]
    if min(len(hospital_password), len(reviewer_password)) < 12:
        raise ValueError("Demo passwords must contain at least 12 characters")
    await init_database()
    async with session_factory() as session:
        for email, role, hospital, password in [
            ("hospital@desk.local", "hospital", "SYN-HOSP-001", hospital_password),
            ("hospital2@desk.local", "hospital", "SYN-HOSP-002", hospital_password),
            ("reviewer@desk.local", "reviewer", None, reviewer_password),
        ]:
            if await session.scalar(select(User).where(User.email == email)) is None:
                session.add(User(id=str(uuid4()), email=email, role=role, hospital_id=hospital,
                                 password_hash=hash_password(password), active=True))
        await session.commit()
    await close_database()


if __name__ == "__main__":
    asyncio.run(main())
