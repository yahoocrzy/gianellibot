import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class BotConfig(BaseModel):
    """Bot configuration model"""
    discord_token: str = Field(default_factory=lambda: os.getenv("DISCORD_TOKEN"))
    default_prefix: str = Field(default="!")
    claude_api_url: str = Field(default_factory=lambda: os.getenv("CLAUDE_API_URL"))
    claude_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("CLAUDE_API_KEY"))
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_data.db"))
    redis_url: Optional[str] = Field(default_factory=lambda: os.getenv("REDIS_URL"))
    encryption_key: str = Field(default_factory=lambda: os.getenv("ENCRYPTION_KEY"))
    log_level: str = Field(default="INFO")
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", 10000)))
    is_render: bool = Field(default_factory=lambda: os.getenv("RENDER", "false").lower() == "true")

config = BotConfig()