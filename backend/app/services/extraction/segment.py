"""文本清洗与分段（P0 最小实现，P1 的"清洗前后对比预览"依赖本模块产出的 raw/clean/is_noise）。"""
import re

# 零宽字符、控制字符、段内多余空白
_RE_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_RE_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_RE_INLINE_WS = re.compile(r"[ \t]+")
_RE_MANY_NEWLINES = re.compile(r"\n{3,}")

# 分段长度参数
MIN_SEG_LEN = 100  # 短段向后归并阈值（字符）
MAX_SEG_LEN = 2000  # 单段上限
HARD_CUT = 500  # 长段硬切目标长度

# 噪音段判定：页码（"12" / "- 12 -" / "第 3 页"）等极短独立行
_RE_NOISE = re.compile(
    r"^[-—–]?\s*\d{1,4}\s*[-—–]?$"  # 纯页码
    r"|^第\s*[0-9一二三四五六七八九十百]+\s*页\s*$"  # "第 X 页"
)


def clean_text(text: str) -> str:
    """清洗：去零宽/控制字符、统一换行、压缩空白、合并连续空行。"""
    t = _RE_ZERO_WIDTH.sub("", text)
    t = _RE_CTRL.sub("", t)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _RE_INLINE_WS.sub(" ", t)
    t = _RE_MANY_NEWLINES.sub("\n\n", t)
    return t.strip()


def _is_noise(seg: str) -> bool:
    return bool(_RE_NOISE.match(seg.strip()))


def _find_cut(text: str, target: int) -> int:
    """在 target 附近找最近的句末标点作为硬切点，避免切断句子。"""
    for i in range(target, max(target - 150, 1), -1):
        if text[i - 1] in "。！？!?；;.":
            return i
    return target


def split_segments(text: str) -> list[tuple[str, bool]]:
    """按空行切段 → 短段归并 → 长段硬切 → 噪音标记。

    返回 [(clean_text, is_noise), ...]，顺序即文档内 seq。
    """
    paras = [p.replace("\n", " ").strip() for p in text.split("\n\n")]
    paras = [p for p in paras if p]

    # 短段向后归并
    merged: list[str] = []
    buf = ""
    for p in paras:
        if not buf:
            buf = p
        elif len(buf) < MIN_SEG_LEN:
            buf = f"{buf} {p}"
        else:
            merged.append(buf)
            buf = p
    if buf:
        merged.append(buf)

    # 长段硬切
    segments: list[str] = []
    for seg in merged:
        while len(seg) > MAX_SEG_LEN:
            cut = _find_cut(seg, HARD_CUT)
            segments.append(seg[:cut].strip())
            seg = seg[cut:].strip()
        if seg:
            segments.append(seg)

    return [(s, _is_noise(s)) for s in segments]
