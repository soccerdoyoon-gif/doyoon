"""아주 단순한 자동 마이그레이션.

새 버전에서 테이블에 컬럼이 추가되면, 기존 DB(data/app.db)에 빠진 컬럼만 ADD COLUMN 합니다.
(컬럼 삭제/타입 변경은 하지 않으므로 데이터가 지워지지 않습니다.)
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.database import Base
from app.core.logging import get_logger

logger = get_logger("migrate")


def add_missing_columns(engine: Engine) -> list[str]:
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    added = []
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                coltype = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}'))
                added.append(f"{table.name}.{col.name}")
    if added:
        logger.info(f"DB 컬럼 추가: {', '.join(added)}")
    return added
