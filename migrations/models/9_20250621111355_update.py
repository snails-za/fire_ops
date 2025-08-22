from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "contact" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "contact_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "contact"."id" IS '联系人ID';
COMMENT ON COLUMN "contact"."created_at" IS '创建时间';
COMMENT ON COLUMN "contact"."updated_at" IS '更新时间';
COMMENT ON COLUMN "contact"."contact_id" IS '联系人';
COMMENT ON COLUMN "contact"."user_id" IS '用户';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ;"""
