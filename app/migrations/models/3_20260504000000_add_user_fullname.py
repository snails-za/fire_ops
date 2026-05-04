from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" ADD "fullname" VARCHAR(50);
        UPDATE "user" SET "fullname" = "username" WHERE "fullname" IS NULL OR "fullname" = '';
        ALTER TABLE "user" ALTER COLUMN "fullname" SET NOT NULL;
        COMMENT ON COLUMN "user"."fullname" IS '姓名';
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" DROP COLUMN "fullname";
    """
