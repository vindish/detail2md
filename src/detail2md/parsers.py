"""详情 HTML 解析器与文件路径解析器。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

from bs4 import BeautifulSoup, Tag


# 详情页文件名格式: <CPID>_<PC>.html  例如  A9064409_403.html
DETAIL_FILE_RE = re.compile(r"^(?P<cpid>[A-Za-z0-9]+)_(?P<pc>\d+)\.html$", re.IGNORECASE)

# 图片文件夹格式: <CLXH>_<CPID>_<PC>，CLXH 中可能含字母数字
IMG_DIR_RE = re.compile(r"^(?P<clxh>.+)_(?P<cpid>[A-Za-z0-9]+)_(?P<pc>\d+)$")


# ---------- 详情页字段统一定义 ----------
# (中文字段名, 数据库/Python 列名)。顺序即 Markdown 输出顺序。
DETAIL_FIELDS: list[tuple[str, str]] = [
    ("产品号", "product_no"),
    ("产品ID", "detail_cpid"),
    ("批次", "detail_pc"),
    ("发布日期", "publish_date"),
    ("企业名称", "enterprise_name"),
    ("产品商标", "brand"),
    ("生产地址", "production_address"),
    ("车辆型号", "detail_clxh"),
    ("车辆名称", "detail_clmc"),
    ("外形尺寸长", "dim_length"),
    ("外形尺寸宽", "dim_width"),
    ("外形尺寸高", "dim_height"),
    ("货厢长", "cargo_length"),
    ("货厢宽", "cargo_width"),
    ("货厢高", "cargo_height"),
    ("总质量", "gross_mass"),
    ("整备质量", "curb_mass"),
    ("额定载质量", "rated_load"),
    ("准拖挂车总质量", "tow_mass"),
    ("载质量利用系数", "load_coef"),
    ("半挂车鞍座最大允许载质量", "saddle_max_load"),
    ("驾驶室准乘人数", "cab_capacity"),
    ("额定载客(含驾驶员)", "passenger_capacity"),
    ("接近角/离去角", "approach_departure_angle"),
    ("最高车速", "max_speed"),
    ("轴荷", "axle_load"),
    ("前悬后悬", "overhang"),
    ("底盘ID", "chassis_id"),
    ("底盘型号及企业", "chassis_model"),
    ("钢板弹簧片数", "spring_leaves"),
    ("轴数", "axle_count"),
    ("轴距", "wheelbase"),
    ("前轮距", "front_track"),
    ("后轮距", "rear_track"),
    ("轮胎数", "tire_count"),
    ("轮胎规格", "tire_spec"),
    ("转向形式", "steering_form"),
    ("车辆识别代号(VIN)", "vin"),
    ("燃料种类", "fuel_type"),
    ("油耗", "fuel_consumption"),
    ("排放依据标准", "emission_standard"),
    ("发动机生产企业", "engine_manufacturer"),
    ("发动机型号", "engine_model"),
    ("排量", "displacement"),
    ("发动机功率", "engine_power"),
    ("反光标识企业", "reflective_manufacturer"),
    ("反光标识型号", "reflective_model"),
    ("反光标识商标", "reflective_brand"),
    ("是否免检", "exempt_inspection"),
    ("防抱死系统", "abs_system"),
    ("其它", "remarks"),
    ("停产日期", "stop_production_date"),
    ("停售日期", "stop_sale_date"),
]

DETAIL_ZH_TO_EN: dict[str, str] = {zh: en for zh, en in DETAIL_FIELDS}
DETAIL_EN_COLUMNS: list[str] = [en for _, en in DETAIL_FIELDS]


def empty_detail_record() -> dict[str, str]:
    """返回所有详情字段都为空字符串的占位记录。"""
    return {en: "" for _, en in DETAIL_FIELDS}


# ---------- JSON 列表 ----------
def iter_cp_list(json_dir: Path) -> Iterator[dict[str, Any]]:
    """遍历某公司 json 目录里所有 cpList 项。"""
    for fp in sorted(json_dir.glob("page_*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] 解析 JSON 失败 {fp.name}: {e}")
            continue
        for item in data.get("cpList") or []:
            if item.get("cpid") and item.get("pc"):
                yield item


# ---------- 详情 HTML ----------
def _clean(s: str | None) -> str:
    if s is None:
        return ""
    s = s.replace("\xa0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


def parse_detail_html(html_path: Path) -> dict[str, str]:
    """解析详情页，返回固定形状的扁平字典：所有 DETAIL_FIELDS 列均存在，缺失为空串。"""
    record = empty_detail_record()

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "lxml")
    table = soup.find("table", class_="query_result_table")
    if table is None:
        return record

    # 详情页表格的典型结构：
    #   <tr><td>键1</td><td>值1</td><td>键2</td><td>值2</td></tr>
    # 也可能是  <td>键</td><td colspan='3'>值</td>
    for tr in table.find_all("tr"):
        cells: list[Tag] = tr.find_all("td", recursive=False)
        if not cells:
            continue
        # 跳过纯图片行
        if len(cells) == 1 and cells[0].find("img"):
            continue

        i = 0
        while i < len(cells):
            cell = cells[i]
            text_val = _clean(cell.get_text(" ", strip=True))
            has_span = cell.find("span") is not None
            if not has_span and text_val and i + 1 < len(cells):
                key = text_val.rstrip(":：").strip()
                val_cell = cells[i + 1]
                value = _clean(val_cell.get_text(" ", strip=True))
                en = DETAIL_ZH_TO_EN.get(key)
                if en is not None:
                    record[en] = value
                i += 2
            else:
                i += 1

    return record


def parse_detail_image_refs(html_path: Path) -> list[str]:
    """从详情页提取图片 zpname 列表（用于交叉校验）。"""
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "lxml")
    refs = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        m = re.search(r"zpname=([^&\"']+)", src)
        if m:
            refs.append(m.group(1))
    return refs


# ---------- 路径辅助 ----------
def find_detail_file(details_dir: Path, cpid: str, pc: str) -> Path | None:
    target = f"{cpid}_{pc}.html".lower()
    if not details_dir.exists():
        return None
    for p in details_dir.iterdir():
        if p.name.lower() == target:
            return p
    return None


def find_image_dir(images_dir: Path, cpid: str, pc: str, clxh: str | None) -> Path | None:
    if not images_dir.exists():
        return None
    if clxh:
        exact = images_dir / f"{clxh}_{cpid}_{pc}"
        if exact.is_dir():
            return exact
    suffix = f"_{cpid}_{pc}".lower()
    for p in images_dir.iterdir():
        if p.is_dir() and p.name.lower().endswith(suffix):
            return p
    return None


def list_images(image_dir: Path) -> list[dict[str, str]]:
    if not image_dir or not image_dir.exists():
        return []
    out = []
    for p in sorted(image_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            out.append({"name": p.name, "path": str(p.resolve()).replace("\\", "/")})
    return out


def discover_companies(input_dir: Path) -> list[tuple[str, Path]]:
    if not input_dir.exists():
        return []
    out = []
    for p in sorted(input_dir.iterdir()):
        if p.is_dir() and p.name.startswith("output_"):
            out.append((p.name[len("output_"):], p))
    return out
