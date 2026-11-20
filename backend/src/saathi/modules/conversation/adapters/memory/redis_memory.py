# ─────────────────────────────────────────────────────────────────────────────────────────────
# 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
# What: Short-term chat memory: the last few messages of each conversation, kept in Redis for 24
#       hours.
# Security: 🔒 Every key starts with the tenant (t:<tenant>:...), so tenants can't read each
#           other's memory.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""Session memory (P3.4): last N turns per conversation in Redis. Keys are tenant scoped."""

# json — reads and writes JSON text.
import json

# From collections.abc — standard type names for collections: Awaitable = type for something you
#   can `await`.
from collections.abc import Awaitable

# From typing — type-hint helpers: cast = tells the type checker the real type.
from typing import cast

# From redis.asyncio — async client for Redis, the fast in-memory store: Redis = the Redis
#   client.
from redis.asyncio import Redis

# From saathi.modules.conversation.ports.llm — AI language-model contracts: ChatMessage = one
#   chat message.
from saathi.modules.conversation.ports.llm import ChatMessage

MAX_TURNS = 6  # user+assistant pairs kept verbatim
TTL_SECONDS = 24 * 3600  # matches the WhatsApp 24h service window


# Stores and reads recent messages.
class RedisConversationMemory:
    # Built with the Redis client.
    def __init__(self, redis: Redis) -> None:
        # Remember it.
        self._redis = redis

    # A static method doesn't need `self`.
    @staticmethod
    # The Redis key for one conversation.
    def _key(tenant_id: str, conversation_id: str) -> str:
        # 🔒 e.g. t:<tenant>:conv:<conversation>:turns - always starts with the tenant.
        return f"t:{tenant_id}:conv:{conversation_id}:turns"

    # Add a message, keep only the newest turns, renew the 24-hour expiry - all in one step.
    async def append(self, tenant_id: str, conversation_id: str, message: ChatMessage) -> None:
        # The Redis key for this conversation.
        key = self._key(tenant_id, conversation_id)
        # The message as JSON text.
        payload = json.dumps({"role": message.role, "content": message.content})
        # Group the next three commands so they run together, all or nothing:
        async with self._redis.pipeline(transaction=True) as pipe:
            # add the message to the end of the list,
            pipe.rpush(key, payload)
            # keep only the newest MAX_TURNS x 2 messages,
            pipe.ltrim(key, -MAX_TURNS * 2, -1)
            # and (re)set the 24-hour expiry.
            pipe.expire(key, TTL_SECONDS)
            # Send them to Redis.
            await pipe.execute()

    # Read the remembered messages, oldest first.
    async def history(self, tenant_id: str, conversation_id: str) -> list[ChatMessage]:
        # redis-py types sync/async clients together; narrow to the async form.
        pending = cast(
            "Awaitable[list[str]]", self._redis.lrange(self._key(tenant_id, conversation_id), 0, -1)
        )
        # Read the stored messages.
        raw = await pending
        # Turn each JSON text back into a ChatMessage.
        return [ChatMessage(**json.loads(item)) for item in raw]
