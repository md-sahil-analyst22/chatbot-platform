"""Distributed token-bucket rate limiter (Redis + atomic Lua). Used from P6.6.

Key format: rl:{scope}:{tenant_id}:{subject}  - always tenant scoped.
Failure policy is explicit: security limits DENY when Redis is down; business quotas may ALLOW.
"""

from dataclasses import dataclass
from typing import Literal

from redis.asyncio import Redis
from redis.exceptions import RedisError

# Uses Redis server TIME so app-server clock skew cannot be abused.
_BUCKET_SCRIPT_LUA = """
local cap  = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local t    = redis.call('TIME')
local now  = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local b    = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(b[1]) or cap
local ts     = tonumber(b[2]) or now
tokens = math.min(cap, tokens + (math.max(0, now - ts) / 1000.0) * rate)
local allowed = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('PEXPIRE', KEYS[1], math.ceil((cap / rate) * 1000) + 1000)
return allowed
"""


@dataclass(frozen=True, slots=True)
class BucketPolicy:
    capacity: int
    refill_per_second: float
    on_backend_error: Literal["deny", "allow"] = "deny"


class RedisTokenBucket:
    def __init__(self, redis: Redis) -> None:
        self._script = redis.register_script(_BUCKET_SCRIPT_LUA)

    async def allow(
        self, *, scope: str, tenant_id: str, subject: str, policy: BucketPolicy, cost: int = 1
    ) -> bool:
        key = f"rl:{scope}:{tenant_id}:{subject}"
        try:
            result = await self._script(
                keys=[key], args=[policy.capacity, policy.refill_per_second, cost]
            )
        except RedisError:
            return policy.on_backend_error == "allow"
        return int(result) == 1
