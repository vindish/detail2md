"""数据库模型与会话工厂。

详情页的字段全部展开为独立列（缺失以空字符串占位）。
JSON 列表项与图片列表保留为 JSONB 以容纳来源差异。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings
from .parsers import DETAIL_FIELDS


class Base(DeclarativeBase):
    pass


# 用 type() 动态构造 Product 类，把 DETAIL_FIELDS 全部展开为独立 Text 列。
_product_attrs: dict[str, Any] = {
    "__tablename__": "products",
    "id": Column("id", String, primary_key=False, autoincrement=True),
    "company": Column(String(255), index=True, nullable=False),
    "cpid": Column(String(64), index=True, nullable=False),
    "pc": Column(String(32), index=True, nullable=False),
    "clxh": Column(String(128), index=True),
    "clmc": Column(String(255)),
    "cpsb": Column(String(255)),
    "json_data": Column(JSONB),
    "images": Column(JSONB),
    "detail_html_path": Column(Text),
    "image_dir_path": Column(Text),
    "created_at": Column(DateTime(timezone=True), server_default=text("now()")),
    "updated_at": Column(DateTime(timezone=True), server_default=text("now()")),
    "__table_args__": (
        UniqueConstraint("cpid", "pc", name="uq_product_cpid_pc"),
        Index("ix_product_company_clxh", "company", "clxh"),
    ),
}

# 主键单独声明（保持自增整型）
from sqlalchemy import Integer  # noqa: E402

_product_attrs["id"] = Column(Integer, primary_key=True, autoincrement=True)

# 详情页字段 → 独立 Text 列，全部 NOT NULL，默认空串占位
for _, _en in DETAIL_FIELDS:
    _product_attrs[_en] = Column(Text, nullable=False, default="", server_default="")


Product = type("Product", (Base,), _product_attrs)


def make_engine(echo: bool = False):
    return create_engine(settings.dsn, echo=echo, future=True)


SessionLocal = sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)


def ensure_database() -> None:
    """连接到 postgres 维护库，若目标库不存在则创建。"""
    import psycopg

    conn = psycopg.connect(
        host=settings.pg_host,
        port=settings.pg_port,
        user=settings.pg_user,
        password=settings.pg_password,
        dbname="postgres",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (settings.pg_database,)
            )
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{settings.pg_database}"')
    finally:
        conn.close()


def init_schema(drop_first: bool = False) -> None:
    """创建库 + 建表。drop_first=True 时先删除旧表（用于结构变更）。"""
    ensure_database()
    engine = make_engine()
    if drop_first:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    SessionLocal.configure(bind=engine)
