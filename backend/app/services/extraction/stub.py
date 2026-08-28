"""占位抽取引擎：不产出实体/关系，仅保证解析流水线状态正常流转（端到端联调用）。

由「知识抽取引擎同学」替换为真实实现（jieba 分词 + 频次过滤 + 句法模式/同句共现），
详见 base.py 的契约说明与 README「抽取引擎接入指南」。
"""
import logging

from app.services.extraction.base import BaseExtractionEngine, ExtractionResult

logger = logging.getLogger(__name__)


class StubExtractionEngine(BaseExtractionEngine):
    name = "stub"

    def extract(self, document_id: int, segments) -> ExtractionResult:
        logger.info("Stub 抽取引擎：文档 %s（%d 个分段）跳过抽取，等待真实引擎接入", document_id, len(segments))
        return ExtractionResult(stats={"engine": "stub", "note": "抽取引擎未实现，返回空结果"})
