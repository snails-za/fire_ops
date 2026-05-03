from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "device" ADD "installer_contact" VARCHAR(11);
        COMMENT ON COLUMN "device"."installer_contact" IS '安装人联系方式（手机号）';
        COMMENT ON COLUMN "device"."contact" IS '维护人联系方式（手机号）';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "device" DROP COLUMN "installer_contact";
        COMMENT ON COLUMN "device"."contact" IS '联系方式（手机号）';
    """
