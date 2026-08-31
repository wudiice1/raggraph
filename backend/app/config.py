"""全局配置：所有配置项均可被环境变量覆盖（测试与部署依赖这一点）。"""
import os
from pathlib import Path

# backend/ 目录（绝对路径，避免 alembic 与 run.py 的 CWD 差异导致指向两个库）
BASE_DIR = Path(__file__).resolve().parent.parent


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


class Settings:
    app_name: str = "认知知识库系统"
    api_v1_prefix: str = "/api/v1"

    database_url: str = _env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'knowledge.db'}")

    secret_key: str = _env("SECRET_KEY", "dev-secret-key-change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(_env("JWT_EXPIRE_MINUTES", "1440"))  # 默认 24 小时

    upload_dir: Path = Path(_env("UPLOAD_DIR", str(BASE_DIR / "uploads")))
    max_upload_mb: int = int(_env("MAX_UPLOAD_MB", "20"))
    allowed_file_types = {"pdf", "docx", "txt", "md"}

    # 抽取引擎注册名（见 app/services/extraction/__init__.py 的 ENGINE_REGISTRY）
    extraction_engine: str = _env("EXTRACTION_ENGINE", "jieba")

    # 内置管理员（AUTH-06）
    default_admin_username: str = _env("ADMIN_USERNAME", "admin")
    default_admin_password: str = _env("ADMIN_PASSWORD", "admin123")
    default_admin_email: str = _env("ADMIN_EMAIL", "admin@example.com")


settings = Settings()
