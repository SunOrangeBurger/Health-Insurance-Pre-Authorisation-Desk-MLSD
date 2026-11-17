import asyncio
import pytest
from preauth.queue import QueueCapacityExceeded, enqueue_bounded
from tests.test_auth import client


@pytest.mark.asyncio
async def test_concurrent_admission_does_not_overfill_queue():
    class Redis:
        def __init__(self):
            self.mutex = asyncio.Lock()
            self.jobs = []

        def lock(self, *args, **kwargs):
            return self.mutex

        async def zcard(self, key):
            await asyncio.sleep(0)
            return len(self.jobs)

        async def enqueue_job(self, *args, **kwargs):
            await asyncio.sleep(0)
            self.jobs.append(args)

    redis = Redis()
    results = await asyncio.gather(enqueue_bounded(redis, 'a', 'c', limit=1),
                                   enqueue_bounded(redis, 'b', 'c', limit=1), return_exceptions=True)
    assert len(redis.jobs) == 1
    assert sum(isinstance(r, QueueCapacityExceeded) for r in results) == 1


@pytest.mark.asyncio
async def test_capacity_failure_stays_visible_for_human_review(client, monkeypatch):
    from tests.test_auth import FakeRedis, login
    from tests.test_validation import valid_payload

    async def full(*args):
        return 64
    monkeypatch.setattr(FakeRedis, 'zcard', full)
    csrf = await login(client)
    payload = valid_payload()
    payload = {k: v.isoformat() if hasattr(v, 'isoformat') else v for k, v in payload.items()}
    response = await client.http.post('/v1/cases', json={'request': payload}, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 202
    case = response.json()
    assert case['status'] == 'awaiting_review' and case['processing_status'] == 'failed'
    assert not case['reusable_eligible']
    assert 'capacity reached' in case['recommendation']['route_reason']
