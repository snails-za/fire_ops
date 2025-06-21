from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "contact" ADD "is_star" BOOL NOT NULL  DEFAULT False;
        ALTER TABLE "user" ADD "pinyin" VARCHAR(255);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ;"""
