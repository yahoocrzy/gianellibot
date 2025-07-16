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
from utils.debug_logger import debug_logger
import signal
import sys
from datetime import datetime

# Load environment variables
load_dotenv()

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

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
        debug_logger.log_event("bot_startup", {"phase": "setup_hook_start"})
        
        # Initialize database
        try:
            await init_db()
            debug_logger.log_event("database", {"status": "initialized"})
        except Exception as e:
            debug_logger.log_error(e, {"phase": "database_init"})
            raise
        
        # Load cogs with enhanced error tracking
        cogs_dir = Path("cogs")
        loaded_cogs = []
        failed_cogs = []
        
        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.name != "__init__.py" and not cog_file.name.endswith(('.old', '.disabled', '.future')):
                cog_name = f"cogs.{cog_file.stem}"
                try:
                    await self.load_extension(cog_name)
                    loaded_cogs.append(cog_name)
                    debug_logger.log_cog_load(cog_name, True)
                except Exception as e:
                    failed_cogs.append((cog_name, str(e)))
                    debug_logger.log_cog_load(cog_name, False, e)
        
        # Log cog loading summary
        debug_logger.log_event("cog_summary", {
            "loaded": len(loaded_cogs),
            "failed": len(failed_cogs),
            "loaded_cogs": loaded_cogs,
            "failed_cogs": failed_cogs
        })
        
        # Sync commands
        try:
            synced = await self.tree.sync()
            debug_logger.log_event("command_sync", {"count": len(synced), "status": "success"})
        except Exception as e:
            debug_logger.log_error(e, {"phase": "command_sync"})
            logger.error(f"Failed to sync commands: {e}")
        
        # Start web server for Render keep-alive
        if os.getenv("WEB_SERVER_ENABLED", "true").lower() == "true":
            try:
                self.web_server = create_web_server(self)
                asyncio.create_task(self.web_server.serve())
                debug_logger.log_event("web_server", {"status": "started", "port": os.getenv('PORT', 10000)})
            except Exception as e:
                debug_logger.log_error(e, {"phase": "web_server_start"})
                logger.error(f"Failed to start web server: {e}")
    
    async def on_ready(self):
        logger.info(f"Bot is ready! Logged in as {self.user}")
        self.start_time = datetime.utcnow()
        
        debug_logger.log_event("bot_ready", {
            "user": str(self.user),
            "guilds": len(self.guilds),
            "users": len(self.users)
        })
        
        # Force sync commands again to ensure they're registered
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} commands")
            debug_logger.log_event("command_sync_ready", {"count": len(synced)})
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
            debug_logger.log_error(e, {"phase": "on_ready_sync"})
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="ClickUp tasks"
            )
        )
        
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Global error handler for commands"""
        debug_logger.log_command(ctx, error)
        
        if isinstance(error, commands.CommandNotFound):
            return
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
            return
            
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing required argument: {error.param}")
            return
            
        # Log unexpected errors
        logger.error(f"Unhandled command error: {error}")
        await ctx.send("An error occurred while processing your command.")
    
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