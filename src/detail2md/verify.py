"""校验：数据库内容与 Markdown 输出是否符合需求。"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, or_, select

from .config import settings
from .db import Product, SessionLocal, make_engine
from .parsers import discover_companies, iter_cp_list


def run_verify() -> int:
    engine = make_engine()
    SessionLocal.configure(bind=engine)

    issues: list[str] = []
    summary: list[str] = []

    json_total = 0
    for company, cdir in discover_companies(settings.input_dir):
        json_total += sum(1 for _ in iter_cp_list(cdir / "json"))

    with SessionLocal() as session:
        db_total = session.scalar(select(func.count()).select_from(Product)) or 0
        # 详情页是否解析成功用 detail_html_path 是否非空衡量
        with_detail = session.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.detail_html_path.isnot(None))
        ) or 0
        with_images = session.scalar(
            select(func.count())
            .select_from(Product)
            .where(func.jsonb_array_length(Product.images) > 0)
        ) or 0

        md_root = settings.output_md_dir
        md_count = 0
        for product in session.scalars(select(Product)):
            folder_name = f"{product.pc}_{product.cpid}_{product.clxh or 'UNKNOWN'}"
            for ch in '\\/:*?"<>|':
                folder_name = folder_name.replace(ch, "_")
            d = md_root / product.company / folder_name
            if not d.exists():
                issues.append(f"缺少 MD 目录: {d}")
                continue
            md_file = d / f"{folder_name}.md"
            if not md_file.exists():
                issues.append(f"缺少 MD 文件: {md_file}")
                continue

            md_count += 1
            expected_imgs = len(product.images or [])
            actual_imgs = (
                sum(1 for _ in (d / "images").iterdir()) if (d / "images").exists() else 0
            )
            if expected_imgs != actual_imgs:
                issues.append(
                    f"图片数不一致 {d.name}: 数据库 {expected_imgs} 个, 文件夹 {actual_imgs} 个"
                )

    summary.append(f"JSON cpList 条目总数 ......... {json_total}")
    summary.append(f"PostgreSQL products 表行数 ... {db_total}")
    summary.append(f"含详情参数的记录数 ........... {with_detail}")
    summary.append(f"含图片的记录数 ............... {with_images}")
    summary.append(f"导出的 MD 文件数 ............. {md_count}")

    print("\n".join(summary))
    if json_total != db_total:
        issues.insert(0, f"JSON 总数 ({json_total}) 与数据库行数 ({db_total}) 不一致")

    if issues:
        print("\n[!] 发现以下问题（最多展示前 20 条）：")
        for x in issues[:20]:
            print(" -", x)
        print(f"   ... 共 {len(issues)} 项")
        return 1

    print("\n[OK] 校验通过。")
    return 0
