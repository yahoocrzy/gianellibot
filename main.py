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
import aiohttp

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
        self.keep_alive_task = None
        
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
                
                # Start keep-alive task to prevent Render shutdown
                self.keep_alive_task = asyncio.create_task(self.keep_alive_loop())
                debug_logger.log_event("keep_alive", {"status": "started"})
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
    
    async def on_guild_join(self, guild: discord.Guild):
        """Send setup guide when bot joins a new server"""
        logger.info(f"Bot joined new guild: {guild.name} (ID: {guild.id})")
        debug_logger.log_event("guild_join", {"guild_name": guild.name, "guild_id": guild.id})
        
        # Find a suitable channel to send the welcome message
        channel = None
        
        # Try system channel first
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            channel = guild.system_channel
        else:
            # Find the first text channel we can send to
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages and ch.permissions_for(guild.me).embed_links:
                    channel = ch
                    break
        
        if not channel:
            logger.warning(f"Could not find suitable channel to send welcome message in {guild.name}")
            return
        
        # Create the welcome embed
        embed = discord.Embed(
            title="🎉 Welcome to ClickBot!",
            description="Thank you for adding ClickBot to your server! Let's get you set up in just a few minutes.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Step 1: Connect ClickUp (Required)",
            value="1. Run `/clickup-setup`\n"
                  "2. Click **🔐 Login with ClickUp**\n"
                  "3. Sign in and select your workspaces\n"
                  "4. You'll be redirected back here",
            inline=False
        )
        
        embed.add_field(
            name="🔑 Step 2: Add Personal API Token (Required for Full Access)",
            value="Due to ClickUp's OAuth limitations, you need a personal token for task operations:\n"
                  "1. Go to [ClickUp Settings > Apps](https://app.clickup.com/settings/apps)\n"
                  "2. Find **Personal API Token** and click **Generate**\n"
                  "3. Copy the token (starts with `pk_`)\n"
                  "4. Run `/workspace-add-token` and paste it",
            inline=False
        )
        
        embed.add_field(
            name="🤖 Step 3: Enable AI Features (Optional)",
            value="For AI-powered task management:\n"
                  "1. Get a Claude API key from [Anthropic](https://console.anthropic.com/)\n"
                  "2. Run `/claude-setup` and enter your key\n"
                  "3. AI commands will be unlocked!",
            inline=False
        )
        
        embed.add_field(
            name="✅ Quick Test",
            value="After setup, try these commands:\n"
                  "• `/task-create` - Create your first task\n"
                  "• `/calendar` - View tasks in calendar\n"
                  "• `/help` - See all available commands",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Important Note",
            value="Without a personal API token, you'll see **'Team(s) not authorized'** errors. "
                  "This is a ClickUp limitation - the personal token provides full access to your spaces and tasks.",
            inline=False
        )
        
        embed.set_footer(text="Need help? Use /help or check out our documentation!")
        
        # Create a view with helpful buttons
        class WelcomeView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                
                # Add ClickUp setup button
                self.add_item(discord.ui.Button(
                    label="ClickUp Settings",
                    url="https://app.clickup.com/settings/apps",
                    emoji="🔗"
                ))
        
        try:
            await channel.send(embed=embed, view=WelcomeView())
            logger.info(f"Sent welcome message to {guild.name} in #{channel.name}")
        except Exception as e:
            logger.error(f"Failed to send welcome message to {guild.name}: {e}")
        
    async def on_disconnect(self):
        """Handle bot disconnection"""
        logger.warning("Bot disconnected from Discord")
        debug_logger.log_event("bot_disconnect", {"timestamp": datetime.utcnow().isoformat()})
    
    async def on_resumed(self):
        """Handle bot reconnection"""
        logger.info("Bot resumed connection to Discord")
        debug_logger.log_event("bot_resumed", {"timestamp": datetime.utcnow().isoformat()})
    
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
    
    async def keep_alive_loop(self):
        """Keep the service alive by pinging itself every 10 minutes"""
        await self.wait_until_ready()
        
        # Get the service URL from environment or construct it
        service_url = os.getenv("RENDER_EXTERNAL_URL")
        if not service_url:
            # Fallback to constructing URL from service name
            service_name = os.getenv("RENDER_SERVICE_NAME", "gianellibot-1")
            service_url = f"https://{service_name}.onrender.com"
        
        logger.info(f"Starting keep-alive loop, pinging: {service_url}")
        
        while not self.is_closed():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{service_url}/health", timeout=30) as response:
                        if response.status == 200:
                            logger.debug("Keep-alive ping successful")
                        else:
                            logger.warning(f"Keep-alive ping returned status {response.status}")
            except Exception as e:
                logger.warning(f"Keep-alive ping failed: {e}")
            
            # Wait 10 minutes before next ping (Render shuts down after 15 minutes of inactivity)
            await asyncio.sleep(600)  # 10 minutes
    
    async def close(self):
        """Cleanup on shutdown"""
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
        
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
    
    # Run bot with auto-restart on connection errors
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            async with bot:
                await bot.start(os.getenv("DISCORD_TOKEN"))
        except (discord.ConnectionClosed, discord.GatewayNotFound, discord.HTTPException) as e:
            retry_count += 1
            logger.error(f"Connection error (attempt {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                wait_time = min(300, 60 * retry_count)  # Exponential backoff, max 5 minutes
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.critical("Max retries exceeded, shutting down")
                break
        except Exception as e:
            logger.critical(f"Unexpected error: {e}")
            break

if __name__ == "__main__":
    asyncio.run(main())