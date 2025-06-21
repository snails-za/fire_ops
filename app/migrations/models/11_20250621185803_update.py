from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "contact" ADD "is_accept" BOOL NOT NULL  DEFAULT False;
        ALTER TABLE "contact" ADD "bak" TEXT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ;"""
