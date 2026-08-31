"""TXT/MD 纯文本读取：自动编码探测 (chardet) + 多重回退 + BOM 处理。"""
from pathlib import Path
import chardet


def extract_plain(path: Path) -> str:
    """读取纯文本文件，支持多种编码探测与自动容错。"""
    data = path.read_bytes()
    if not data:
        return ""

    # 1. 尝试使用 chardet 探测编码
    detected = chardet.detect(data)
    detected_encoding = detected.get("encoding") if detected else None

    # 2. 候选编码优先级列表
    candidate_encodings = []
    if detected_encoding:
        candidate_encodings.append(detected_encoding)
    candidate_encodings.extend(["utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "utf-16"])

    # 去重且保持顺序
    seen = set()
    encodings_to_try = []
    for enc in candidate_encodings:
        if enc and enc.lower() not in seen:
            seen.add(enc.lower())
            encodings_to_try.append(enc)

    # 3. 逐个尝试解码
    for encoding in encodings_to_try:
        try:
            text = data.decode(encoding)
            # 去除 UTF-8 BOM
            if text.startswith("\ufeff"):
                text = text[1:]
            return text
        except (UnicodeDecodeError, LookupError):
            continue

    # 4. 最终容错解码
    text = data.decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    return text
