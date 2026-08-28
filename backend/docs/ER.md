# 认知知识库系统 — 数据库设计文档（ER 图）

结题交付物 5（后端一牵头）：数据库 ER 图 + 表结构说明。
数据库：SQLite（单文件 `knowledge.db`），共 8 张表。建库双路径：启动 `create_all`（零配置）与 Alembic 迁移（`alembic upgrade head`），同源 schema。

## ER 图

```mermaid
erDiagram
    users ||--o{ documents : "拥有 user_id"
    users ||--o{ entities : "拥有 user_id（多用户隔离）"
    documents ||--o{ segments : "包含 document_id"
    documents ||--o{ entities : "首个来源 document_id"
    documents ||--o{ relations : "首个建立 document_id"
    documents ||--o{ evidences : "来源 document_id"
    entity_types ||--o{ entities : "分类 type_id（RESTRICT）"
    relation_types ||--o{ relations : "类型 relation_type_id（RESTRICT）"
    entities ||--o{ relations : "头节点 head_id"
    entities ||--o{ relations : "尾节点 tail_id"
    relations ||--o{ evidences : "证据 relation_id"
    segments ||--o{ evidences : "定位 segment_id"

    users {
        int id PK
        varchar username UK "3-32字符，登录名"
        varchar email UK
        varchar password_hash "bcrypt 哈希（非明文）"
        varchar role "user / admin"
        varchar status "active（P2 禁用预留）"
        datetime created_at
    }
    documents {
        int id PK
        int user_id FK "归属用户（级联删除）"
        varchar filename "原始文件名（已清洗路径成分）"
        varchar stored_name "相对存储名 uploads/uid/uuid.ext"
        varchar file_type "pdf/docx/txt/md"
        int size "字节"
        varchar status "pending/parsing/completed/failed"
        text parse_error "失败原因（≤500字符）"
        datetime created_at
    }
    segments {
        int id PK
        int document_id FK "所属文档（级联删除）"
        int seq "文档内序号"
        text raw_text "原始分段"
        text clean_text "清洗后分段（搜索目标）"
        boolean is_noise "页码/页眉噪音标记"
        datetime created_at
        unique(document_id, seq)
    }
    entity_types {
        int id PK
        varchar name UK "人物/组织/地点/概念/技术"
        varchar color "ECharts 节点着色/图例"
        varchar description
        datetime created_at
    }
    relation_types {
        int id PK
        varchar name UK "包含/属于/相关/引用"
        varchar description
        datetime created_at
    }
    entities {
        int id PK
        int user_id FK "归属用户（级联删除）"
        varchar name "实体名"
        varchar type_id FK "实体类型（RESTRICT）"
        int frequency "累计频次（节点大小依据）"
        json attributes "附加属性"
        int document_id FK "首个来源文档（SET NULL）"
        datetime created_at
        unique(user_id, name)
    }
    relations {
        int id PK
        int head_id FK "头实体（级联删除）"
        int tail_id FK "尾实体（级联删除）"
        int relation_type_id FK "关系类型（RESTRICT）"
        int document_id FK "首个建立该关系的文档（SET NULL）"
        float weight "证据句条数（边粗细）"
        datetime created_at
        unique(head_id, tail_id, relation_type_id)
    }
    evidences {
        int id PK
        int relation_id FK "所属关系（级联删除）"
        int segment_id FK "来源分段（级联删除）"
        int document_id FK "来源文档（级联删除）"
        text sentence "原文证据句"
        datetime created_at
        unique(relation_id, segment_id, sentence)
    }
```

## 核心设计要点

| 要点 | 说明 |
|---|---|
| 多用户隔离 | `entities` 唯一约束为 `(user_id, name)`：跨文档同名实体合并限定在同一用户内，图谱/搜索/文档全部按 `user_id` 过滤 |
| 跨文档节点合并 | 同名实体（同用户内）只存在一行，`frequency` 累加，类型保留先见类型 |
| 关系去重 | `(head_id, tail_id, relation_type_id)` 唯一：重复来源只累加证据句，`weight` 重算为证据句条数 |
| 证据可追溯 | 每条关系 ≥1 条证据句，证据句关联分段 + 来源文档（EXT-06） |
| 级联策略 | 用户删 → 文档/实体级联删；文档删 → 分段/证据级联删；实体删 → 关系级联删；类型被引用时 RESTRICT 禁止删除 |
| 崩溃恢复 | 启动种子把遗留 `parsing` 状态文档重置为 `pending` |
| 时间约定 | 全部 naive UTC（`server_default=func.now()`），前端展示时本地化 |

## 与 PRD §8 数据模型的差异（已写入 README 知会团队）

1. `entities` 增加 `user_id`（PRD 假设单用户，`name` 全局唯一无法多用户隔离）；
2. `entities`/`relations` 增加 `document_id`（PRD ER 要点写明「documents 1-N entities/relations（来源）」，表字段清单漏列，已补全）。
