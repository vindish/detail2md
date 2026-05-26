"""命令行入口。"""
from __future__ import annotations

import argparse
import sys

from .db import init_schema
from .markdown_writer import run_export
from .pipeline import run_ingest
from .verify import run_verify


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="detail2md",
        description="公告详情页 + JSON + 图片 -> PostgreSQL -> Markdown 流水线",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-db", help="创建数据库并建表")
    p_init.add_argument("--rebuild", action="store_true", help="先删除旧表再建表")

    p_ing = sub.add_parser("ingest", help="解析 input/ 并写入数据库")
    p_ing.add_argument("--company", action="append", help="只处理指定公司名（可多次指定）")

    sub.add_parser("export-md", help="导出 Markdown 文档及图片")
    sub.add_parser("verify", help="校验数据库与 Markdown 是否符合需求")

    p_all = sub.add_parser("all", help="一键 init-db -> ingest -> export-md -> verify")
    p_all.add_argument("--rebuild", action="store_true", help="先删除旧表再建表")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "init-db":
        init_schema(drop_first=args.rebuild)
        print("[OK] 数据库与表已就绪")
        return 0

    if args.cmd == "ingest":
        run_ingest(only_companies=args.company)
        return 0

    if args.cmd == "export-md":
        run_export()
        return 0

    if args.cmd == "verify":
        return run_verify()

    if args.cmd == "all":
        init_schema(drop_first=args.rebuild)
        print("[OK] 数据库与表已就绪")
        run_ingest()
        run_export()
        return run_verify()

    return 1


if __name__ == "__main__":
    sys.exit(main())
