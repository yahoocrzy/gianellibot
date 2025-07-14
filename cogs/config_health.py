import discord
from discord.ext import commands
from discord import app_commands
from utils.unified_config import UnifiedConfigManager
from utils.embed_factory import EmbedFactory
from loguru import logger

class ConfigHealth(commands.Cog):
    """Configuration health check and migration utilities"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="config-status", description="Check ClickUp configuration status")
    @app_commands.default_permissions(administrator=True)
    async def config_status(self, interaction: discord.Interaction):
        """Check the health of ClickUp configuration"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            status = await UnifiedConfigManager.get_configuration_status(interaction.guild_id)
            
            if status["recommendation"] == "all_good":
                embed = EmbedFactory.create_success_embed(
                    "✅ Configuration Healthy",
                    "ClickUp is properly configured and working!"
                )
                embed.add_field(
                    name="Current Setup",
                    value=f"• **Active System**: New multi-workspace system\n"
                          f"• **Default Workspace**: {status['default_workspace']['name']}\n"
                          f"• **Workspace ID**: `{status['default_workspace']['id']}`\n"
                          f"• **API Status**: ✅ Working",
                    inline=False
                )
                
            elif status["recommendation"] == "migrate_recommended":
                embed = EmbedFactory.create_warning_embed(
                    "⚠️ Migration Recommended",
                    "You're using the legacy configuration system. Migration is recommended for better features."
                )
                embed.add_field(
                    name="Current Setup",
                    value=f"• **Active System**: Legacy single-workspace system\n"
                          f"• **Workspace ID**: `{status.get('legacy_workspace_id', 'Unknown')}`\n"
                          f"• **API Status**: ✅ Working",
                    inline=False
                )
                embed.add_field(
                    name="Migration Benefits",
                    value="• Support for multiple workspaces\n"
                          "• Better workspace management\n"
                          "• Improved reliability\n"
                          "• Future-proof configuration",
                    inline=False
                )
                
                class MigrationView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=60)
                    
                    @discord.ui.button(label="Migrate Now", style=discord.ButtonStyle.success)
                    async def migrate(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                        await button_interaction.response.defer()
                        
                        success = await UnifiedConfigManager.migrate_legacy_to_new(
                            interaction.guild_id, 
                            interaction.user.id
                        )
                        
                        if success:
                            embed = EmbedFactory.create_success_embed(
                                "Migration Successful!",
                                "✅ Successfully migrated to the new workspace system!"
                            )
                            embed.add_field(
                                name="What's New",
                                value="• You can now use `/workspace-add` to add more workspaces\n"
                                      "• Use `/workspace-switch` to change between workspaces\n"
                                      "• All commands now work with the new system",
                                inline=False
                            )
                        else:
                            embed = EmbedFactory.create_error_embed(
                                "Migration Failed",
                                "❌ Migration failed. Please try manually adding workspace with `/workspace-add`."
                            )
                        
                        await button_interaction.edit_original_response(embed=embed, view=None)
                
                await interaction.followup.send(embed=embed, view=MigrationView(), ephemeral=True)
                return
                
            elif status["recommendation"] == "token_invalid":
                embed = EmbedFactory.create_error_embed(
                    "❌ Invalid Token",
                    "ClickUp configuration exists but the API token is invalid or expired."
                )
                embed.add_field(
                    name="What You Have",
                    value=f"• **New System**: {'✅' if status['has_new_system'] else '❌'}\n"
                          f"• **Legacy System**: {'✅' if status['has_legacy_system'] else '❌'}\n"
                          f"• **API Status**: ❌ Not working",
                    inline=False
                )
                embed.add_field(
                    name="How to Fix",
                    value="1. Get a new API token from [ClickUp Settings](https://app.clickup.com/settings/apps)\n"
                          "2. Run `/workspace-add` to add it again\n"
                          "3. Or contact an administrator to fix the configuration",
                    inline=False
                )
                
            else:  # setup_required
                embed = EmbedFactory.create_info_embed(
                    "🔧 Setup Required",
                    "ClickUp hasn't been configured for this server yet."
                )
                embed.add_field(
                    name="Getting Started",
                    value="1. Get your ClickUp API token from [ClickUp Settings](https://app.clickup.com/settings/apps)\n"
                          "2. Run `/workspace-add` and paste your token\n"
                          "3. Select which workspace to use\n"
                          "4. Start using commands like `/calendar` and `/task-create`",
                    inline=False
                )
                
                embed.add_field(
                    name="Available Commands After Setup",
                    value="• `/calendar` - View tasks in calendar format\n"
                          "• `/task-create` - Create new tasks\n"
                          "• `/task-list` - List tasks\n"
                          "• `/workspace-switch` - Switch between workspaces",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in config status: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error",
                f"Failed to check configuration status: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="migrate-config", description="Migrate from legacy to new workspace system")
    @app_commands.default_permissions(administrator=True)
    async def migrate_config(self, interaction: discord.Interaction):
        """Manually migrate from legacy to new workspace system"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            success = await UnifiedConfigManager.migrate_legacy_to_new(
                interaction.guild_id, 
                interaction.user.id
            )
            
            if success:
                embed = EmbedFactory.create_success_embed(
                    "Migration Successful!",
                    "✅ Successfully migrated to the new workspace system!"
                )
                embed.add_field(
                    name="What's New",
                    value="• You can now use `/workspace-add` to add more workspaces\n"
                          "• Use `/workspace-switch` to change between workspaces\n"
                          "• All commands now work with the new system\n"
                          "• Better reliability and features",
                    inline=False
                )
                embed.add_field(
                    name="Next Steps",
                    value="• Try `/workspace-list` to see your configured workspaces\n"
                          "• Use `/calendar` to test that everything works\n"
                          "• Add more workspaces with `/workspace-add` if needed",
                    inline=False
                )
            else:
                embed = EmbedFactory.create_error_embed(
                    "Migration Failed",
                    "❌ Migration failed. This might be because:\n"
                    "• No legacy configuration exists\n"
                    "• API token is invalid\n"
                    "• You already have the new system"
                )
                embed.add_field(
                    name="Alternative",
                    value="Try manually adding your workspace with `/workspace-add`",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in config migration: {e}")
            embed = EmbedFactory.create_error_embed(
                "Migration Error",
                f"Failed to migrate configuration: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ConfigHealth(bot))