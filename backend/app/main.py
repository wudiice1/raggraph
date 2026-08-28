"""FastAPI 应用入口：路由注册、CORS、启动初始化（建表 + 种子 + 崩溃恢复）。"""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 —— 导入全部模型，保证 Base.metadata 完整
from app.api.v1 import api_router
from app.config import settings
from app.core.seed import seed_database
from app.database import Base, SessionLocal, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _prewarm_jieba() -> None:
    """后台预热 jieba 词典，避免首个解析任务首次加载卡顿（引擎未用到时静默跳过）。"""

    def _load():
        try:
            import jieba

            jieba.initialize()
            jieba.lcut("知识图谱预热")
            logger.info("jieba 词典预热完成")
        except Exception:  # noqa: BLE001 —— 预热失败不影响主流程
            pass

    threading.Thread(target=_load, daemon=True, name="jieba-prewarm").start()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # create_all 是"零配置兜底"（表已存在时零操作）；schema 变更的正式通道是 Alembic（见 README）
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)  # 默认类型 + admin 账号 + parsing→pending 崩溃恢复
    _prewarm_jieba()
    logger.info("%s 启动完成，Swagger 文档: http://127.0.0.1:8000/docs", settings.app_name)
    yield


app = FastAPI(
    title=f"{settings.app_name} API",
    description="文档上传 → 知识抽取 → 图谱可视化 → 知识检索（PRD V1.3 P0 核心闭环）",
    version="1.0.0",
    lifespan=lifespan,
)

# 前端 Vue3(CDN) 本地开发跨域；鉴权走 Authorization 头（非 cookie），无需 credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["健康检查"], summary="健康检查")
def health():
    return {"app": settings.app_name, "status": "ok", "docs": "/docs", "api": settings.api_v1_prefix}
