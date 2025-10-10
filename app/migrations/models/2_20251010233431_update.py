from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "friendrequest" ALTER COLUMN "requester_id" TYPE INT USING "requester_id"::INT;
        ALTER TABLE "friendrequest" ALTER COLUMN "receiver_id" TYPE INT USING "receiver_id"::INT;
        ALTER TABLE "user" ADD "role" VARCHAR(20)NOT NULL DEFAULT 'user';
        ALTER TABLE "user" ALTER COLUMN "username" TYPE VARCHAR(20) USING "username"::VARCHAR(20);
        ALTER TABLE "user" ALTER COLUMN "email" TYPE VARCHAR(50) USING "email"::VARCHAR(50);
        ALTER TABLE "user" ALTER COLUMN "password" TYPE VARCHAR(128) USING "password"::VARCHAR(128);
        ALTER TABLE "user" ALTER COLUMN "pinyin" TYPE VARCHAR(255) USING "pinyin"::VARCHAR(255);
        ALTER TABLE "user" ALTER COLUMN "head" TYPE VARCHAR(255) USING "head"::VARCHAR(255);
        ALTER TABLE "device" ALTER COLUMN "installer" TYPE VARCHAR(50) USING "installer"::VARCHAR(50);
        ALTER TABLE "device" ALTER COLUMN "contact" TYPE VARCHAR(11) USING "contact"::VARCHAR(11);
        ALTER TABLE "device" ALTER COLUMN "name" TYPE VARCHAR(100) USING "name"::VARCHAR(100);
        ALTER TABLE "device" ALTER COLUMN "address" TYPE VARCHAR(100) USING "address"::VARCHAR(100);
        ALTER TABLE "device" ALTER COLUMN "status" TYPE VARCHAR(50) USING "status"::VARCHAR(50);
        ALTER TABLE "chat_message" ALTER COLUMN "role" TYPE VARCHAR(20) USING "role"::VARCHAR(20);
        ALTER TABLE "chat_message" ALTER COLUMN "session_id" TYPE INT USING "session_id"::INT;
        ALTER TABLE "chat_session" ALTER COLUMN "user_id" TYPE INT USING "user_id"::INT;
        ALTER TABLE "chat_session" ALTER COLUMN "session_name" TYPE VARCHAR(100) USING "session_name"::VARCHAR(100);
        ALTER TABLE "document" ALTER COLUMN "original_filename" TYPE VARCHAR(255) USING "original_filename"::VARCHAR(255);
        ALTER TABLE "document" ALTER COLUMN "filename" TYPE VARCHAR(255) USING "filename"::VARCHAR(255);
        ALTER TABLE "document" ALTER COLUMN "file_path" TYPE VARCHAR(500) USING "file_path"::VARCHAR(500);
        ALTER TABLE "document" ALTER COLUMN "status" SET DEFAULT 'queued';
        ALTER TABLE "document" ALTER COLUMN "status" TYPE VARCHAR(20) USING "status"::VARCHAR(20);
        ALTER TABLE "document" ALTER COLUMN "task_id" TYPE VARCHAR(255) USING "task_id"::VARCHAR(255);
        ALTER TABLE "document" ALTER COLUMN "file_type" TYPE VARCHAR(50) USING "file_type"::VARCHAR(50);
        ALTER TABLE "document_chunk" ALTER COLUMN "document_id" TYPE INT USING "document_id"::INT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" ALTER COLUMN "username" TYPE VARCHAR(20) USING "username"::VARCHAR(20);
        ALTER TABLE "user" ALTER COLUMN "email" TYPE VARCHAR(50) USING "email"::VARCHAR(50);
        ALTER TABLE "user" ALTER COLUMN "password" TYPE VARCHAR(128) USING "password"::VARCHAR(128);
        ALTER TABLE "user" ALTER COLUMN "pinyin" TYPE VARCHAR(255) USING "pinyin"::VARCHAR(255);
        ALTER TABLE "user" ALTER COLUMN "head" TYPE VARCHAR(255) USING "head"::VARCHAR(255);
        ALTER TABLE "device" ALTER COLUMN "installer" TYPE VARCHAR(50) USING "installer"::VARCHAR(50);
        ALTER TABLE "device" ALTER COLUMN "contact" TYPE VARCHAR(11) USING "contact"::VARCHAR(11);
        ALTER TABLE "device" ALTER COLUMN "name" TYPE VARCHAR(100) USING "name"::VARCHAR(100);
        ALTER TABLE "device" ALTER COLUMN "address" TYPE VARCHAR(100) USING "address"::VARCHAR(100);
        ALTER TABLE "device" ALTER COLUMN "status" TYPE VARCHAR(50) USING "status"::VARCHAR(50);
        ALTER TABLE "document" ALTER COLUMN "original_filename" TYPE VARCHAR(255) USING "original_filename"::VARCHAR(255);
        ALTER TABLE "document" ALTER COLUMN "filename" TYPE VARCHAR(255) USING "filename"::VARCHAR(255);
        ALTER TABLE "document" ALTER COLUMN "file_path" TYPE VARCHAR(500) USING "file_path"::VARCHAR(500);
        ALTER TABLE "document" ALTER COLUMN "status" SET DEFAULT 'processing';
        ALTER TABLE "document" ALTER COLUMN "status" TYPE VARCHAR(20) USING "status"::VARCHAR(20);
        ALTER TABLE "document" ALTER COLUMN "task_id" TYPE VARCHAR(255) USING "task_id"::VARCHAR(255);
        ALTER TABLE "document" ALTER COLUMN "file_type" TYPE VARCHAR(50) USING "file_type"::VARCHAR(50);
        ALTER TABLE "chat_message" ALTER COLUMN "role" TYPE VARCHAR(20) USING "role"::VARCHAR(20);
        ALTER TABLE "chat_message" ALTER COLUMN "session_id" TYPE INT USING "session_id"::INT;
        ALTER TABLE "chat_session" ALTER COLUMN "user_id" TYPE INT USING "user_id"::INT;
        ALTER TABLE "chat_session" ALTER COLUMN "session_name" TYPE VARCHAR(100) USING "session_name"::VARCHAR(100);
        ALTER TABLE "document_chunk" ALTER COLUMN "document_id" TYPE INT USING "document_id"::INT;
        ALTER TABLE "friendrequest" ALTER COLUMN "requester_id" TYPE INT USING "requester_id"::INT;
        ALTER TABLE "friendrequest" ALTER COLUMN "receiver_id" TYPE INT USING "receiver_id"::INT;"""
