"""统一配置。所有路径与数据库连接在此集中，默认 PostgreSQL 密码为空。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    # 输入根目录（包含若干 output_<公司名> 子目录）
    # input_dir: Path = PROJECT_ROOT / "input"
    # input_dir: Path = .. /  "miit-eidc_firstpage"
    input_dir: Path = PROJECT_ROOT.parent / "miit-eidc_db2" / "input_company"
    # Markdown 输出根目录
    output_md_dir: Path = PROJECT_ROOT / "output_md2"

    # PostgreSQL 连接信息（密码默认为空）
    pg_host: str = os.getenv("PGHOST", "localhost")
    pg_port: int = int(os.getenv("PGPORT", "5433"))
    pg_user: str = os.getenv("PGUSER", "miit")
    pg_password: str = os.getenv("PGPASSWORD", "secret")
    pg_database: str = os.getenv("PGDATABASE", "miit")

    @property
    def admin_dsn(self) -> str:
        """连接到 postgres 维护数据库，用于自动创建目标库。"""
        return self._dsn("postgres")

    @property
    def dsn(self) -> str:
        return self._dsn(self.pg_database)

    def _dsn(self, db: str) -> str:
        # SQLAlchemy URL；psycopg v3 驱动
        pw = f":{self.pg_password}" if self.pg_password else ":"
        return f"postgresql+psycopg://{self.pg_user}{pw}@{self.pg_host}:{self.pg_port}/{db}"


settings = Settings()
