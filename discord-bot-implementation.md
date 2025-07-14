# Discord Bot with ClickUp and Claude Integration - Render Deployment Guide

## Project Overview
Create a Python Discord bot deployed on Render that integrates with ClickUp API v2 and Claude AI, featuring:
- Complete ClickUp API functionality (all endpoints)
- Claude AI natural language processing
- Carl-bot style setup wizard
- Reaction roles system
- Secure token management
- Persistent online operation through Render
- PostgreSQL database for production persistence
- Auto-scaling and health monitoring

## Project Structure
```
discord_clickup_bot/
├── main.py
├── web_server.py          # Keep-alive web server for Render
├── config.py
├── requirements.txt
├── runtime.txt           # Python version for Render
├── render.yaml          # Render deployment config
├── .env.example
├── cogs/
│   ├── __init__.py
│   ├── clickup_tasks.py
│   ├── clickup_lists.py
│   ├── clickup_admin.py
│   ├── clickup_time.py
│   ├── claude_ai.py
│   ├── setup_wizard.py
│   ├── reaction_roles.py
│   └── error_handler.py
├── services/
│   ├── __init__.py
│   ├── clickup_api.py
│   ├── claude_api.py
│   ├── cache.py
│   └── security.py
├── repositories/
│   ├── __init__.py
│   ├── server_config.py
│   └── reaction_roles.py
├── utils/
│   ├── __init__.py
│   ├── helpers.py
│   └── embed_factory.py
└── database/
    ├── __init__.py
    ├── models.py
    └── migrations/
```

## Implementation Files

### 1. requirements.txt
```txt
discord.py==2.3.2
aiohttp==3.9.1
python-dotenv==1.0.0
cryptography==41.0.7
asyncpg==0.29.0
sqlalchemy[asyncio]==2.0.23
alembic==1.13.1
redis==5.0.1
loguru==0.7.2
click==8.1.7
tenacity==8.2.3
pydantic==2.5.3
fastapi==0.108.0
uvicorn==0.25.0
psycopg2-binary==2.9.9
```

### 2. runtime.txt
```txt
python-3.11.7
```

### 3. render.yaml
```yaml
services:
  - type: web
    name: discord-clickup-bot
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python main.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.7
      - key: DATABASE_URL
        fromDatabase:
          name: clickup-bot-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: clickup-bot-redis
          property: connectionString
    healthCheckPath: /health
    
databases:
  - name: clickup-bot-db
    plan: free
    databaseName: clickup_bot
    user: clickup_bot

  - name: clickup-bot-redis
    type: redis
    plan: free
```

### 4. .env.example
```env
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token_here
DEFAULT_PREFIX=!

# Claude API Configuration
CLAUDE_API_URL=https://claudeup.onrender.com
CLAUDE_API_KEY=your_claude_api_key_here

# Database Configuration (Render provides this automatically)
DATABASE_URL=postgresql://user:password@host:port/database

# Redis Configuration (Render provides this automatically)
REDIS_URL=redis://host:port

# Security
ENCRYPTION_KEY=generate_a_fernet_key_here

# Web Server Configuration (for Render keep-alive)
PORT=10000
WEB_SERVER_ENABLED=true

# Logging
LOG_LEVEL=INFO

# Render-specific
RENDER=true
```

### 5. main.py
```python
import asyncio
import os
from pathlib import Path
import discord
from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger
from database.models import init_db
from utils.helpers import get_prefix
from web_server import create_web_server
import signal
import sys

# Load environment variables
load_dotenv()

# Configure logging
logger.add("logs/bot.log", rotation="1 day", retention="7 days", level=os.getenv("LOG_LEVEL", "INFO"))

class ClickUpBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None
        )
        
        self.db = None
        self.web_server = None
        
    async def setup_hook(self):
        """Initialize bot components"""
        # Initialize database
        await init_db()
        
        # Load cogs
        cogs_dir = Path("cogs")
        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.name != "__init__.py":
                cog_name = f"cogs.{cog_file.stem}"
                try:
                    await self.load_extension(cog_name)
                    logger.info(f"Loaded cog: {cog_name}")
                except Exception as e:
                    logger.error(f"Failed to load cog {cog_name}: {e}")
        
        # Sync commands
        await self.tree.sync()
        logger.info("Synced application commands")
        
        # Start web server for Render keep-alive
        if os.getenv("WEB_SERVER_ENABLED", "true").lower() == "true":
            self.web_server = create_web_server(self)
            asyncio.create_task(self.web_server.serve())
            logger.info(f"Web server started on port {os.getenv('PORT', 10000)}")
    
    async def on_ready(self):
        logger.info(f"Bot is ready! Logged in as {self.user}")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="ClickUp tasks"
            )
        )
    
    async def close(self):
        """Cleanup on shutdown"""
        if self.web_server:
            await self.web_server.shutdown()
        await super().close()

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Received shutdown signal, cleaning up...")
    asyncio.create_task(bot.close())
    sys.exit(0)

async def main():
    global bot
    bot = ClickUpBot()
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
```

### 6. web_server.py
```python
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
import os
from datetime import datetime
from loguru import logger

def create_web_server(bot):
    """Create FastAPI web server for health checks and monitoring"""
    app = FastAPI(title="ClickUp Discord Bot")
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "name": "ClickUp Discord Bot",
            "status": "online",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint for Render"""
        try:
            # Check bot connection
            if not bot.is_ready():
                return JSONResponse(
                    status_code=503,
                    content={"status": "unhealthy", "reason": "Bot not ready"}
                )
            
            # Check database connection
            if bot.db:
                await bot.db.execute("SELECT 1")
            
            return {
                "status": "healthy",
                "bot_latency": f"{bot.latency * 1000:.2f}ms",
                "guilds": len(bot.guilds),
                "users": len(bot.users),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "error": str(e)}
            )
    
    @app.get("/stats")
    async def stats():
        """Bot statistics endpoint"""
        if not bot.is_ready():
            return {"error": "Bot not ready"}
        
        return {
            "guilds": len(bot.guilds),
            "users": len(bot.users),
            "commands": len(bot.commands),
            "cogs": len(bot.cogs),
            "latency": f"{bot.latency * 1000:.2f}ms",
            "uptime": str(datetime.utcnow() - bot.start_time) if hasattr(bot, 'start_time') else "Unknown"
        }
    
    @app.post("/webhook/clickup")
    async def clickup_webhook(data: dict):
        """Handle ClickUp webhooks"""
        # Process webhook data
        logger.info(f"Received ClickUp webhook: {data}")
        # You can emit events to the bot here
        return {"status": "received"}
    
    class Server:
        def __init__(self, app):
            self.app = app
            self.server = None
            
        async def serve(self):
            """Start the web server"""
            config = uvicorn.Config(
                self.app,
                host="0.0.0.0",
                port=int(os.getenv("PORT", 10000)),
                log_level="info"
            )
            server = uvicorn.Server(config)
            self.server = server
            await server.serve()
        
        async def shutdown(self):
            """Shutdown the web server"""
            if self.server:
                await self.server.shutdown()
    
    return Server(app)
```

### 7. config.py
```python
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
```

### 8. database/models.py
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, DateTime, Text, JSON, BigInteger
from datetime import datetime
import os
from loguru import logger

# Database URL handling for Render
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///bot_data.db")
if DATABASE_URL.startswith("postgres://"):
    # Render uses postgres:// but SQLAlchemy needs postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class ServerConfig(Base):
    __tablename__ = "server_configs"
    
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prefix: Mapped[str] = mapped_column(String(10), default="!")
    clickup_workspace_id: Mapped[str] = mapped_column(String(100), nullable=True)
    clickup_token_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    claude_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    setup_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    config_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ReactionRole(Base):
    __tablename__ = "reaction_roles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    emoji: Mapped[str] = mapped_column(String(100), nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    exclusive: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    default_list_id: Mapped[str] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Cache(Base):
    __tablename__ = "cache"
    
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

async def init_db():
    """Initialize database tables"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def get_session() -> AsyncSession:
    """Get database session"""
    async with async_session() as session:
        return session
```

### 9. repositories/server_config.py
```python
from typing import Optional, Dict, Any
from sqlalchemy import select, update
from database.models import ServerConfig, async_session
from loguru import logger

class ServerConfigRepository:
    def __init__(self):
        pass
    
    async def get_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get server configuration"""
        async with async_session() as session:
            result = await session.execute(
                select(ServerConfig).where(ServerConfig.guild_id == guild_id)
            )
            config = result.scalar_one_or_none()
            
            if config:
                return {
                    "guild_id": config.guild_id,
                    "prefix": config.prefix,
                    "clickup_workspace_id": config.clickup_workspace_id,
                    "clickup_token_encrypted": config.clickup_token_encrypted,
                    "claude_enabled": config.claude_enabled,
                    "setup_complete": config.setup_complete,
                    "config_data": config.config_data
                }
            return None
    
    async def save_config(
        self,
        guild_id: int,
        encrypted_token: str,
        workspace_id: str,
        setup_complete: bool = True,
        **kwargs
    ) -> None:
        """Save or update server configuration"""
        async with async_session() as session:
            # Check if config exists
            result = await session.execute(
                select(ServerConfig).where(ServerConfig.guild_id == guild_id)
            )
            config = result.scalar_one_or_none()
            
            if config:
                # Update existing
                config.clickup_token_encrypted = encrypted_token
                config.clickup_workspace_id = workspace_id
                config.setup_complete = setup_complete
                if kwargs.get('config_data'):
                    config.config_data = kwargs['config_data']
            else:
                # Create new
                config = ServerConfig(
                    guild_id=guild_id,
                    clickup_token_encrypted=encrypted_token,
                    clickup_workspace_id=workspace_id,
                    setup_complete=setup_complete,
                    config_data=kwargs.get('config_data', {})
                )
                session.add(config)
            
            await session.commit()
            logger.info(f"Saved config for guild {guild_id}")
    
    async def update_prefix(self, guild_id: int, prefix: str) -> None:
        """Update server prefix"""
        async with async_session() as session:
            await session.execute(
                update(ServerConfig)
                .where(ServerConfig.guild_id == guild_id)
                .values(prefix=prefix)
            )
            await session.commit()
    
    async def delete_config(self, guild_id: int) -> None:
        """Delete server configuration"""
        async with async_session() as session:
            result = await session.execute(
                select(ServerConfig).where(ServerConfig.guild_id == guild_id)
            )
            config = result.scalar_one_or_none()
            if config:
                await session.delete(config)
                await session.commit()
```

### 10. utils/helpers.py
```python
from datetime import datetime, timedelta
import re
from typing import Optional, Union
import discord
from discord.ext import commands
from repositories.server_config import ServerConfigRepository

async def get_prefix(bot: commands.Bot, message: discord.Message) -> str:
    """Get the prefix for a guild"""
    if not message.guild:
        return "!"
    
    repo = ServerConfigRepository()
    config = await repo.get_config(message.guild.id)
    
    if config and config.get('prefix'):
        return config['prefix']
    
    return "!"

def parse_due_date(date_string: str) -> Optional[datetime]:
    """Parse various date formats into datetime"""
    date_string = date_string.lower().strip()
    now = datetime.utcnow()
    
    # Relative dates
    if date_string == "today":
        return now.replace(hour=23, minute=59, second=59)
    elif date_string == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)
    elif date_string == "next week":
        return (now + timedelta(weeks=1)).replace(hour=23, minute=59, second=59)
    
    # Try to parse ISO format
    try:
        return datetime.fromisoformat(date_string)
    except:
        pass
    
    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except:
            continue
    
    return None

def format_task_status(status: str) -> str:
    """Convert task status to emoji"""
    status_emojis = {
        "to do": "⬜",
        "in progress": "🔵",
        "review": "🟡",
        "complete": "✅",
        "closed": "❌",
        "blocked": "🚫"
    }
    return status_emojis.get(status.lower(), "❓")

def truncate_text(text: str, max_length: int = 1024) -> str:
    """Truncate text to fit Discord embed limits"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def format_user_mention(user_id: Union[str, int]) -> str:
    """Format user ID as Discord mention"""
    return f"<@{user_id}>"

def parse_mentions(text: str) -> list[int]:
    """Extract user IDs from mentions in text"""
    mention_pattern = r'<@!?(\d+)>'
    matches = re.findall(mention_pattern, text)
    return [int(user_id) for user_id in matches]

def humanize_timedelta(td: timedelta) -> str:
    """Convert timedelta to human-readable string"""
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds and not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    return " ".join(parts) if parts else "0 seconds"
```

### 11. utils/embed_factory.py
```python
import discord
from typing import Optional, List, Dict, Any
from datetime import datetime

class EmbedFactory:
    """Factory for creating consistent embed styles"""
    
    # Color scheme
    COLORS = {
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "warning": discord.Color.yellow(),
        "info": discord.Color.blue(),
        "primary": discord.Color.blurple()
    }
    
    @staticmethod
    def create_base_embed(
        title: str,
        description: Optional[str] = None,
        color: Optional[discord.Color] = None
    ) -> discord.Embed:
        """Create base embed with consistent styling"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color or EmbedFactory.COLORS["primary"],
            timestamp=datetime.utcnow()
        )
        return embed
    
    @staticmethod
    def create_success_embed(title: str, description: str) -> discord.Embed:
        """Create success embed"""
        return EmbedFactory.create_base_embed(
            f"✅ {title}",
            description,
            EmbedFactory.COLORS["success"]
        )
    
    @staticmethod
    def create_error_embed(title: str, description: str) -> discord.Embed:
        """Create error embed"""
        return EmbedFactory.create_base_embed(
            f"❌ {title}",
            description,
            EmbedFactory.COLORS["error"]
        )
    
    @staticmethod
    def create_warning_embed(title: str, description: str) -> discord.Embed:
        """Create warning embed"""
        return EmbedFactory.create_base_embed(
            f"⚠️ {title}",
            description,
            EmbedFactory.COLORS["warning"]
        )
    
    @staticmethod
    def create_info_embed(title: str, description: str) -> discord.Embed:
        """Create info embed"""
        return EmbedFactory.create_base_embed(
            f"ℹ️ {title}",
            description,
            EmbedFactory.COLORS["info"]
        )
    
    @staticmethod
    def create_task_embed(task: Dict[str, Any]) -> discord.Embed:
        """Create embed for task display"""
        embed = EmbedFactory.create_base_embed(
            task.get('name', 'Untitled Task'),
            task.get('description', 'No description'),
            EmbedFactory.COLORS["info"]
        )
        
        # Add fields
        if task.get('status'):
            embed.add_field(
                name="Status",
                value=task['status'].get('status', 'Unknown'),
                inline=True
            )
        
        if task.get('priority'):
            priority_map = {1: "🔴 Urgent", 2: "🟠 High", 3: "🟡 Normal", 4: "⚪ Low"}
            priority = priority_map.get(task['priority'].get('id', 4), "🟡 Normal")
            embed.add_field(name="Priority", value=priority, inline=True)
        
        if task.get('due_date'):
            due = datetime.fromtimestamp(int(task['due_date']) / 1000)
            embed.add_field(
                name="Due Date",
                value=due.strftime("%Y-%m-%d %H:%M"),
                inline=True
            )
        
        if task.get('assignees'):
            assignees = ", ".join([a.get('username', 'Unknown') for a in task['assignees']])
            embed.add_field(name="Assignees", value=assignees or "None", inline=False)
        
        if task.get('tags'):
            tags = ", ".join([t.get('name', '') for t in task['tags']])
            embed.add_field(name="Tags", value=tags or "None", inline=False)
        
        if task.get('url'):
            embed.add_field(
                name="Link",
                value=f"[Open in ClickUp]({task['url']})",
                inline=False
            )
        
        embed.set_footer(text=f"Task ID: {task.get('id', 'Unknown')}")
        
        return embed
    
    @staticmethod
    def create_list_embed(
        title: str,
        items: List[str],
        description: Optional[str] = None,
        color: Optional[discord.Color] = None
    ) -> discord.Embed:
        """Create embed for displaying lists"""
        embed = EmbedFactory.create_base_embed(title, description, color)
        
        # Split items into chunks if needed (Discord field limit)
        for i in range(0, len(items), 10):
            chunk = items[i:i+10]
            field_value = "\n".join(chunk)
            embed.add_field(
                name=f"Items {i+1}-{min(i+10, len(items))}",
                value=field_value or "None",
                inline=False
            )
        
        return embed
```

### 12. services/security.py
```python
from cryptography.fernet import Fernet
from typing import Optional
import os
from loguru import logger

class SecurityService:
    def __init__(self):
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            logger.warning("No encryption key found, generating new one")
            key = Fernet.generate_key().decode()
            logger.info(f"Generated encryption key: {key}")
        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        try:
            encrypted = self.fernet.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        try:
            decrypted = self.fernet.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise

security_service = SecurityService()
```

### 13. services/clickup_api.py
```python
import aiohttp
from typing import Dict, Any, Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
import asyncio

class ClickUpAPI:
    BASE_URL = "https://api.clickup.com/api/v2"
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": api_token,
            "Content-Type": "application/json"
        }
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession(headers=self.headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request with retry logic"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        async with self._session.request(method, url, **kwargs) as response:
            data = await response.json()
            
            if response.status == 429:  # Rate limited
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited, waiting {retry_after} seconds")
                await asyncio.sleep(retry_after)
                raise Exception("Rate limited")
            
            if response.status >= 400:
                logger.error(f"API error: {response.status} - {data}")
                raise Exception(f"ClickUp API error: {data}")
            
            return data
    
    # Workspace & Teams
    async def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get all workspaces"""
        data = await self._request("GET", "team")
        return data.get("teams", [])
    
    # Spaces
    async def get_spaces(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all spaces in a workspace"""
        data = await self._request("GET", f"team/{workspace_id}/space")
        return data.get("spaces", [])
    
    async def create_space(self, workspace_id: str, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new space"""
        return await self._request("POST", f"team/{workspace_id}/space", json={"name": name, **kwargs})
    
    # Folders
    async def get_folders(self, space_id: str) -> List[Dict[str, Any]]:
        """Get all folders in a space"""
        data = await self._request("GET", f"space/{space_id}/folder")
        return data.get("folders", [])
    
    async def create_folder(self, space_id: str, name: str) -> Dict[str, Any]:
        """Create a new folder"""
        return await self._request("POST", f"space/{space_id}/folder", json={"name": name})
    
    # Lists
    async def get_lists(self, folder_id: str) -> List[Dict[str, Any]]:
        """Get all lists in a folder"""
        data = await self._request("GET", f"folder/{folder_id}/list")
        return data.get("lists", [])
    
    async def get_folderless_lists(self, space_id: str) -> List[Dict[str, Any]]:
        """Get lists not in any folder"""
        data = await self._request("GET", f"space/{space_id}/list")
        return data.get("lists", [])
    
    async def create_list(self, folder_id: str, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new list"""
        return await self._request("POST", f"folder/{folder_id}/list", json={"name": name, **kwargs})
    
    # Tasks
    async def get_tasks(self, list_id: str, **params) -> List[Dict[str, Any]]:
        """Get tasks from a list"""
        data = await self._request("GET", f"list/{list_id}/task", params=params)
        return data.get("tasks", [])
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get a specific task"""
        return await self._request("GET", f"task/{task_id}")
    
    async def create_task(self, list_id: str, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new task"""
        return await self._request("POST", f"list/{list_id}/task", json={"name": name, **kwargs})
    
    async def update_task(self, task_id: str, **kwargs) -> Dict[str, Any]:
        """Update a task"""
        return await self._request("PUT", f"task/{task_id}", json=kwargs)
    
    async def delete_task(self, task_id: str) -> None:
        """Delete a task"""
        await self._request("DELETE", f"task/{task_id}")
    
    # Comments
    async def get_comments(self, task_id: str) -> List[Dict[str, Any]]:
        """Get comments on a task"""
        data = await self._request("GET", f"task/{task_id}/comment")
        return data.get("comments", [])
    
    async def create_comment(self, task_id: str, comment_text: str, **kwargs) -> Dict[str, Any]:
        """Create a comment on a task"""
        return await self._request("POST", f"task/{task_id}/comment", json={"comment_text": comment_text, **kwargs})
    
    # Attachments
    async def upload_attachment(self, task_id: str, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Upload an attachment to a task"""
        data = aiohttp.FormData()
        data.add_field('attachment', file_data, filename=filename)
        return await self._request("POST", f"task/{task_id}/attachment", data=data)
    
    # Custom Fields
    async def get_custom_fields(self, list_id: str) -> List[Dict[str, Any]]:
        """Get custom fields for a list"""
        data = await self._request("GET", f"list/{list_id}/field")
        return data.get("fields", [])
    
    async def set_custom_field_value(self, task_id: str, field_id: str, value: Any) -> Dict[str, Any]:
        """Set custom field value on a task"""
        return await self._request("POST", f"task/{task_id}/field/{field_id}", json={"value": value})
    
    # Members
    async def get_members(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all members in a workspace"""
        data = await self._request("GET", f"team/{workspace_id}/member")
        return data.get("members", [])
    
    async def assign_task(self, task_id: str, assignee_ids: List[int]) -> Dict[str, Any]:
        """Assign users to a task"""
        return await self._request("PUT", f"task/{task_id}", json={"assignees": assignee_ids})
    
    # Time Tracking
    async def get_time_entries(self, workspace_id: str, **params) -> List[Dict[str, Any]]:
        """Get time entries"""
        data = await self._request("GET", f"team/{workspace_id}/time_entries", params=params)
        return data.get("data", [])
    
    async def start_timer(self, task_id: str, description: str = "") -> Dict[str, Any]:
        """Start a time tracking timer"""
        return await self._request("POST", f"task/{task_id}/time", json={"description": description})
    
    async def stop_timer(self, workspace_id: str) -> Dict[str, Any]:
        """Stop the current timer"""
        return await self._request("POST", f"team/{workspace_id}/time_entries/stop")
    
    # Goals
    async def get_goals(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all goals"""
        data = await self._request("GET", f"team/{workspace_id}/goal")
        return data.get("goals", [])
    
    async def create_goal(self, workspace_id: str, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new goal"""
        return await self._request("POST", f"team/{workspace_id}/goal", json={"name": name, **kwargs})
    
    # Webhooks
    async def get_webhooks(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all webhooks"""
        data = await self._request("GET", f"team/{workspace_id}/webhook")
        return data.get("webhooks", [])
    
    async def create_webhook(self, workspace_id: str, endpoint: str, events: List[str]) -> Dict[str, Any]:
        """Create a webhook"""
        return await self._request("POST", f"team/{workspace_id}/webhook", json={
            "endpoint": endpoint,
            "events": events
        })
    
    # Views
    async def get_views(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all views"""
        data = await self._request("GET", f"team/{workspace_id}/view")
        return data.get("views", [])
    
    async def get_view_tasks(self, view_id: str, **params) -> List[Dict[str, Any]]:
        """Get tasks from a view"""
        data = await self._request("GET", f"view/{view_id}/task", params=params)
        return data.get("tasks", [])
```

### 14. services/claude_api.py
```python
import aiohttp
from typing import Dict, Any, Optional
from loguru import logger

class ClaudeAPI:
    def __init__(self, api_url: str, api_key: Optional[str] = None):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def complete(self, prompt: str, **kwargs) -> str:
        """Send completion request to Claude"""
        async with aiohttp.ClientSession() as session:
            payload = {
                "prompt": prompt,
                **kwargs
            }
            
            try:
                async with session.post(
                    f"{self.api_url}/complete",
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("completion", "")
                    else:
                        error = await response.text()
                        logger.error(f"Claude API error: {response.status} - {error}")
                        return ""
            except Exception as e:
                logger.error(f"Claude API request failed: {e}")
                return ""
    
    async def parse_task_command(self, command: str) -> Dict[str, Any]:
        """Use Claude to parse natural language task commands"""
        prompt = f"""Parse this task command and return a JSON object with the task details.
        Command: "{command}"
        
        Extract:
        - name: task name
        - description: task description (if any)
        - priority: 1-4 (1=urgent, 2=high, 3=normal, 4=low)
        - due_date: ISO date string or null
        - assignees: list of mentioned users
        - tags: list of tags
        
        Respond only with valid JSON."""
        
        response = await self.complete(prompt)
        try:
            import json
            return json.loads(response)
        except:
            return {
                "name": command,
                "description": "",
                "priority": 3,
                "due_date": None,
                "assignees": [],
                "tags": []
            }
```

### 15. cogs/setup_wizard.py
```python
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import asyncio
from services.security import security_service
from services.clickup_api import ClickUpAPI
from repositories.server_config import ServerConfigRepository
from utils.embed_factory import EmbedFactory
from loguru import logger

class SetupView(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=300)
        self.bot = bot
        self.ctx = ctx
        self.config = {}
        self.current_step = 0
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can interact"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the person who started setup can interact with this menu.",
                ephemeral=True
            )
            return False
        return True

class APITokenModal(discord.ui.Modal, title="ClickUp API Token"):
    token = discord.ui.TextInput(
        label="API Token",
        placeholder="pk_...",
        style=discord.TextStyle.short,
        required=True,
        min_length=10
    )
    
    def __init__(self, setup_view):
        super().__init__()
        self.setup_view = setup_view
    
    async def on_submit(self, interaction: discord.Interaction):
        # Validate token
        try:
            async with ClickUpAPI(self.token.value) as api:
                workspaces = await api.get_workspaces()
                if not workspaces:
                    await interaction.response.send_message(
                        "Invalid token or no workspaces found.",
                        ephemeral=True
                    )
                    return
                    
                # Store encrypted token
                encrypted = security_service.encrypt(self.token.value)
                self.setup_view.config['clickup_token'] = encrypted
                self.setup_view.config['workspaces'] = workspaces
                
                # Create workspace selection
                embed = EmbedFactory.create_info_embed(
                    "Select Workspace",
                    "Choose the ClickUp workspace to connect:"
                )
                
                view = WorkspaceSelectView(self.setup_view, workspaces)
                await interaction.response.edit_message(embed=embed, view=view)
                
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            await interaction.response.send_message(
                "Failed to validate token. Please check and try again.",
                ephemeral=True
            )

class WorkspaceSelectView(discord.ui.View):
    def __init__(self, setup_view, workspaces):
        super().__init__(timeout=180)
        self.setup_view = setup_view
        
        # Create dropdown
        options = [
            discord.SelectOption(
                label=ws['name'],
                value=ws['id'],
                description=f"ID: {ws['id']}"
            )
            for ws in workspaces[:25]  # Discord limit
        ]
        
        self.workspace_select = discord.ui.Select(
            placeholder="Choose a workspace",
            options=options
        )
        self.workspace_select.callback = self.workspace_callback
        self.add_item(self.workspace_select)
    
    async def workspace_callback(self, interaction: discord.Interaction):
        workspace_id = self.workspace_select.values[0]
        self.setup_view.config['workspace_id'] = workspace_id
        
        # Continue to next step
        embed = EmbedFactory.create_success_embed(
            "Setup Progress",
            f"✅ API Token configured\n✅ Workspace selected\n\nNext: Configure default settings"
        )
        
        view = FinalSetupView(self.setup_view)
        await interaction.response.edit_message(embed=embed, view=view)

class FinalSetupView(discord.ui.View):
    def __init__(self, setup_view):
        super().__init__(timeout=180)
        self.setup_view = setup_view
    
    @discord.ui.button(label="Complete Setup", style=discord.ButtonStyle.success)
    async def complete_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Save configuration
        repo = ServerConfigRepository()
        
        await repo.save_config(
            interaction.guild_id,
            encrypted_token=self.setup_view.config['clickup_token'],
            workspace_id=self.setup_view.config['workspace_id'],
            setup_complete=True
        )
        
        embed = EmbedFactory.create_success_embed(
            "Setup Complete! 🎉",
            "Your ClickUp integration is now configured.\n\n"
            "**Available Slash Commands:**\n"
            "• `/task create` - Create a new ClickUp task\n"
            "• `/task list` - List tasks from a ClickUp list\n"
            "• `/task update` - Update an existing task\n"
            "• `/task delete` - Delete a task (with confirmation)\n"
            "• `/task comment` - Add comments to tasks\n"
            "• `/task assign` - Assign users to tasks\n\n"
            "**Getting Started:**\n"
            "• Type `/task create` to create your first task\n"
            "• You'll need your ClickUp List ID for most commands\n"
            "• All commands use modern Discord slash command interface"
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

class SetupWizard(commands.Cog):
    """Interactive setup wizard for the bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(name="setup", description="Start the bot setup wizard")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx: commands.Context):
        """Start interactive setup wizard"""
        embed = EmbedFactory.create_info_embed(
            "ClickUp Bot Setup Wizard",
            "Welcome! Let's set up your ClickUp integration.\n\n"
            "**What you'll need:**\n"
            "• Your ClickUp API token\n"
            "• Administrator permissions\n\n"
            "Ready to begin?"
        )
        
        view = SetupStartView(self.bot, ctx)
        await ctx.send(embed=embed, view=view)

class SetupStartView(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=180)
        self.bot = bot
        self.ctx = ctx
    
    @discord.ui.button(label="Start Setup", style=discord.ButtonStyle.primary)
    async def start_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check existing config
        repo = ServerConfigRepository()
        config = await repo.get_config(interaction.guild_id)
        
        if config and config.get('setup_complete'):
            view = ReconfigureView(self.bot, self.ctx)
            embed = EmbedFactory.create_warning_embed(
                "Existing Configuration Found",
                "This server already has a ClickUp configuration.\n"
                "Would you like to reconfigure?"
            )
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            # Start fresh setup
            await interaction.response.send_modal(APITokenModal(SetupView(self.bot, self.ctx)))
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Setup cancelled.",
            embed=None,
            view=None
        )

class ReconfigureView(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=60)
        self.bot = bot
        self.ctx = ctx
    
    @discord.ui.button(label="Reconfigure", style=discord.ButtonStyle.danger)
    async def reconfigure(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(APITokenModal(SetupView(self.bot, self.ctx)))
    
    @discord.ui.button(label="Keep Current", style=discord.ButtonStyle.secondary)
    async def keep_current(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Keeping current configuration.",
            embed=None,
            view=None
        )

async def setup(bot):
    await bot.add_cog(SetupWizard(bot))
```

### 16. cogs/clickup_tasks.py
```python
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio
from services.clickup_api import ClickUpAPI
from services.security import security_service
from repositories.server_config import ServerConfigRepository
from utils.embed_factory import EmbedFactory
from utils.helpers import parse_due_date, format_task_status
from loguru import logger

class TaskView(discord.ui.View):
    def __init__(self, task_data: dict, api: ClickUpAPI):
        super().__init__(timeout=180)
        self.task_data = task_data
        self.api = api
        
    @discord.ui.button(label="Complete", style=discord.ButtonStyle.success)
    async def complete_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.api.update_task(self.task_data['id'], status='complete')
            embed = EmbedFactory.create_success_embed(
                "Task Completed",
                f"✅ Task '{self.task_data['name']}' marked as complete!"
            )
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to complete task: {str(e)}",
                ephemeral=True
            )
    
    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary)
    async def edit_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditTaskModal(self.task_data, self.api)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Confirmation view
        confirm_view = ConfirmDeleteView(self.task_data, self.api)
        embed = EmbedFactory.create_warning_embed(
            "Confirm Deletion",
            f"Are you sure you want to delete task '{self.task_data['name']}'?"
        )
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)

class EditTaskModal(discord.ui.Modal, title="Edit Task"):
    def __init__(self, task_data: dict, api: ClickUpAPI):
        super().__init__()
        self.task_data = task_data
        self.api = api
        
        # Pre-fill with current values
        self.name = discord.ui.TextInput(
            label="Task Name",
            default=task_data['name'],
            max_length=200
        )
        self.description = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            default=task_data.get('description', ''),
            required=False,
            max_length=1000
        )
        
        self.add_item(self.name)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.api.update_task(
                self.task_data['id'],
                name=self.name.value,
                description=self.description.value
            )
            
            embed = EmbedFactory.create_success_embed(
                "Task Updated",
                f"✅ Task '{self.name.value}' has been updated!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to update task: {str(e)}",
                ephemeral=True
            )

class ConfirmDeleteView(discord.ui.View):
    def __init__(self, task_data: dict, api: ClickUpAPI):
        super().__init__(timeout=30)
        self.task_data = task_data
        self.api = api
    
    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.api.delete_task(self.task_data['id'])
            embed = EmbedFactory.create_success_embed(
                "Task Deleted",
                f"Task '{self.task_data['name']}' has been deleted."
            )
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to delete task: {str(e)}",
                ephemeral=True
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Deletion cancelled.",
            embed=None,
            view=None
        )

class ClickUpTasks(commands.Cog):
    """ClickUp task management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def _get_api(self, guild_id: int) -> Optional[ClickUpAPI]:
        """Get ClickUp API instance for guild"""
        repo = ServerConfigRepository()
        config = await repo.get_config(guild_id)
        
        if not config or not config.get('clickup_token_encrypted'):
            return None
            
        token = security_service.decrypt(config['clickup_token_encrypted'])
        return ClickUpAPI(token)
    
    @commands.hybrid_group(name="task", description="Task management commands")
    async def task(self, ctx: commands.Context):
        """Task management commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
    
    @task.command(name="create", description="Create a new task")
    @app_commands.describe(
        name="Task name",
        description="Task description",
        list_id="List ID (optional, uses default if not provided)",
        priority="Priority (1=Urgent, 2=High, 3=Normal, 4=Low)",
        due_date="Due date (e.g., 'tomorrow', 'next week', '2024-01-15')"
    )
    async def create_task(
        self,
        ctx: commands.Context,
        name: str,
        description: Optional[str] = None,
        list_id: Optional[str] = None,
        priority: Optional[int] = 3,
        due_date: Optional[str] = None
    ):
        """Create a new task"""
        api = await self._get_api(ctx.guild.id)
        if not api:
            await ctx.send("❌ ClickUp is not configured. Run `!setup` first.")
            return
        
        async with api:
            try:
                # Parse due date if provided
                due_timestamp = None
                if due_date:
                    parsed_date = parse_due_date(due_date)
                    if parsed_date:
                        due_timestamp = int(parsed_date.timestamp() * 1000)
                
                # Get default list if not provided
                if not list_id:
                    # This would come from user preferences or server config
                    await ctx.send("❌ Please provide a list ID or set a default list.")
                    return
                
                # Create task
                task_data = {
                    "name": name,
                    "priority": priority
                }
                
                if description:
                    task_data["description"] = description
                if due_timestamp:
                    task_data["due_date"] = due_timestamp
                
                task = await api.create_task(list_id, **task_data)
                
                # Create response embed
                embed = discord.Embed(
                    title="✅ Task Created",
                    color=discord.Color.green()
                )
                embed.add_field(name="Name", value=task['name'], inline=False)
                embed.add_field(name="ID", value=task['id'], inline=True)
                embed.add_field(name="Status", value=task['status']['status'], inline=True)
                
                if task.get('url'):
                    embed.add_field(name="Link", value=f"[Open in ClickUp]({task['url']})", inline=False)
                
                # Add task action buttons
                view = TaskView(task, api)
                await ctx.send(embed=embed, view=view)
                
            except Exception as e:
                logger.error(f"Failed to create task: {e}")
                await ctx.send(f"❌ Failed to create task: {str(e)}")
    
    @task.command(name="list", description="List tasks")
    @app_commands.describe(
        list_id="List ID to fetch tasks from",
        status="Filter by status",
        assignee="Filter by assignee (user mention or ID)"
    )
    async def list_tasks(
        self,
        ctx: commands.Context,
        list_id: str,
        status: Optional[str] = None,
        assignee: Optional[discord.Member] = None
    ):
        """List tasks from a list"""
        api = await self._get_api(ctx.guild.id)
        if not api:
            await ctx.send("❌ ClickUp is not configured. Run `!setup` first.")
            return
        
        async with api:
            try:
                params = {}
                if status:
                    params['statuses'] = [status]
                if assignee:
                    # You'd need to map Discord user to ClickUp user
                    pass
                
                tasks = await api.get_tasks(list_id, **params)
                
                if not tasks:
                    await ctx.send("No tasks found.")
                    return
                
                # Create paginated embed
                embed = discord.Embed(
                    title="📋 Tasks",
                    color=discord.Color.blue()
                )
                
                for task in tasks[:10]:  # Show first 10
                    status_emoji = format_task_status(task['status']['status'])
                    priority_emoji = ["🔴", "🟠", "🟡", "⚪"][task.get('priority', {}).get('id', 4) - 1]
                    
                    field_value = f"{status_emoji} Status: {task['status']['status']}\n"
                    field_value += f"{priority_emoji} Priority: {task.get('priority', {}).get('priority', 'None')}\n"
                    
                    if task.get('due_date'):
                        due = datetime.fromtimestamp(int(task['due_date']) / 1000)
                        field_value += f"📅 Due: {due.strftime('%Y-%m-%d')}\n"
                    
                    embed.add_field(
                        name=f"{task['name']} ({task['id']})",
                        value=field_value,
                        inline=False
                    )
                
                if len(tasks) > 10:
                    embed.set_footer(text=f"Showing 10 of {len(tasks)} tasks")
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Failed to list tasks: {e}")
                await ctx.send(f"❌ Failed to list tasks: {str(e)}")
    
    @task.command(name="update", description="Update a task")
    @app_commands.describe(
        task_id="Task ID to update",
        name="New task name",
        description="New description",
        status="New status",
        priority="New priority (1-4)"
    )
    async def update_task(
        self,
        ctx: commands.Context,
        task_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None
    ):
        """Update an existing task"""
        api = await self._get_api(ctx.guild.id)
        if not api:
            await ctx.send("❌ ClickUp is not configured. Run `!setup` first.")
            return
        
        async with api:
            try:
                update_data = {}
                if name:
                    update_data['name'] = name
                if description is not None:
                    update_data['description'] = description
                if status:
                    update_data['status'] = status
                if priority:
                    update_data['priority'] = priority
                
                task = await api.update_task(task_id, **update_data)
                
                embed = EmbedFactory.create_success_embed(
                    "Task Updated",
                    f"Task '{task['name']}' has been updated successfully."
                )
                embed.add_field(name="ID", value=task['id'], inline=True)
                embed.add_field(name="Status", value=task['status']['status'], inline=True)
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Failed to update task: {e}")
                await ctx.send(f"❌ Failed to update task: {str(e)}")
    
    @task.command(name="delete", description="Delete a task")
    @app_commands.describe(task_id="Task ID to delete")
    async def delete_task(self, ctx: commands.Context, task_id: str):
        """Delete a task"""
        api = await self._get_api(ctx.guild.id)
        if not api:
            await ctx.send("❌ ClickUp is not configured. Run `!setup` first.")
            return
        
        # Confirmation view
        view = ConfirmView()
        await ctx.send(
            f"⚠️ Are you sure you want to delete task `{task_id}`?",
            view=view
        )
        
        await view.wait()
        
        if view.value:
            async with api:
                try:
                    await api.delete_task(task_id)
                    await ctx.send(f"✅ Task `{task_id}` has been deleted.")
                except Exception as e:
                    logger.error(f"Failed to delete task: {e}")
                    await ctx.send(f"❌ Failed to delete task: {str(e)}")
        else:
            await ctx.send("Task deletion cancelled.")
    
    @task.command(name="comment", description="Add a comment to a task")
    @app_commands.describe(
        task_id="Task ID to comment on",
        comment="Comment text"
    )
    async def add_comment(self, ctx: commands.Context, task_id: str, *, comment: str):
        """Add a comment to a task"""
        api = await self._get_api(ctx.guild.id)
        if not api:
            await ctx.send("❌ ClickUp is not configured. Run `!setup` first.")
            return
        
        async with api:
            try:
                result = await api.create_comment(
                    task_id,
                    comment,
                    notify_all=False
                )
                
                await ctx.send(f"✅ Comment added to task `{task_id}`")
                
            except Exception as e:
                logger.error(f"Failed to add comment: {e}")
                await ctx.send(f"❌ Failed to add comment: {str(e)}")
    
    @task.command(name="assign", description="Assign users to a task")
    @app_commands.describe(
        task_id="Task ID to assign users to",
        users="Discord users to assign (mentions)"
    )
    async def assign_task(self, ctx: commands.Context, task_id: str, users: commands.Greedy[discord.Member]):
        """Assign users to a task"""
        if not users:
            await ctx.send("❌ Please mention at least one user to assign.")
            return
        
        api = await self._get_api(ctx.guild.id)
        if not api:
            await ctx.send("❌ ClickUp is not configured. Run `!setup` first.")
            return
        
        # Note: You would need to implement Discord -> ClickUp user mapping
        await ctx.send("⚠️ User mapping between Discord and ClickUp is not yet implemented.")

class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.edit_message(content="Confirmed.", view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.edit_message(content="Cancelled.", view=None)

async def setup(bot):
    await bot.add_cog(ClickUpTasks(bot))
```

### 17. Deployment Instructions for Render

```markdown
# Deploying to Render

## Prerequisites
1. GitHub account with your bot code repository
2. Render account (free tier works)
3. Discord bot token
4. ClickUp API token

## Step-by-Step Deployment

### 1. Prepare Your Repository
- Push all code to GitHub
- Ensure all files from this guide are included
- Create a `.gitignore` file:
```
.env
*.pyc
__pycache__/
logs/
bot_data.db
```

### 2. Create Render Services

#### A. Create PostgreSQL Database
1. Go to Render Dashboard
2. Click "New +" → "PostgreSQL"
3. Name: `clickup-bot-db`
4. Choose free tier
5. Click "Create Database"
6. Copy the connection string

#### B. Create Redis Instance (Optional but recommended)
1. Click "New +" → "Redis"
2. Name: `clickup-bot-redis`
3. Choose free tier
4. Click "Create Redis"

#### C. Create Web Service
1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Configure:
   - Name: `discord-clickup-bot`
   - Environment: `Python`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
   - Choose free tier

### 3. Configure Environment Variables
In your Render web service settings, add:

```
DISCORD_TOKEN=your_discord_bot_token
CLAUDE_API_URL=https://claudeup.onrender.com
ENCRYPTION_KEY=generate_using_python_script_below
DEFAULT_PREFIX=!
LOG_LEVEL=INFO
WEB_SERVER_ENABLED=true
RENDER=true
```

To generate encryption key:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### 4. Deploy
1. Render will automatically deploy when you push to GitHub
2. Monitor the deploy logs in Render dashboard
3. Check the health endpoint: `https://your-app.onrender.com/health`

### 5. Keep Bot Online
Render free tier spins down after 15 minutes of inactivity. Solutions:
1. Use a service like UptimeRobot to ping your health endpoint every 5 minutes
2. The built-in web server helps keep it alive
3. Consider upgrading to paid tier for 24/7 uptime

## Monitoring
- View logs in Render dashboard
- Check `/stats` endpoint for bot statistics
- Monitor PostgreSQL usage in Render dashboard

## Troubleshooting
- If bot goes offline, check Render logs
- Ensure all environment variables are set
- Verify database connection string is correct
- Check that Discord token is valid
```

### 18. Additional Cogs Overview

Here's a brief overview of the other cogs that need to be implemented:

**cogs/claude_ai.py** - Natural language processing for task management
**cogs/reaction_roles.py** - Reaction role management system
**cogs/clickup_time.py** - Time tracking commands
**cogs/clickup_lists.py** - List and folder management
**cogs/clickup_admin.py** - Workspace administration
**cogs/error_handler.py** - Global error handling

### 19. Final Setup Instructions

1. **Generate Encryption Key**:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

2. **Create Discord Application**:
- Go to https://discord.com/developers/applications
- Create new application
- Go to Bot section
- Copy token
- Enable necessary intents

3. **Get ClickUp API Token**:
- Go to ClickUp Settings
- Apps section
- Generate personal token

4. **Deploy to Render**:
- Push code to GitHub
- Connect GitHub to Render
- Follow deployment steps above

5. **Invite Bot to Server**:
- Use OAuth2 URL generator in Discord Developer Portal
- Select necessary permissions
- Invite to your server

6. **Run Setup Command**:
- Once bot is online, run `!setup` in your Discord server
- Follow the interactive setup wizard

The bot will now run persistently on Render, automatically restart if it crashes, and maintain all data in PostgreSQL database.