import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import json
# from services.clickup_api import ClickUpAPI  # Removed ClickUp dependency
from services.claude_api import ClaudeAPI
# from repositories.clickup_oauth_workspaces import ClickUpOAuthWorkspaceRepository  # Removed ClickUp dependency
from repositories.claude_config import ClaudeConfigRepository
from utils.embed_factory import EmbedFactory
# from utils.enhanced_selections import ListSelectView  # Removed ClickUp dependency
from loguru import logger

class AICommandsEnhanced(commands.Cog):
    """Enhanced AI commands with Claude functionality (ClickUp features disabled)"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # async def get_clickup_api(self, guild_id: int) -> Optional[ClickUpAPI]:
    #     """Get ClickUp API instance using workspace repository - DISABLED"""
    #     # ClickUp functionality has been removed
    #     return None
    
    async def get_claude_api(self, guild_id: int) -> Optional[ClaudeAPI]:
        """Get Claude API instance"""
        try:
            config = await ClaudeConfigRepository.get_config(guild_id)
            if config and config.is_enabled:
                api_key = await ClaudeConfigRepository.get_decrypted_api_key(config)
                return ClaudeAPI(api_key)
            return None
        except Exception as e:
            logger.error(f"Error getting Claude API: {e}")
            return None
    
    @app_commands.command(name="ai-create-task", description="AI task creation (ClickUp features disabled)")
    @app_commands.describe(
        command="Natural language description (ClickUp integration removed)"
    )
    async def ai_create_task(
        self,
        interaction: discord.Interaction,
        command: str
    ):
        """AI task parsing - ClickUp functionality disabled"""
        # Check Claude configuration
        claude_api = await self.get_claude_api(interaction.guild_id)
        if not claude_api:
            embed = EmbedFactory.create_error_embed(
                "AI Not Configured",
                "Claude AI hasn't been set up yet. Use `/claude-setup` to enable AI features."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # ClickUp functionality has been disabled
        embed = EmbedFactory.create_error_embed(
            "ClickUp Features Disabled",
            "ClickUp integration has been removed from this command. Only Claude AI parsing is available.\n\n"
            f"Your parsed command: `{command}`"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
        
        # All ClickUp-related functionality has been commented out.
        # The following commands were disabled due to ClickUp dependency removal:
        # - Task creation functionality
        # - Task analysis functionality
        
        # To re-enable these features, you would need to:
        # 1. Uncomment the ClickUp imports at the top of the file
        # 2. Uncomment the get_clickup_api method
        # 3. Restore the ClickUp-dependent implementations
    
    # @app_commands.command(name="ai-analyze-tasks", description="AI-powered task analysis")
    # async def ai_analyze_tasks(self, interaction: discord.Interaction, analysis_type: str):
    #     """Analyze tasks using AI - DISABLED due to ClickUp dependency removal"""
    #     embed = EmbedFactory.create_error_embed(
    #         "ClickUp Features Disabled",
    #         "ClickUp integration has been removed from this command."
    #     )
    #     await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AICommandsEnhanced(bot))