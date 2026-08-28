"""文件 → 全文文本：按文件类型分发的统一入口。"""
from pathlib import Path

from app.services.parser.docx import extract_docx
from app.services.parser.pdf import extract_pdf
from app.services.parser.plain import extract_plain


def parse_document(path: Path, file_type: str) -> str:
    if file_type == "pdf":
        return extract_pdf(path)
    if file_type == "docx":
        return extract_docx(path)
    return extract_plain(path)  # txt / md
