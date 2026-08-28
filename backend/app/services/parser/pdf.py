"""PDF 文本提取（PyMuPDF）。扫描版 PDF 提取为空由流水线判为解析失败。"""
from pathlib import Path

import pymupdf  # PyMuPDF


def extract_pdf(path: Path) -> str:
    parts: list[str] = []
    with pymupdf.open(path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n".join(parts)
