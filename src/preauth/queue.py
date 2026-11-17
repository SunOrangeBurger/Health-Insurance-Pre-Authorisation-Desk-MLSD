"""Serialize admission across API replicas before adding bounded ARQ jobs."""
from preauth.config import get_settings


class QueueCapacityExceeded(RuntimeError):
    pass


async def enqueue_bounded(redis, run_id, correlation_id, limit=None):
    capacity = limit if limit is not None else get_settings().queue_capacity
    # ARQ retains running jobs in this sorted set until they finish, so the
    # budget covers queued and currently running work across worker replicas.
    async with redis.lock('desk:queue:admission', timeout=30, blocking_timeout=5):
        if await redis.zcard('arq:queue') >= capacity:
            raise QueueCapacityExceeded('Processing capacity reached; human review is required')
        return await redis.enqueue_job('process_preauth', run_id, correlation_id, _job_id=run_id)
