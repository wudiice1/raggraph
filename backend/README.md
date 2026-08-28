# 认知知识库系统 — 后端

FastAPI + SQLAlchemy + SQLite 后端：注册登录（JWT + bcrypt）→ 文档上传（PDF/DOCX/TXT/MD）→ 后台解析分段 → 知识抽取（引擎可插拔）→ 图谱点线数据 → 关键词搜索。对应 PRD V1.3 的 **P0 核心闭环**。

## 快速开始（零配置）

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

打开 http://127.0.0.1:8000/docs 查看 Swagger 文档（全部接口）。

- 内置管理员账号（AUTH-06）：**admin / admin123**（请尽快修改默认密码）
- 数据库自动创建：`knowledge.db`（SQLite 单文件，免安装）；也可显式执行建库脚本 `.venv/bin/python scripts/init_db.py`（结题交付物 4）
- 上传文件存储：`uploads/<user_id>/<uuid>.<ext>`
- 配置项均可用环境变量覆盖：`SECRET_KEY`、`DATABASE_URL`、`JWT_EXPIRE_MINUTES`、`UPLOAD_DIR`、`MAX_UPLOAD_MB`、`EXTRACTION_ENGINE`、`ADMIN_USERNAME/PASSWORD`（见 `app/config.py`）

## 运行测试

```bash
.venv/bin/python -m pytest tests/ -v
```

覆盖：认证（注册/登录/401/409/密码 bcrypt 哈希）、四格式上传、解析流水线状态流转、失败重解析、重解析清理、图谱点线/节点详情、全文/实体检索、多用户隔离、迁移集成。测试使用独立临时库与上传目录，不污染开发数据。

## 数据库迁移（Alembic）

两条建库路径**同源并存**（同一份 `Base.metadata`）：

| 路径 | 用途 |
|---|---|
| 启动时 `create_all` | 零配置兜底：表已存在时零操作，绝不 alter/drop |
| `alembic upgrade head` | schema 变更的正式通道（迁移全流程管理） |

日常变更流程：

```bash
# 1. 修改 app/models/ 下的模型
# 2. 生成迁移（注意：若 create_all 已建过库，autogenerate 会认为"无差异"，
#    生成初始迁移前需先删除 knowledge.db，或使用全新空库）
.venv/bin/alembic revision --autogenerate -m "变更说明"
# 3. 应用迁移
.venv/bin/alembic upgrade head
```

注意：SQLite 下 autogenerate 对 alter column / rename 等变更识别有限，复杂变更请手写 `op.` 语句。种子数据（默认类型 + admin 账号）是数据而非 schema，由 `app/core/seed.py` 幂等执行，不写入迁移。

## 团队分工与交接说明

require.md 分工：**后端一（框架与接口，本仓库基础）**、**后端二（知识抽取引擎）**、**后端三（文档解析与入库）**。以下两节是后两者的交接说明，涉及归属变更的文件以「✅组长已确认」为准。

### 后端二交接：知识抽取引擎接入指南

引擎契约全部在 `app/services/extraction/base.py`，核心规则：

1. 引擎是**纯函数**：输入 `list[SegmentInfo]`（纯内存），输出 `ExtractionResult`（纯内存），不读不写数据库、不改文档状态；
2. `sentence`（证据句）必须逐字取自某分段的原文（可追溯性）；`type_name` 未命中种子类型自动回退「概念」；
3. 抛异常由流水线兜底：回滚本次写入 → 文档状态 `failed` + `parse_error`；
4. 落库（实体合并/关系去重/证据句/weight 重算）由 `writers.apply_extraction_result` 完成，无需关心。

接入三步：

1. 新建 `app/services/extraction/engine.py`，实现：

```python
from app.services.extraction.base import BaseExtractionEngine, ExtractionResult

class JiebaEngine(BaseExtractionEngine):
    name = "jieba"

    def extract(self, document_id, segments):
        # jieba 分词 → 名词过滤 → 频次统计 → 同句共现/句法模式关系抽取
        entities, relations = [], []
        ...
        return ExtractionResult(entities=entities, relations=relations, stats={...})
```

2. 在 `app/services/extraction/__init__.py` 的 `ENGINE_REGISTRY` 中注册：`"jieba": JiebaEngine`；
3. 把 `app/config.py` 的 `EXTRACTION_ENGINE` 默认值改为 `"jieba"`（或启动时设环境变量 `EXTRACTION_ENGINE=jieba`）。

验证方式：`tests/test_writers.py` 是可执行示例（按契约产出结果后无需关心落库）；联调时替换引擎后跑一遍 `tests/` 全绿即接入成功。

**后端二验收要点**（对照 require.md）：
1. jieba 分词 + 词性标注，名词/名词短语候选实体，按频次过滤（MIN_ENTITY_FREQ 等参数需在 `stats` 中自报，便于写《核心算法说明》）；
2. 复合词消歧：优化名词短语组合（如"北京大学"不被拆成"北京/大学"）；
3. 关系抽取：句法模式匹配 + 同句共现补全；每条关系必须带逐字取自分段的证据句（sentence + segment_id）；
4. 交付物《核心算法说明》：参数调整前后效果对比（见 require.md 交付物 6）。

### 后端三交接：文档解析与入库

require.md 分工中「PDF/DOCX/TXT/MD 解析、文本分段、噪音清洗、对接抽取引擎写库（节点合并/关系去重/证据句）、上传→解析→抽取→入库全流程链路」属**后端三**职责。为保证 P0 闭环可测，后端一已先行实现**基础版**（以下文件），后端三在此基础上完善并接管维护。

| 文件 | 已实现（基础版） | 后端三增强方向 |
|---|---|---|
| `app/services/parser/pdf.py` | PyMuPDF 逐页提取文本；空文本判为扫描件失败 | OCR 识别（超技术栈可裁剪）、页眉页脚剔除、表格结构提取 |
| `app/services/parser/docx.py` | 段落 + 表格单元格文本 | 标题层级识别、样式/目录过滤 |
| `app/services/parser/plain.py` | utf-8 → gbk 回退解码 | 编码自动探测（chardet）、BOM 处理 |
| `app/services/extraction/segment.py` | 空行切段 + 短段归并 + 长段硬切 + 页码/页眉噪音标记 | 清洗规则增强（URL/重复模式/页眉行）、P1 分段清洗对比预览（依赖 raw/clean/is_noise 三列，schema 已就绪） |
| `app/services/storage.py` | uuid 存储名 + 分块限长 + 按用户目录隔离 | 重复文件去重、断点续传（P2） |
| `app/services/pipeline/__init__.py` | 状态机 + 后台线程 + per-doc 并发守卫 + 重解析清理 | 解析进度百分比上报、失败重试策略 |
| `app/services/extraction/writers.py` | 实体 (user_id,name) 合并、关系 (head,tail,type) 去重、证据句写入、weight 重算 | 属性合并策略、类型冲突仲裁策略 |

**约束（勿改，改前团队同步）**：
- 引擎契约（`base.py`）与写库入口 `apply_extraction_result` 的签名是后端二/三的协作分界；
- 重解析清理顺序（删分段→级联清证据句→删零证据关系→删孤儿实体）防跨文档误删，勿调整；
- 状态机枚举（pending/parsing/completed/failed）与 API 响应结构已被前端依赖，变更需同步前端。

**后端三验收要点**：
1. 四格式文档解析不崩溃，失败场景（扫描件/空文件/损坏文件）有明确 `parse_error`；
2. `pytest tests/` 全绿（重点：`test_documents.py` 重解析清理、`test_writers.py` 写库契约）；
3. 与后端二引擎联调：上传 → 分段 → 抽取 → 图谱出现点线的全链路可演示（结题演示录屏的核心流程）。

## 接口一览（/api/v1，13 个 P0 接口）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /auth/register | 注册（用户名/邮箱唯一，密码 bcrypt） |
| POST | /auth/login | 登录，签发 JWT |
| GET | /auth/me | 当前用户信息 |
| POST | /documents/upload | 上传（pdf/docx/txt/md，≤20MB，自动触发解析） |
| GET | /documents | 列表（分页/状态筛选/解析统计） |
| GET | /documents/{id} | 详情（前端轮询解析状态） |
| POST | /documents/{id}/parse | 触发/重新解析（解析中重复触发 409） |
| GET | /graph/overview | 全图点线数据（ECharts 直出，含图例/采样标记） |
| GET | /graph/node/{id} | 节点详情（关系+一跳邻居+证据句+来源文档） |
| GET | /search/fulltext?q= | 全文检索（命中高亮 `<mark>`） |
| GET | /search/entities?q= | 实体检索（含关联统计） |
| GET | /ontology/entity-types | 实体类型（图例着色数据） |
| GET | /ontology/relation-types | 关系类型 |

所有业务接口需 `Authorization: Bearer <token>`；访问他人资源一律 404。

## 对 PRD §8 数据模型的两处修正（请读到后提醒整个团队）

1. **多用户隔离**：PRD 假设单用户（entities.name 全局唯一），本系统多用户注册。修正：`entities` 增加 `user_id`，唯一约束改为 `(user_id, name)`——跨文档同名合并限定在同一用户内，图谱/搜索/文档全部按用户过滤。
2. **溯源列补全**：`entities`/`relations` 增加 `document_id`（首个来源文档，PRD ER 要点本身写明「documents 1-N entities/relations（来源）」），用于重解析清理与将来级联删除。

## 已知限制

- **单进程部署**：后台解析为自管线程模型，仅支持 `python run.py`（单 worker）。请勿用 `uvicorn --workers N`（N>1）或 gunicorn 多进程；开发期 `--reload` 会杀掉解析线程，属预期行为。
- **重解析频次为近似值**：实体 `frequency` 是累计频次，重解析只精确重算关系与证据句（不回溯扣减旧频次）。
- **搜索用 LIKE 而非 FTS5**：SQLite FTS5 默认 unicode61 分词器不切分中文（需编译 jieba tokenizer，违背零配置）；万级分段内 LIKE 满足性能要求。数据量增长后可平滑演进到 FTS5 trigram tokenizer。
- **类型冲突保留先见类型**：同名实体合并时以最先出现的类型为准。
- **Stub 引擎**：默认 `EXTRACTION_ENGINE=stub` 不产出实体/关系（状态流转正常），接入真实引擎后即完成闭环的抽取环节。

## 技术文档（结题交付物 5，后端一牵头）

- **数据库 ER 图**：`docs/ER.md`（Mermaid 格式，含 8 张表字段/约束/关系与设计要点）
- **Swagger 接口文档导出**：`docs/openapi.json`（与 http://127.0.0.1:8000/docs 同源，重新导出命令见下）

```bash
.venv/bin/python -c "import json; from app.main import app; \
json.dump(app.openapi(), open('docs/openapi.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)"
```

## 项目结构

```
backend/
├── run.py                # 启动入口
├── requirements.txt
├── scripts/init_db.py    # 标准化建库脚本（结题交付物 4）
├── docs/                 # ER 图 + Swagger JSON（结题交付物 5）
├── alembic/              # 迁移（env.py 从 app.config 读 URL）
├── app/
│   ├── main.py           # FastAPI 实例/CORS/lifespan（建表+种子+崩溃恢复）
│   ├── config.py         # 全局配置（环境变量可覆盖）
│   ├── database.py       # engine(WAL)/SessionLocal/Base/get_db
│   ├── models/           # 8 张表（users/documents/segments/entity_types/relation_types/entities/relations/evidences）
│   ├── schemas/          # Pydantic 请求/响应模型
│   ├── api/v1/           # auth/documents/graph/search/ontology 路由 + deps
│   ├── core/             # security（bcrypt+PyJWT）、seed（种子）
│   └── services/
│       ├── storage.py    # 上传存储（uuid/限长/目录隔离）
│       ├── parser/       # PDF(PyMuPDF)/DOCX/TXT/MD → 文本
│       ├── pipeline/     # 解析流水线（状态机+线程+重解析清理）
│       └── extraction/   # 引擎契约(base)/stub/writers(落库)/segment(清洗分段)
└── tests/                # pytest（49 个用例）
```
