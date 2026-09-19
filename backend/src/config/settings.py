"""应用配置：ConfigManager + BaseSettings，use_env=False，不读进程环境。"""

from pathlib import Path

from pydantic import Field

from pycore.core import BaseSettings, ConfigManager
from pycore.core.exceptions import ConfigurationError

BACKEND_DIR = Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    debug: bool = False
    secret_key: str
    database_path: str = "data/Customer_Service.db"
    upload_dir: str = "data/uploads"
    host: str = "127.0.0.1"
    port: int = 8099
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5199",
            "http://127.0.0.1:5199",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
        ]
    )
    internal_username: str
    internal_password: str
    jwt_expire_hours: int = 12
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str = ""
    llm_chat_model: str = "qwen-plus"
    llm_embed_model: str = "text-embedding-v3"
    llm_embed_dimensions: int = 1024
    llm_timeout_seconds: float = 60
    llm_max_retries: int = 2
    upload_max_bytes: int = 20971520
    ingest_job_timeout_seconds: int = 300
    chunk_size_chars: int = 500
    chunk_overlap_chars: int = 80
    tag_batch_size: int = 8
    faq_max_per_document: int = 20
    faq_source_max_chars: int = 20000
    faq_similarity_threshold: float = 0.82
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.45
    context_message_limit: int = 16
    message_max_chars: int = 2000
    out_of_scope_text: str = "当前问题超出知识服务范围，你可以点击转人工。"
    no_knowledge_text: str = "现有知识无法回答。你可以点击转人工。"
    wait_human_text: str = "正在等待人工客服"
    tag_taxonomy_path: str = "docs/tag-taxonomy.json"
    ws_heartbeat_seconds: int = 20
    ws_reconnect_max_seconds: int = 30


def resolve_config_path() -> Path:
    env_path = BACKEND_DIR / ".env"
    example_path = BACKEND_DIR / ".env.example"
    if env_path.is_file():
        return env_path
    if example_path.is_file():
        return example_path
    raise ConfigurationError(
        "Configuration file not found",
        config_path=str(env_path),
    )


def load_app_config() -> AppSettings:
    manager: ConfigManager[AppSettings] = ConfigManager()
    try:
        return manager.settings
    except ConfigurationError:
        manager.load(AppSettings, resolve_config_path(), use_env=False)
        return manager.settings


def get_settings() -> AppSettings:
    return ConfigManager.instance().settings
