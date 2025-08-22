from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "friendrequest" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "is_star" BOOL NOT NULL  DEFAULT False,
    "is_accept" BOOL,
    "bak" TEXT,
    "receiver_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    "requester_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "friendrequest"."id" IS '联系人ID';
COMMENT ON COLUMN "friendrequest"."created_at" IS '创建时间';
COMMENT ON COLUMN "friendrequest"."updated_at" IS '更新时间';
COMMENT ON COLUMN "friendrequest"."is_star" IS '是否星标';
COMMENT ON COLUMN "friendrequest"."is_accept" IS '是否接受';
COMMENT ON COLUMN "friendrequest"."bak" IS '备注';
COMMENT ON COLUMN "friendrequest"."receiver_id" IS '接收人';
COMMENT ON COLUMN "friendrequest"."requester_id" IS '申请人';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ;"""
