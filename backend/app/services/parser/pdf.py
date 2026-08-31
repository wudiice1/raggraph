"""PDF 文本提取（PyMuPDF）：逐页提取文本、表格提取、页眉页脚噪音过滤与扫描件识别。"""
import re
from pathlib import Path
import pymupdf  # PyMuPDF

# 页眉页脚/纯页码正则
_RE_PAGE_NOISE = re.compile(
    r"^[-—–]?\s*\d{1,4}\s*[-—–]?$"
    r"|^第\s*[0-9一二三四五六七八九十百]+\s*页(\s*[/共]\s*[0-9一二三四五六七八九十百]+\s*页)?$"
    r"|^Page\s+\d+(\s+of\s+\d+)?$",
    re.IGNORECASE
)


def extract_pdf(path: Path) -> str:
    """提取 PDF 文档文本，支持表格提取与页眉页脚清洗。"""
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise ValueError(f"无法打开 PDF 文件，文件可能已损坏或格式不受支持: {exc}") from exc

    if doc.is_encrypted:
        try:
            if not doc.authenticate(""):
                raise ValueError("PDF 文档已被密码加密，无法读取内容")
        except Exception as exc:
            raise ValueError("PDF 文档已被密码加密，无法读取内容") from exc

    parts: list[str] = []
    total_raw_len = 0

    for page in doc:
        page_rect = page.rect
        page_height = page_rect.height
        
        # 尝试提取页面表格
        extracted_tables_text = []
        try:
            tabs = page.find_tables()
            if tabs.tables:
                for tab in tabs:
                    table_df = tab.extract()
                    if table_df:
                        for row in table_df:
                            cleaned_row = [str(c).strip().replace("\n", " ") if c is not None else "" for c in row]
                            if any(cleaned_row):
                                extracted_tables_text.append(" | ".join(cleaned_row))
        except Exception:
            pass

        # 逐块（block）提取文本，过滤上下边界页眉页脚
        blocks = page.get_text("blocks")
        page_text_blocks: list[str] = []

        for b in blocks:
            # b: (x0, y0, x1, y1, text, block_no, block_type)
            if len(b) >= 5:
                y0, y1, btext = b[1], b[3], b[4].strip()
                if not btext:
                    continue

                total_raw_len += len(btext)

                # 顶部 35pt 范围内的极短行或纯页码判定为页眉
                if y0 < 35 and (_RE_PAGE_NOISE.match(btext) or len(btext) < 15):
                    continue
                # 底部 40pt 范围内的极短行或纯页码判定为页脚
                if y1 > (page_height - 40) and (_RE_PAGE_NOISE.match(btext) or len(btext) < 15):
                    continue

                page_text_blocks.append(btext)

        if page_text_blocks:
            parts.append("\n\n".join(page_text_blocks))
        if extracted_tables_text:
            parts.append("\n".join(extracted_tables_text))

    doc.close()

    result = "\n\n".join(parts).strip()
    if not result:
        raise ValueError("未能从文档中提取到文本（可能为扫描版 PDF 或纯图片文件）")

    return result
