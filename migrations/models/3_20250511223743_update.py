from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "device" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(100),
    "address" VARCHAR(100),
    "location" JSONB,
    "image" VARCHAR(255),
    "status" VARCHAR(50),
    "install_date" DATE,
    "bak" TEXT,
    CONSTRAINT "uid_device_name_374f1e" UNIQUE ("name", "address")
);
CREATE INDEX IF NOT EXISTS "idx_device_name_0312e5" ON "device" ("name", "status", "install_date");
COMMENT ON COLUMN "device"."created_at" IS '创建时间';
COMMENT ON COLUMN "device"."updated_at" IS '更新时间';
COMMENT ON COLUMN "device"."name" IS '设备名称';
COMMENT ON COLUMN "device"."address" IS '地址';
COMMENT ON COLUMN "device"."location" IS '设备位置';
COMMENT ON COLUMN "device"."image" IS '图片路径';
COMMENT ON COLUMN "device"."status" IS '设备状态';
COMMENT ON COLUMN "device"."install_date" IS '安装日期';
COMMENT ON COLUMN "device"."bak" IS '备注';
        ALTER TABLE "user" ADD "updated_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP;
        ALTER TABLE "user" ADD "created_at" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" DROP COLUMN "updated_at";
        ALTER TABLE "user" DROP COLUMN "created_at";
        DROP TABLE IF EXISTS "device";"""
