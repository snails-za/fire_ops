from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "direct_conversation" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_message" VARCHAR(500),
    "last_message_at" TIMESTAMPTZ,
    "user_a_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    "user_b_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_direct_conv_user_a__79f683" UNIQUE ("user_a_id", "user_b_id")
);
CREATE INDEX IF NOT EXISTS "idx_direct_conv_user_a__79f683" ON "direct_conversation" ("user_a_id", "user_b_id");
CREATE INDEX IF NOT EXISTS "idx_direct_conv_last_me_b2ecc5" ON "direct_conversation" ("last_message_at");
COMMENT ON COLUMN "direct_conversation"."created_at" IS '创建时间';
COMMENT ON COLUMN "direct_conversation"."updated_at" IS '更新时间';
COMMENT ON COLUMN "direct_conversation"."last_message" IS '最后一条消息';
COMMENT ON COLUMN "direct_conversation"."last_message_at" IS '最后消息时间';
COMMENT ON COLUMN "direct_conversation"."user_a_id" IS '会话用户A';
COMMENT ON COLUMN "direct_conversation"."user_b_id" IS '会话用户B';
COMMENT ON TABLE "direct_conversation" IS '好友一对一会话。';
        CREATE TABLE IF NOT EXISTS "direct_message" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "content" TEXT NOT NULL,
    "is_read" BOOL NOT NULL DEFAULT False,
    "conversation_id" INT NOT NULL REFERENCES "direct_conversation" ("id") ON DELETE CASCADE,
    "receiver_id" INT REFERENCES "user" ("id") ON DELETE SET NULL,
    "sender_id" INT REFERENCES "user" ("id") ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS "idx_direct_mess_convers_eafcec" ON "direct_message" ("conversation_id", "created_at");
CREATE INDEX IF NOT EXISTS "idx_direct_mess_receive_617584" ON "direct_message" ("receiver_id", "is_read");
COMMENT ON COLUMN "direct_message"."created_at" IS '创建时间';
COMMENT ON COLUMN "direct_message"."updated_at" IS '更新时间';
COMMENT ON COLUMN "direct_message"."content" IS '消息内容';
COMMENT ON COLUMN "direct_message"."is_read" IS '是否已读';
COMMENT ON COLUMN "direct_message"."conversation_id" IS '所属会话';
COMMENT ON COLUMN "direct_message"."receiver_id" IS '接收人';
COMMENT ON COLUMN "direct_message"."sender_id" IS '发送人';
COMMENT ON TABLE "direct_message" IS '好友一对一消息。';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ;"""
