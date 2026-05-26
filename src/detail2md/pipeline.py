"""数据采集流水线：JSON + 详情 HTML + 图片 -> PostgreSQL。"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .config import settings
from .db import Product, SessionLocal, init_schema, make_engine
from .parsers import (
    discover_companies,
    empty_detail_record,
    find_detail_file,
    find_image_dir,
    iter_cp_list,
    list_images,
    parse_detail_html,
)


def _upsert(session: Session, row: dict) -> None:
    stmt = insert(Product).values(**row)
    update_cols = {
        k: stmt.excluded[k]
        for k in row
        if k not in ("cpid", "pc", "id", "created_at")
    }
    update_cols["updated_at"] = stmt.excluded.created_at
    stmt = stmt.on_conflict_do_update(
        index_elements=["cpid", "pc"],
        set_=update_cols,
    )
    session.execute(stmt)


def ingest_company(company: str, company_dir: Path, session: Session) -> tuple[int, int, int]:
    json_dir = company_dir / "json"
    details_dir = company_dir / "details"
    images_dir = company_dir / "images"

    n_total = n_detail = n_image = 0

    for item in iter_cp_list(json_dir):
        cpid = str(item["cpid"]).strip()
        pc = str(item["pc"]).strip()
        clxh = (item.get("clxh") or "").strip() or None

        detail_file = find_detail_file(details_dir, cpid, pc)
        if detail_file:
            detail_record = parse_detail_html(detail_file)
            n_detail += 1
        else:
            detail_record = empty_detail_record()

        image_dir = find_image_dir(images_dir, cpid, pc, clxh)
        images = list_images(image_dir) if image_dir else []
        if image_dir:
            n_image += 1

        row = dict(
            company=company,
            cpid=cpid,
            pc=pc,
            clxh=clxh,
            clmc=item.get("clmc"),
            cpsb=item.get("cpsb"),
            json_data=item,
            images=images,
            detail_html_path=str(detail_file) if detail_file else None,
            image_dir_path=str(image_dir) if image_dir else None,
            **detail_record,
        )
        _upsert(session, row)
        n_total += 1

    return n_total, n_detail, n_image


def run_ingest(only_companies: Iterable[str] | None = None) -> None:
    init_schema()
    engine = make_engine()
    SessionLocal.configure(bind=engine)

    companies = discover_companies(settings.input_dir)
    if only_companies:
        wanted = set(only_companies)
        companies = [(n, p) for n, p in companies if n in wanted]

    if not companies:
        print(f"[!] 未在 {settings.input_dir} 找到任何 output_<公司> 目录")
        return

    grand_total = grand_detail = grand_image = 0
    with SessionLocal() as session:
        for company, cdir in companies:
            print(f"[*] 处理公司：{company}")
            t, d, i = ingest_company(company, cdir, session)
            session.commit()
            grand_total += t
            grand_detail += d
            grand_image += i
            print(f"    -> 产品 {t}，命中详情 {d}，命中图片目录 {i}")

    print(
        f"[OK] 完成。共写入 {grand_total} 条产品记录"
        f"（详情命中 {grand_detail} / 图片目录命中 {grand_image}）"
    )
