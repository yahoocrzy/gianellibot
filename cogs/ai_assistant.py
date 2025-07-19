import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import json
# from services.clickup_api import ClickUpAPI  # Removed ClickUp dependency
from services.claude_api import ClaudeAPI
from repositories.claude_config import ClaudeConfigRepository
from utils.embed_factory import EmbedFactory
# from repositories.clickup_oauth_workspaces import ClickUpOAuthWorkspaceRepository  # Removed ClickUp dependency
from loguru import logger

class AIAssistant(commands.Cog):
    """AI assistant with Claude functionality (ClickUp features disabled)"""
    
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
    
    @app_commands.command(name="ai-assistant", description="AI assistant with Claude functionality")
    async def ai_assistant(self, interaction: discord.Interaction):
        """AI assistant with Claude capabilities (ClickUp features disabled)"""
        # Check if Claude API is available
        claude_api = await self.get_claude_api(interaction.guild_id)
        
        if not claude_api:
            embed = EmbedFactory.create_error_embed(
                "Claude AI Not Configured",
                "Claude AI hasn't been set up yet. Use `/claude-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # ClickUp functionality has been disabled
        embed = EmbedFactory.create_error_embed(
            "ClickUp Features Disabled",
            "ClickUp integration has been removed from this command. Only Claude AI functionality is available."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
        
        # ClickUp action selection has been commented out
        # The following code has been disabled due to ClickUp dependency removal:
        
        # # Show AI action selection
        # embed = EmbedFactory.create_info_embed(
        #     "🤖 AI Assistant",
        #     "What would you like me to help you with?"
        # )
        # ... (rest of ClickUp-dependent code commented out)
    
    # The following methods have been commented out due to ClickUp dependency removal:
    
    # async def handle_create_smart_task(self, interaction: discord.Interaction, clickup_api: ClickUpAPI, claude_api: ClaudeAPI):
    #     """Handle smart task creation - DISABLED"""
    #     All ClickUp-related functionality has been disabled.
    #     The following methods were removed due to ClickUp dependency:
    #     - handle_create_smart_task
    #     - handle_status_report  
    #     - handle_find_tasks
    #     - handle_suggest_improvements
    #     
    #     To re-enable these features, you would need to:
    #     1. Uncomment the ClickUp imports at the top of the file
    #     2. Uncomment the get_clickup_api method
    #     3. Restore the method implementations
    #     4. Update the ai_assistant command to use ClickUp functionality
        pass

async def setup(bot):
    await bot.add_cog(AIAssistant(bot))