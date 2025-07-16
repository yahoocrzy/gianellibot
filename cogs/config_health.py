import discord
from discord.ext import commands
from discord import app_commands
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from utils.embed_factory import EmbedFactory
from loguru import logger

class ConfigHealth(commands.Cog):
    """Configuration health check utilities"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="config-status", description="Check the health of ClickUp configuration")
    @app_commands.default_permissions(administrator=True)
    async def config_status(self, interaction: discord.Interaction):
        """Check the health of ClickUp configuration"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check if workspaces are configured
            workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
            
            if workspaces:
                # Get default workspace
                default_workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
                
                embed = EmbedFactory.create_success_embed(
                    "✅ Configuration Healthy",
                    "ClickUp is properly configured and working!"
                )
                
                embed.add_field(
                    name="Current Setup",
                    value=f"• **Total Workspaces**: {len(workspaces)}\n"
                          f"• **Default Workspace**: {default_workspace.workspace_name if default_workspace else 'None set'}\n"
                          f"• **Workspace ID**: `{default_workspace.workspace_id if default_workspace else 'N/A'}`\n"
                          f"• **Status**: ✅ Ready to use",
                    inline=False
                )
                
                embed.add_field(
                    name="Available Commands",
                    value="• `/task-create` - Create new tasks\n"
                          "• `/task-list` - View and manage tasks\n"
                          "• `/calendar` - View tasks in calendar\n"
                          "• `/upcoming` - See upcoming tasks\n"
                          "• `/workspace-list` - Manage workspaces",
                    inline=False
                )
                
                if len(workspaces) > 1:
                    embed.add_field(
                        name="Multiple Workspaces",
                        value=f"You have {len(workspaces)} workspaces configured. Use `/workspace-switch` to change the active one.",
                        inline=False
                    )
                    
            else:
                embed = EmbedFactory.create_error_embed(
                    "❌ ClickUp Not Configured",
                    "ClickUp hasn't been set up for this server yet."
                )
                embed.add_field(
                    name="Quick Setup",
                    value="1. Get your ClickUp API token from [ClickUp Settings](https://app.clickup.com/settings/apps)\n"
                          "2. Run `/clickup-setup` and follow the prompts\n"
                          "3. Select your workspace and you're ready to go!",
                    inline=False
                )
                embed.add_field(
                    name="Need Help?",
                    value="Use `/help` for a list of all available commands.",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error checking config status: {e}")
            embed = EmbedFactory.create_error_embed(
                "Status Check Failed",
                f"Unable to check configuration status: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ConfigHealth(bot))