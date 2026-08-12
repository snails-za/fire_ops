"""运行时补齐已有表的增量字段（Tortoise generate_schemas safe 模式不会 ALTER）。"""

from tortoise import Tortoise


async def ensure_document_columns() -> None:
    conn = Tortoise.get_connection("default")
    await conn.execute_query(
        'ALTER TABLE "document" ADD COLUMN IF NOT EXISTS dp_document_id VARCHAR(255)'
    )
