from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "user" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "username" VARCHAR(20) NOT NULL UNIQUE,
    "email" VARCHAR(50)  UNIQUE,
    "password" VARCHAR(128),
    "head" VARCHAR(255),
    "pinyin" VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS "idx_user_usernam_9987ab" ON "user" ("username");
CREATE INDEX IF NOT EXISTS "idx_user_email_1b4f1c" ON "user" ("email");
COMMENT ON COLUMN "user"."id" IS '用户ID';
COMMENT ON COLUMN "user"."created_at" IS '创建时间';
COMMENT ON COLUMN "user"."updated_at" IS '更新时间';
COMMENT ON COLUMN "user"."username" IS '用户名';
COMMENT ON COLUMN "user"."email" IS '邮箱';
COMMENT ON COLUMN "user"."password" IS '密码';
COMMENT ON COLUMN "user"."head" IS '头像';
COMMENT ON COLUMN "user"."pinyin" IS '用户名首字母';
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
COMMENT ON COLUMN "friendrequest"."requester_id" IS '申请人';
CREATE TABLE IF NOT EXISTS "device" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(100),
    "address" VARCHAR(100),
    "location" JSONB,
    "images" JSONB,
    "status" VARCHAR(50),
    "install_date" DATE,
    "installer" VARCHAR(50),
    "contact" VARCHAR(11),
    "remark" TEXT,
    CONSTRAINT "uid_device_name_374f1e" UNIQUE ("name", "address")
);
CREATE INDEX IF NOT EXISTS "idx_device_name_d43932" ON "device" ("name");
CREATE INDEX IF NOT EXISTS "idx_device_name_0312e5" ON "device" ("name", "status", "install_date");
COMMENT ON COLUMN "device"."created_at" IS '创建时间';
COMMENT ON COLUMN "device"."updated_at" IS '更新时间';
COMMENT ON COLUMN "device"."name" IS '设备名称';
COMMENT ON COLUMN "device"."address" IS '地址';
COMMENT ON COLUMN "device"."location" IS '设备位置';
COMMENT ON COLUMN "device"."images" IS '设备图片';
COMMENT ON COLUMN "device"."status" IS '设备状态';
COMMENT ON COLUMN "device"."install_date" IS '安装日期';
COMMENT ON COLUMN "device"."installer" IS '安装人';
COMMENT ON COLUMN "device"."contact" IS '联系人';
COMMENT ON COLUMN "device"."remark" IS '备注';
CREATE TABLE IF NOT EXISTS "chat_session" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "session_name" VARCHAR(100) NOT NULL,
    "created_time" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "last_active" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "chat_session"."id" IS '会话ID';
COMMENT ON COLUMN "chat_session"."created_at" IS '创建时间';
COMMENT ON COLUMN "chat_session"."updated_at" IS '更新时间';
COMMENT ON COLUMN "chat_session"."session_name" IS '会话名称';
COMMENT ON COLUMN "chat_session"."created_time" IS '创建时间';
COMMENT ON COLUMN "chat_session"."last_active" IS '最后活跃时间';
COMMENT ON COLUMN "chat_session"."user_id" IS '用户';
COMMENT ON TABLE "chat_session" IS '聊天会话模型';
CREATE TABLE IF NOT EXISTS "chat_message" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "role" VARCHAR(20) NOT NULL,
    "content" TEXT NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "metadata" JSONB,
    "session_id" INT NOT NULL REFERENCES "chat_session" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "chat_message"."id" IS '消息ID';
COMMENT ON COLUMN "chat_message"."created_at" IS '创建时间';
COMMENT ON COLUMN "chat_message"."updated_at" IS '更新时间';
COMMENT ON COLUMN "chat_message"."role" IS '角色: user, assistant, system';
COMMENT ON COLUMN "chat_message"."content" IS '消息内容';
COMMENT ON COLUMN "chat_message"."timestamp" IS '时间戳';
COMMENT ON COLUMN "chat_message"."metadata" IS '元数据';
COMMENT ON COLUMN "chat_message"."session_id" IS '所属会话';
COMMENT ON TABLE "chat_message" IS '聊天消息模型';
CREATE TABLE IF NOT EXISTS "document" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "filename" VARCHAR(255) NOT NULL,
    "original_filename" VARCHAR(255) NOT NULL,
    "file_path" VARCHAR(500) NOT NULL,
    "file_size" INT NOT NULL,
    "file_type" VARCHAR(50) NOT NULL,
    "content" TEXT NOT NULL,
    "status" VARCHAR(20) NOT NULL  DEFAULT 'processing',
    "upload_time" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "process_time" TIMESTAMPTZ,
    "error_message" TEXT
);
COMMENT ON COLUMN "document"."id" IS '文档ID';
COMMENT ON COLUMN "document"."created_at" IS '创建时间';
COMMENT ON COLUMN "document"."updated_at" IS '更新时间';
COMMENT ON COLUMN "document"."filename" IS '文件名';
COMMENT ON COLUMN "document"."original_filename" IS '原始文件名';
COMMENT ON COLUMN "document"."file_path" IS '文件路径';
COMMENT ON COLUMN "document"."file_size" IS '文件大小(字节)';
COMMENT ON COLUMN "document"."file_type" IS '文件类型';
COMMENT ON COLUMN "document"."content" IS '文档内容';
COMMENT ON COLUMN "document"."status" IS '处理状态: processing, completed, failed';
COMMENT ON COLUMN "document"."upload_time" IS '上传时间';
COMMENT ON COLUMN "document"."process_time" IS '处理完成时间';
COMMENT ON COLUMN "document"."error_message" IS '错误信息';
COMMENT ON TABLE "document" IS '文档模型';
CREATE TABLE IF NOT EXISTS "document_chunk" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "chunk_index" INT NOT NULL,
    "content" TEXT NOT NULL,
    "content_length" INT NOT NULL,
    "metadata" JSONB,
    "document_id" INT NOT NULL REFERENCES "document" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "document_chunk"."id" IS '分块ID';
COMMENT ON COLUMN "document_chunk"."created_at" IS '创建时间';
COMMENT ON COLUMN "document_chunk"."updated_at" IS '更新时间';
COMMENT ON COLUMN "document_chunk"."chunk_index" IS '分块索引';
COMMENT ON COLUMN "document_chunk"."content" IS '分块内容';
COMMENT ON COLUMN "document_chunk"."content_length" IS '内容长度';
COMMENT ON COLUMN "document_chunk"."metadata" IS '元数据';
COMMENT ON COLUMN "document_chunk"."document_id" IS '所属文档';
COMMENT ON TABLE "document_chunk" IS '文档分块模型';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
