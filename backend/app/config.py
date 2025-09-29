from pydantic import BaseSettings, EmailStr
from typing import List


class Settings(BaseSettings):
    app_name: str = "Career Guidance Platform"
    secret_key: str = "super-secret-key"
    access_token_expire_minutes: int = 60 * 24
    algorithm: str = "HS256"
    database_url: str = "sqlite:///./career_guidance.db"
    allow_origins: List[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
