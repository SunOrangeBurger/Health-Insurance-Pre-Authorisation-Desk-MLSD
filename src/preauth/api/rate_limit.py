from dataclasses import dataclass
import time


TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local values = redis.call('HMGET', key, 'tokens', 'updated')
local tokens = tonumber(values[1]) or capacity
local updated = tonumber(values[2]) or now
tokens = math.min(capacity, tokens + math.max(0, now - updated) * refill)
local allowed = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
end
redis.call('HMSET', key, 'tokens', tokens, 'updated', now)
redis.call('EXPIRE', key, math.ceil(capacity / refill) + 1)
return {allowed, tostring(tokens)}
"""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: float
    retry_after: int


async def consume_token(redis, client_id: str, capacity: int, refill_per_second: float) -> RateLimitDecision:
    now = time.time()
    allowed, remaining = await redis.eval(
        TOKEN_BUCKET_LUA, 1, f"rate-limit:{client_id}", capacity, refill_per_second, now, 1
    )
    remaining_value = float(remaining)
    retry_after = max(1, int((1 - remaining_value) / refill_per_second + 0.999))
    return RateLimitDecision(bool(int(allowed)), remaining_value, retry_after)
