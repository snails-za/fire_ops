from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "device" ALTER COLUMN "image" TYPE JSONB USING "image"::JSONB;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "device" ALTER COLUMN "image" TYPE VARCHAR(255) USING "image"::VARCHAR(255);"""
