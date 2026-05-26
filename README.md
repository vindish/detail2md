# detail2md

将 `input/output_<公司名>/` 下的 **JSON 产品列表 + 详情 HTML + 图片** 整合到 PostgreSQL，并为每个产品导出一份独立的 Markdown 文档（含图片附件）。

## 设计概览

- **数据流**：`input/` → 解析 → PostgreSQL（单表 `products`） → 导出 → `output_md/`
- **数据库**：PostgreSQL，`(cpid, pc)` 联合唯一键 + UPSERT，重复运行不会写脏。详情页参数与图片清单使用 `JSONB` 列灵活存储，不为字段差异所困。
- **代码组织**（`src/detail2md/`）：
  - `config.py`     —— 路径与连接配置（密码默认空）
  - `db.py`         —— SQLAlchemy 2.x 模型 + 自动建库建表
  - `parsers.py`    —— JSON / 详情 HTML / 图片目录解析
  - `pipeline.py`   —— 端到端导入流水线（带 UPSERT）
  - `markdown_writer.py` —— 每个产品一个文件夹 + Markdown
  - `verify.py`     —— 校验数据库与导出结果一致性
  - `cli.py`        —— 命令行入口（`init-db / ingest / export-md / verify / all`）

## 关联规则

| 来源 | 关联键 |
| --- | --- |
| `<公司>/json/page_*.json` 中的 `cpList[*]` | 每条以 `cpid + pc` 入库 |
| `<公司>/details/<CPID>_<PC>.html` | 文件名按 `cpid + pc` 大小写不敏感匹配 |
| `<公司>/images/<CLXH>_<CPID>_<PC>/` | 文件夹名优先按 `clxh + cpid + pc` 精确匹配，否则后缀 `*_<cpid>_<pc>` 模糊匹配 |

## 环境准备

PostgreSQL 已安装并运行（默认连接 `localhost:5432`，用户 `postgres`，密码为空，库名 `detail2md`，可通过 `PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE` 环境变量覆盖）。

```cmd
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

依赖：`SQLAlchemy>=2.0`、`psycopg[binary]>=3.1`、`beautifulsoup4>=4.12`、`lxml>=4.9`。

## 使用方式

```cmd
:: 一键完成（推荐）
.\.venv\Scripts\python.exe run.py all
python run.py all
python run.py ingest --company 湖北同威专用汽车有限公司  :: 指定公司
python run.py export-md --company 湖北同威专用汽车有限公司
python run.py export-md

:: 或者按步骤
.\.venv\Scripts\python.exe run.py init-db
.\.venv\Scripts\python.exe run.py ingest                                 :: 全部公司
.\.venv\Scripts\python.exe run.py ingest --company 湖北凯力专用汽车有限公司  :: 指定公司
.\.venv\Scripts\python.exe run.py ingest --company 湖北同威专用汽车有限公司  :: 指定公司   此处功能无法完成，待修正。
.\.venv\Scripts\python.exe run.py export-md
.\.venv\Scripts\python.exe run.py verify
```

`ingest` 可重复执行：依赖 `(cpid, pc)` 唯一键的 ON CONFLICT DO UPDATE，已有记录会被刷新。

## 数据库结构

详情页字段已展开为一字段一列（`Text NOT NULL DEFAULT ''`，缺失以空串占位），便于直接 SQL 查询：

```
products
├── id, company, cpid, pc          基本键
├── clxh, clmc, cpsb               JSON 列表里的关键字段
├── json_data       JSONB          cpList 原始项
├── images          JSONB          [{name, path}] 图片清单
├── detail_html_path / image_dir_path
├── created_at, updated_at
└── 详情页扁平列（53 个，全部 Text，缺失为空串）：
    product_no, detail_cpid, detail_pc, publish_date,
    enterprise_name, brand, production_address,
    detail_clxh, detail_clmc,
    dim_length, dim_width, dim_height,
    cargo_length, cargo_width, cargo_height,
    gross_mass, curb_mass, rated_load, tow_mass,
    load_coef, saddle_max_load,
    cab_capacity, passenger_capacity,
    approach_departure_angle, max_speed, axle_load, overhang,
    chassis_id, chassis_model, spring_leaves,
    axle_count, wheelbase, front_track, rear_track,
    tire_count, tire_spec, steering_form, vin,
    fuel_type, fuel_consumption, emission_standard,
    engine_manufacturer, engine_model, displacement, engine_power,
    reflective_manufacturer, reflective_model, reflective_brand,
    exempt_inspection, abs_system, remarks,
    stop_production_date, stop_sale_date
```

中文字段名 → 英文列名的映射定义在 `src/detail2md/parsers.py` 的 `DETAIL_FIELDS`，新增/修改字段只需改这一处。

如果之前已经建过旧版结构，需要重建：

```cmd
.\.venv\Scripts\python.exe run.py init-db --rebuild
```

## 输出布局

```
output_md/
└── <公司名>/
    └── <CLXH>_<PC>_<CPID>/
        ├── <CLXH>_<PC>_<CPID>.md   # 包含 JSON 字段、详情页全部参数、图片嵌入
        └── images/                 # 该产品全部图片副本
```

Markdown 内容包括：
- 基本信息（cpid / pc / clxh / clmc / cpsb / 公司）
- 详情页全部参数表
- JSON 列表参数表
- 图片嵌入（相对引用 `images/xxx.jpg`）
- 来源文件路径

## 校验

`run.py verify` 会比较：
- `cpList` 总条数 vs 数据库行数
- 每条记录是否都有详情参数与图片
- 每条记录的 MD 目录是否存在、图片数是否一致

最近一次完整运行结果：

```
JSON cpList 条目总数 ......... 1057
PostgreSQL products 表行数 ... 1057
含详情参数的记录数 ........... 1057
含图片的记录数 ............... 1057
导出的 MD 文件数 ............. 1057
[OK] 校验通过。
```

## 扩展

- 新增公司：把 `output_<公司名>/` 放入 `input/` 即可，无需改代码。
- 新增字段：在 `parsers.DETAIL_FIELDS` 追加 `(中文名, 列名)`，运行 `run.py init-db --rebuild` 后重新 `ingest`。
- 切换数据库账号/库：用 `PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE` 环境变量覆盖。




做了什么

设计了一个简洁的 PostgreSQL+SQLAlchemy 2 流水线,代码全部在 src/detail2md/:

config.py 集中配置(默认 localhost/postgres/空密码/detail2md 库,环境变量可覆盖)
db.py SQLAlchemy 2.x 模型 + 自动建库建表,(cpid,pc) 唯一键
parsers.py JSON、详情 HTML、图片目录三种解析
pipeline.py UPSERT 入库,可重复执行
markdown_writer.py 每个产品一文件夹 + 图片副本 + 嵌入引用,文件夹名 clxh_pc_cpid
verify.py 校验三方一致性
cli.py 子命令 init-db / ingest / export-md / verify / all
用 pyproject.toml + requirements.txt 描述依赖,项目根 run.py 作为不安装也能跑的入口。

实际运行:

创建 venv → 安装依赖 → 连接 PostgreSQL 9.5(空密码 OK)
init-db 创建 detail2md 库与 products 表
ingest 处理 2 家公司、1057 条产品,详情/图片命中率 100%
export-md 在 output_md/<公司>/<clxh>_<pc>_<cpid>/ 下写出每个产品的 MD + 图片附件
verify 通过
更新了 README.md,介绍架构、关联规则、命令、表结构、输出布局与校验结果。

重复使用

后续把任意 output_<公司名>/ 目录丢进 input/ 后,运行:

.\.venv\Scripts\python.exe run.py all
就能完成端到端处理,无需改代码。

Est. Credits Used: 14.21
Elapsed time: 9m 18s