from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "event" ALTER COLUMN "status" SET DEFAULT 'wait';
        ALTER TABLE "event" ALTER COLUMN "status" TYPE VARCHAR(20) USING "status"::VARCHAR(20);
        ALTER TABLE "event" ALTER COLUMN "level" SET DEFAULT 'medium';
        ALTER TABLE "event" ALTER COLUMN "level" TYPE VARCHAR(20) USING "level"::VARCHAR(20);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "event" ALTER COLUMN "status" SET DEFAULT 'alarm';
        ALTER TABLE "event" ALTER COLUMN "status" TYPE VARCHAR(20) USING "status"::VARCHAR(20);
        ALTER TABLE "event" ALTER COLUMN "level" SET DEFAULT 'normal';
        ALTER TABLE "event" ALTER COLUMN "level" TYPE VARCHAR(20) USING "level"::VARCHAR(20);"""
