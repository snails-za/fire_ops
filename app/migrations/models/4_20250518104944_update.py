from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" ADD "password" VARCHAR(128);
        ALTER TABLE "user" ALTER COLUMN "username" TYPE VARCHAR(20) USING "username"::VARCHAR(20);
        ALTER TABLE "user" ALTER COLUMN "email" TYPE VARCHAR(50) USING "email"::VARCHAR(50);
        CREATE INDEX "idx_device_name_d43932" ON "device" ("name");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX "idx_device_name_d43932";
        ALTER TABLE "user" ADD "hashed_password" VARCHAR(128) NOT NULL;
        ALTER TABLE "user" ALTER COLUMN "username" TYPE VARCHAR(20) USING "username"::VARCHAR(20);
        ALTER TABLE "user" ALTER COLUMN "email" TYPE VARCHAR(50) USING "email"::VARCHAR(50);"""
