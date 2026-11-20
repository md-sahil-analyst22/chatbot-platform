# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Short-term chat memory: the last few messages of each conversation, kept in Redis for 24
#       hours.
# Security: 🔒 Every key starts with the tenant (t:<tenant>:...), so tenants can't read each
#           other's memory.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Session memory (P3.4): last N turns per conversation in Redis. Keys are tenant scoped."""

import json
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis

from saathi.modules.conversation.ports.llm import ChatMessage

MAX_TURNS = 6  # user+assistant pairs kept verbatim
TTL_SECONDS = 24 * 3600  # matches the WhatsApp 24h service window


# Stores and reads recent messages.
class RedisConversationMemory:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    # The Redis key for one conversation.
    def _key(tenant_id: str, conversation_id: str) -> str:
        return f"t:{tenant_id}:conv:{conversation_id}:turns"

    # Add a message, keep only the newest turns, renew the 24-hour expiry - all in one step.
    async def append(self, tenant_id: str, conversation_id: str, message: ChatMessage) -> None:
        key = self._key(tenant_id, conversation_id)
        payload = json.dumps({"role": message.role, "content": message.content})
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.rpush(key, payload)
            pipe.ltrim(key, -MAX_TURNS * 2, -1)
            pipe.expire(key, TTL_SECONDS)
            await pipe.execute()

    # Read the remembered messages, oldest first.
    async def history(self, tenant_id: str, conversation_id: str) -> list[ChatMessage]:
        # redis-py types sync/async clients together; narrow to the async form.
        pending = cast(
            "Awaitable[list[str]]", self._redis.lrange(self._key(tenant_id, conversation_id), 0, -1)
        )
        raw = await pending
        return [ChatMessage(**json.loads(item)) for item in raw]
