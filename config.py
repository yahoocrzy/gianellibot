import os
from typing import Optional
from pydantic import BaseModel, Field, field_validator
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

    @field_validator('discord_token')
    @classmethod
    def validate_discord_token(cls, v):
        if not v:
            raise ValueError("DISCORD_TOKEN environment variable is required")
        return v

    @field_validator('encryption_key')
    @classmethod
    def validate_encryption_key(cls, v):
        if not v:
            raise ValueError("ENCRYPTION_KEY environment variable is required")
        if len(v) < 32:
            raise ValueError("ENCRYPTION_KEY must be at least 32 characters long")
        return v

    @field_validator('claude_api_url')
    @classmethod
    def validate_claude_api_url(cls, v):
        if not v:
            raise ValueError("CLAUDE_API_URL environment variable is required")
        return v

config = BotConfig()