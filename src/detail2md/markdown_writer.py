"""将数据库中产品逐条导出为 Markdown 文档。"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from sqlalchemy import select

from .config import settings
from .db import Product, SessionLocal, make_engine
from .parsers import DETAIL_FIELDS


_INVALID = re.compile(r'[\\/:*?"<>|]+')


def _safe_dir_name(s: str) -> str:
    return _INVALID.sub("_", s).strip().rstrip(".")


def _pipe(v) -> str:
    if v is None:
        return ""
    return str(v).replace("|", "\\|").replace("\n", " ")


def _detail_table(product: Product) -> str:
    """以 DETAIL_FIELDS 顺序输出，缺失字段以空串显示。"""
    lines = ["## 详情页参数", "", "| 字段 | 值 |", "| --- | --- |"]
    for zh, en in DETAIL_FIELDS:
        lines.append(f"| {zh} | {_pipe(getattr(product, en, ''))} |")
    return "\n".join(lines) + "\n"


def _json_table(data: dict | None) -> str:
    if not data:
        return "## JSON 列表参数\n\n_无数据_\n"
    lines = ["## JSON 列表参数", "", "| 字段 | 值 |", "| --- | --- |"]
    for k, v in data.items():
        lines.append(f"| {k} | {_pipe(v)} |")
    return "\n".join(lines) + "\n"


def export_one(product: Product, root: Path) -> Path:
    clxh = product.clxh or "UNKNOWN"
    folder_name = _safe_dir_name(f"{clxh}_{product.pc}_{product.cpid}")
    out_dir = root / _safe_dir_name(product.company) / folder_name
    img_dir = out_dir / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    image_md_refs: list[str] = []
    if product.images:
        img_dir.mkdir(exist_ok=True)
        for img in product.images:
            src = Path(img["path"])
            if not src.exists():
                continue
            dst = img_dir / src.name
            if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                shutil.copy2(src, dst)
            image_md_refs.append(f"![{src.stem}](images/{src.name})")

    parts: list[str] = []
    parts.append(f"# {clxh}  {product.clmc or ''}".strip())
    parts.append("")
    parts.append(
        f"- 企业：{product.company}\n"
        f"- 产品ID(cpid)：{product.cpid}\n"
        f"- 批次(pc)：{product.pc}\n"
        f"- 车辆型号(clxh)：{clxh}\n"
        f"- 车辆名称(clmc)：{product.clmc or ''}\n"
        f"- 商标(cpsb)：{product.cpsb or ''}"
    )
    parts.append("")
    parts.append(_detail_table(product))
    parts.append(_json_table(product.json_data))

    parts.append("## 图片")
    parts.append("")
    if image_md_refs:
        parts.extend(image_md_refs)
    else:
        parts.append("_无图片_")
    parts.append("")

    if product.detail_html_path:
        parts.append(f"\n_来源详情页：`{product.detail_html_path}`_")
    if product.image_dir_path:
        parts.append(f"\n_来源图片目录：`{product.image_dir_path}`_")

    md_path = out_dir / f"{folder_name}.md"
    md_path.write_text("\n".join(parts), encoding="utf-8")
    return md_path


def run_export() -> None:
    engine = make_engine()
    SessionLocal.configure(bind=engine)

    settings.output_md_dir.mkdir(parents=True, exist_ok=True)

    n = 0
    with SessionLocal() as session:
        for product in session.scalars(select(Product).order_by(Product.company, Product.cpid)):
            export_one(product, settings.output_md_dir)
            n += 1
            if n % 100 == 0:
                print(f"  ...已导出 {n} 条")
    print(f"[OK] 共导出 {n} 个 Markdown 产品包到 {settings.output_md_dir}")
