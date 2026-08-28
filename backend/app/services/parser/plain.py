"""TXT/MD 纯文本读取：utf-8 → gbk 回退 → 容错解码。"""
from pathlib import Path


def extract_plain(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
