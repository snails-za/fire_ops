import redis.asyncio as redis
from config import REDIS_HOST, REDIS_DB, REDIS_PORT, REDIS_PASSWORD

class RedisManager:
    _client = None

    @classmethod
    async def init(cls):
        cls._client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
        )
        print("Redis init done")

    @classmethod
    async def close(cls):
        if cls._client:
            await cls._client.close()
            print("Redis closed")

    @classmethod
    def get_client(cls):
        if cls._client is None:
            raise RuntimeError("Redis client is not initialized")
        return cls._client


async def get_redis_client():
    client = RedisManager.get_client()
    return client