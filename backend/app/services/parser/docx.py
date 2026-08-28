"""DOCX 文本提取（python-docx）：段落 + 表格单元格。"""
from pathlib import Path

from docx import Document as DocxDocument


def extract_docx(path: Path) -> str:
    doc = DocxDocument(str(path))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text:
                    parts.append(cell.text)
    return "\n".join(parts)
