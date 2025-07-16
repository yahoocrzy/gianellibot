"""
Debug dashboard cog for bot diagnostics
"""
import os
import sys
import platform
import psutil
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Optional
import asyncio
from loguru import logger

from utils.debug_logger import debug_logger
from database.models import async_session, ServerConfig, ClickUpWorkspace, ClaudeConfig
from services.clickup_api import ClickUpAPI
from services.claude_api import ClaudeAPI
from repositories.clickup_oauth_workspaces import ClickUpOAuthWorkspaceRepository

class DebugDashboard(commands.Cog):
    """Debug and diagnostic commands for bot administrators"""
    
    def __init__(self, bot):
        self.bot = bot
        self.startup_diagnostics_run = False
        
    async def cog_load(self):
        """Run startup diagnostics when cog loads"""
        if not self.startup_diagnostics_run:
            await self.run_startup_diagnostics()
            self.startup_diagnostics_run = True
            
    async def run_startup_diagnostics(self):
        """Run comprehensive startup diagnostics"""
        logger.info("Running startup diagnostics...")
        
        # Check environment variables
        required_env = ["DISCORD_TOKEN", "ENCRYPTION_KEY", "CLAUDE_API_URL"]
        missing_env = []
        
        for var in required_env:
            if not os.getenv(var):
                missing_env.append(var)
                
        if missing_env:
            logger.error(f"Missing required environment variables: {missing_env}")
        else:
            logger.info("All required environment variables present")
            
        # Check database connection
        try:
            from sqlalchemy import text
            async with async_session() as session:
                await session.execute(text("SELECT 1"))
            logger.info("Database connection successful")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            
        # Log system information
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Platform: {platform.platform()}")
        logger.info(f"Discord.py version: {discord.__version__}")
        
    @app_commands.command(name="debug", description="Show debug information and bot diagnostics")
    @app_commands.default_permissions(administrator=True)
    async def debug_info(self, interaction: discord.Interaction):
        """Display comprehensive debug information"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            embed = discord.Embed(
                title="🔧 Bot Debug Dashboard",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            # Bot information
            embed.add_field(
                name="Bot Status",
                value=f"**Latency:** {self.bot.latency * 1000:.2f}ms\n"
                      f"**Guilds:** {len(self.bot.guilds)}\n"
                      f"**Users:** {len(self.bot.users)}\n"
                      f"**Cogs:** {len(self.bot.cogs)}",
                inline=True
            )
            
            # System information
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            embed.add_field(
                name="System Resources",
                value=f"**CPU:** {cpu_percent}%\n"
                      f"**Memory:** {memory.percent}%\n"
                      f"**Python:** {sys.version.split()[0]}\n"
                      f"**Platform:** {platform.system()}",
                inline=True
            )
            
            # Environment check
            env_status = []
            env_vars = ["DISCORD_TOKEN", "ENCRYPTION_KEY", "CLAUDE_API_URL", "DATABASE_URL"]
            for var in env_vars:
                status = "✅" if os.getenv(var) else "❌"
                env_status.append(f"{status} {var}")
            
            embed.add_field(
                name="Environment Variables",
                value="\n".join(env_status),
                inline=False
            )
            
            # Get debug stats
            stats = debug_logger.get_debug_stats()
            embed.add_field(
                name="Debug Statistics",
                value=f"**Uptime:** {stats['uptime']}\n"
                      f"**Total Events:** {stats['total_events']}\n"
                      f"**Total Errors:** {stats['total_errors']}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            debug_logger.log_error(e, {"command": "debug_info", "user": str(interaction.user)})
            await interaction.followup.send(
                f"Error generating debug information: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="debug-config", description="Check configuration for this server")
    @app_commands.default_permissions(administrator=True)
    async def debug_config(self, interaction: discord.Interaction):
        """Check server configuration status"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = interaction.guild_id
            
            embed = discord.Embed(
                title="🔍 Server Configuration Status",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            # Check server config
            async with async_session() as session:
                server_config = await session.get(ServerConfig, guild_id)
                
                if server_config:
                    embed.add_field(
                        name="Server Config",
                        value=f"**Prefix:** {server_config.prefix}\n"
                              f"**Claude Enabled:** {server_config.claude_enabled}",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Server Config",
                        value="❌ No server configuration found",
                        inline=False
                    )
                
                # Check ClickUp workspaces
                workspaces = await session.query(ClickUpWorkspace).filter_by(
                    guild_id=guild_id, is_active=True
                ).all()
                
                if workspaces:
                    workspace_info = []
                    for ws in workspaces[:3]:  # Show max 3
                        default = "✅" if ws.is_default else "❌"
                        workspace_info.append(f"{default} {ws.workspace_name}")
                    
                    embed.add_field(
                        name=f"ClickUp Workspaces ({len(workspaces)} total)",
                        value="\n".join(workspace_info),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="ClickUp Workspaces",
                        value="❌ No workspaces configured",
                        inline=False
                    )
                
                # Check Claude config
                claude_config = await session.get(ClaudeConfig, guild_id)
                if claude_config:
                    embed.add_field(
                        name="Claude AI Config",
                        value=f"**Enabled:** {claude_config.is_enabled}\n"
                              f"**Model:** {claude_config.model}\n"
                              f"**Max Tokens:** {claude_config.max_tokens}",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Claude AI Config",
                        value="❌ No Claude configuration found",
                        inline=False
                    )
            
            # Test workspace repository config
            try:
                default_workspace = await ClickUpOAuthWorkspaceRepository.get_default_workspace(guild_id)
                if default_workspace:
                    token = await ClickUpOAuthWorkspaceRepository.get_access_token(default_workspace)
                    if token:
                        api = ClickUpAPI(token)
                        embed.add_field(
                            name="API Status", 
                            value="✅ ClickUp API accessible via workspace repository",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="API Status",
                        value="❌ No working ClickUp configuration found",
                        inline=False
                    )
            except Exception as e:
                embed.add_field(
                    name="API Status",
                    value=f"❌ Error: {str(e)[:100]}",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            debug_logger.log_error(e, {"command": "debug_config", "guild": str(interaction.guild)})
            await interaction.followup.send(
                f"Error checking configuration: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="debug-test-api", description="Test API connections")
    @app_commands.default_permissions(administrator=True)
    async def debug_test_api(self, interaction: discord.Interaction):
        """Test API connections"""
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="🔌 API Connection Tests",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # Test ClickUp API using workspace repository
        try:
            default_workspace = await ClickUpOAuthWorkspaceRepository.get_default_workspace(interaction.guild_id)
            if default_workspace:
                token = await ClickUpOAuthWorkspaceRepository.get_access_token(default_workspace)
                api = ClickUpAPI(token) if token else None
            else:
                api = None
                
            if api:
                async with api:
                    workspaces = await api.get_workspaces()
                    embed.add_field(
                        name="ClickUp API",
                        value=f"✅ Connected\n**Workspaces found:** {len(workspaces)}",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="ClickUp API",
                    value="❌ No API configuration found",
                    inline=False
                )
        except Exception as e:
            embed.add_field(
                name="ClickUp API",
                value=f"❌ Error: {str(e)[:100]}",
                inline=False
            )
            debug_logger.log_error(e, {"test": "clickup_api", "guild": str(interaction.guild)})
        
        # Test Claude API if configured
        try:
            async with async_session() as session:
                claude_config = await session.get(ClaudeConfig, interaction.guild_id)
                if claude_config and claude_config.is_enabled:
                    # Note: Claude API still uses encrypted storage - will be updated later
                    from services.security import decrypt_token
                    api_key = await decrypt_token(claude_config.api_key_encrypted)
                    claude_api = ClaudeAPI(api_key)
                    
                    # Test with a simple message
                    response = await claude_api.test_connection()
                    if response:
                        embed.add_field(
                            name="Claude API",
                            value="✅ Connected and responding",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="Claude API",
                            value="❌ Connection failed",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="Claude API",
                        value="❌ Not configured for this server",
                        inline=False
                    )
        except Exception as e:
            embed.add_field(
                name="Claude API",
                value=f"❌ Error: {str(e)[:100]}",
                inline=False
            )
            debug_logger.log_error(e, {"test": "claude_api", "guild": str(interaction.guild)})
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="debug-errors", description="Show recent errors")
    @app_commands.default_permissions(administrator=True)
    async def debug_errors(self, interaction: discord.Interaction):
        """Display recent errors"""
        await interaction.response.defer(ephemeral=True)
        
        stats = debug_logger.get_debug_stats()
        
        if not stats['recent_errors']:
            await interaction.followup.send("No recent errors logged.", ephemeral=True)
            return
        
        embeds = []
        for i, error in enumerate(stats['recent_errors'][-5:], 1):
            embed = discord.Embed(
                title=f"Error {i}: {error['error_type']}",
                description=error['error_message'][:1024],
                color=discord.Color.red(),
                timestamp=datetime.fromisoformat(error['timestamp'])
            )
            
            # Add context
            context_str = "\n".join([f"**{k}:** {v}" for k, v in error['context'].items()])
            if context_str:
                embed.add_field(
                    name="Context",
                    value=context_str[:1024],
                    inline=False
                )
            
            # Add truncated traceback
            if error.get('traceback'):
                tb_lines = error['traceback'].split('\n')
                # Get last 5 lines of traceback
                tb_summary = '\n'.join(tb_lines[-5:])
                embed.add_field(
                    name="Traceback (last 5 lines)",
                    value=f"```python\n{tb_summary[:1000]}\n```",
                    inline=False
                )
            
            embeds.append(embed)
        
        await interaction.followup.send(embeds=embeds[:5], ephemeral=True)
    
    @app_commands.command(name="debug-cogs", description="Show cog loading status")
    @app_commands.default_permissions(administrator=True)
    async def debug_cogs(self, interaction: discord.Interaction):
        """Display cog loading status"""
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="⚙️ Cog Status",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # List loaded cogs
        loaded_cogs = []
        for name, cog in self.bot.cogs.items():
            cog_file = cog.__module__.split('.')[-1]
            loaded_cogs.append(f"✅ {cog_file}")
        
        if loaded_cogs:
            embed.add_field(
                name=f"Loaded Cogs ({len(loaded_cogs)})",
                value="\n".join(loaded_cogs[:10]),  # Show max 10
                inline=False
            )
        
        # Check for cog files that might not be loaded
        cogs_dir = os.path.join(os.path.dirname(__file__))
        all_cog_files = [f for f in os.listdir(cogs_dir) if f.endswith('.py') and f != '__init__.py']
        
        unloaded = []
        for file in all_cog_files:
            cog_name = file[:-3]  # Remove .py
            if not any(cog_name in name for name in self.bot.cogs):
                # Check if it's a disabled/old file
                if file.endswith('.old') or file.endswith('.disabled') or file.endswith('.future'):
                    unloaded.append(f"⏸️ {file} (disabled)")
                else:
                    unloaded.append(f"❌ {file}")
        
        if unloaded:
            embed.add_field(
                name="Unloaded/Disabled Cogs",
                value="\n".join(unloaded[:10]),
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(DebugDashboard(bot))
    debug_logger.log_cog_load("debug_dashboard", True)