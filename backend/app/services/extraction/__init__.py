"""引擎注册表：按名称获取抽取引擎实例。

引擎同学在此注册自己的引擎类，并把 config.py 的 EXTRACTION_ENGINE 改为注册名。
"""
import logging

from app.services.extraction.base import BaseExtractionEngine
from app.services.extraction.engine import JiebaEngine
from app.services.extraction.stub import StubExtractionEngine

logger = logging.getLogger(__name__)

ENGINE_REGISTRY: dict[str, type[BaseExtractionEngine]] = {
    "stub": StubExtractionEngine,
    "jieba": JiebaEngine,
}


def get_engine(name: str) -> BaseExtractionEngine:
    cls = ENGINE_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"未注册的抽取引擎: {name}（可用: {', '.join(ENGINE_REGISTRY)}）")
    return cls()
