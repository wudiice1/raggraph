"""上传文件存储：uuid 重命名、按用户目录隔离、分块限长写入。

存储布局：uploads/<user_id>/<uuid4.hex>.<ext>，stored_name 只保存相对路径
（<user_id>/<uuid>.<ext>），不向外部暴露真实文件系统路径。
"""
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

_CHUNK = 1024 * 1024  # 1MB 分块


def save_upload(user_id: int, file: UploadFile, ext: str) -> tuple[str, int]:
    """保存上传文件，返回 (stored_name, size)。超过大小限制抛 ValueError（路由层转 413）。"""
    user_dir = settings.upload_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}.{ext}"
    dest = user_dir / stored_filename
    max_bytes = settings.max_upload_mb * 1024 * 1024

    size = 0
    try:
        with dest.open("wb") as out:
            while chunk := file.file.read(_CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(f"文件超过 {settings.max_upload_mb}MB 大小限制")
                out.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)  # 失败不留半成品文件
        raise

    return f"{user_id}/{stored_filename}", size


def resolve_path(user_id: int, stored_name: str) -> Path:
    """按 stored_name 解析存储路径（仅允许落在 upload_dir 内）。"""
    p = (settings.upload_dir / stored_name).resolve()
    root = settings.upload_dir.resolve()
    if not p.is_relative_to(root):
        raise ValueError("非法存储路径")
    return p
