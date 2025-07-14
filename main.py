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
from datetime import datetime

# Load environment variables
load_dotenv()

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

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
        self.start_time = datetime.utcnow()
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
    # Don't create async tasks in signal handlers
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