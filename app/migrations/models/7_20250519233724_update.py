from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "device" ADD "contact" VARCHAR(11);
        ALTER TABLE "device" ADD "installer" VARCHAR(50);
        ALTER TABLE "device" RENAME COLUMN "bak" TO "remark";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "device" RENAME COLUMN "remark" TO "bak";"""
