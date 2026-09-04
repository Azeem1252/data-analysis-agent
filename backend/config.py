import os
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find and load .env files from current dir, backend dir, or root dir
_backend_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.abspath(os.path.join(_backend_dir, ".."))

for path in [
    os.path.join(_backend_dir, ".env"),
    os.path.join(_root_dir, ".env"),
    ".env",
    "backend/.env",
]:
    if os.path.exists(path):
        load_dotenv(path, override=False)


class Settings(BaseSettings):
    groq_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    llm_provider: str = "groq"  # "groq" or "mistral"
    model_name: str = "llama-3.3-70b-versatile"
    max_retries: int = 3
    sandbox_timeout_seconds: int = 15
    max_upload_mb: int = 25
    session_ttl_minutes: int = 60
    use_docker_sandbox: bool = False  # False = subprocess sandbox, True = Docker

    model_config = SettingsConfigDict(
        env_file=(
            os.path.join(_backend_dir, ".env"),
            os.path.join(_root_dir, ".env"),
            ".env",
            "backend/.env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
