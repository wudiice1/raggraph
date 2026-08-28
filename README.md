# raggraph — 认知知识库系统

面向个人 / 小团队的知识管理与图谱构建系统：用户上传文档，系统自动完成解析、清洗、实体与关系抽取、图谱入库，并提供知识图谱可视化浏览、实体检索、路径查询等核心能力。实现「从文件管理到认知关联」的升级。

## 核心闭环（P0）

注册登录（JWT + bcrypt）→ 上传文档（PDF / DOCX / TXT / MD）→ 自动解析实体与关系 → 知识图谱点线展示（ECharts）→ 关键词搜索。

## 仓库结构

| 目录/文件 | 说明 |
|---|---|
| `prd2.md` | 产品需求文档 PRD V1.3（定稿后为官方开发依据） |
| `require.md` | 项目启动与任务分工通知（团队角色表、里程碑、交付物清单） |
| `backend/` | 后端源码（FastAPI + SQLAlchemy + SQLite），启动/测试/迁移/交接说明见 [backend/README.md](backend/README.md) |
| `frontend/` | 前端源码（Vue3 CDN + ECharts，开发中） |

## 快速开始（后端）

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py        # 打开 http://127.0.0.1:8000/docs
```

内置管理员账号：`admin / admin123`（请尽快修改）。运行测试：`.venv/bin/python -m pytest tests/ -v`。

## 技术栈

- 后端：FastAPI + SQLAlchemy 2.0 + SQLite + jieba（知识抽取引擎，可插拔）+ Alembic（数据库迁移）
- 前端：Vue3（CDN 模式）+ ECharts（知识图谱力导向图）

## 分支规范

`main`（主干）/ `dev`（开发）/ `feature-*`（功能分支）；每日下班前提交推送，接口先行（Swagger 文档为准）。
