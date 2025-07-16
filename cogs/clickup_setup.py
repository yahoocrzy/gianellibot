import discord
from discord.ext import commands
from discord import app_commands
from utils.embed_factory import EmbedFactory
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from loguru import logger

class ClickUpSetup(commands.Cog):
    """Simple ClickUp setup command that guides users to the workspace system"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="clickup-setup", description="Set up ClickUp integration for this server")
    @app_commands.default_permissions(administrator=True)
    async def clickup_setup(self, interaction: discord.Interaction):
        """Guide users through ClickUp setup using the workspace system"""
        
        # Check if already configured
        workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        
        if workspaces:
            # Already configured - show status
            default_workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
            
            embed = EmbedFactory.create_success_embed(
                "ClickUp Already Configured",
                f"✅ ClickUp is already set up for this server!"
            )
            
            embed.add_field(
                name="Current Setup",
                value=f"**Default Workspace**: {default_workspace.workspace_name if default_workspace else 'None'}\n"
                      f"**Total Workspaces**: {len(workspaces)}\n"
                      f"**Status**: Ready to use",
                inline=False
            )
            
            embed.add_field(
                name="Available Commands",
                value="• `/task-create` - Create new tasks\n"
                      "• `/task-list` - View and manage tasks\n"
                      "• `/calendar` - View tasks in calendar\n"
                      "• `/workspace-list` - Manage workspaces",
                inline=False
            )
            
            embed.add_field(
                name="Need Help?",
                value="• `/help` - Full command list\n"
                      "• `/config-status` - Check configuration health\n"
                      "• `/workspace-add` - Add more workspaces",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        else:
            # Not configured - show setup guide
            embed = EmbedFactory.create_info_embed(
                "🚀 ClickUp Setup Guide",
                "Let's get ClickUp integrated with your Discord server!"
            )
            
            embed.add_field(
                name="Step 1: Get Your ClickUp API Token",
                value="1. Go to [ClickUp Settings](https://app.clickup.com/settings/apps)\n"
                      "2. Click on **API** in the left sidebar\n"
                      "3. Click **Generate** to create a new API token\n"
                      "4. Copy the token (starts with `pk_`)",
                inline=False
            )
            
            embed.add_field(
                name="Step 2: Add Your Workspace",
                value="Run `/workspace-add` and paste your API token when prompted.\n"
                      "The bot will automatically detect your ClickUp workspaces.",
                inline=False
            )
            
            embed.add_field(
                name="Step 3: Start Using ClickUp",
                value="• `/task-create` - Create your first task\n"
                      "• `/calendar` - View tasks in calendar\n"
                      "• `/help` - See all available commands",
                inline=False
            )
            
            embed.add_field(
                name="Need Help?",
                value="• **Token Issues**: Make sure your token starts with `pk_`\n"
                      "• **Permissions**: You need ClickUp workspace admin access\n"
                      "• **Support**: Use `/config-status` to check configuration",
                inline=False
            )
            
            # Add a quick setup button
            class QuickSetupView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=300)
                
                @discord.ui.button(label="Start Setup", style=discord.ButtonStyle.success, emoji="🚀")
                async def start_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
                    embed = EmbedFactory.create_info_embed(
                        "Quick Setup",
                        "Perfect! Now run `/workspace-add` to add your ClickUp workspace.\n\n"
                        "💡 **Tip**: Have your ClickUp API token ready (from ClickUp Settings → API)"
                    )
                    await interaction.response.edit_message(embed=embed, view=None)
                
                @discord.ui.button(label="Check Status", style=discord.ButtonStyle.secondary, emoji="🔍")
                async def check_status(self, interaction: discord.Interaction, button: discord.ui.Button):
                    # Run config status check
                    from utils.unified_config import UnifiedConfigManager
                    
                    status = await UnifiedConfigManager.get_configuration_status(interaction.guild_id)
                    
                    if status["recommendation"] == "setup_required":
                        embed = EmbedFactory.create_info_embed(
                            "Configuration Status",
                            "❌ **Not Configured**\n\n"
                            "No ClickUp workspaces found. Use `/workspace-add` to get started."
                        )
                    else:
                        embed = EmbedFactory.create_success_embed(
                            "Configuration Status",
                            "✅ **Configured**\n\n"
                            "ClickUp integration is working properly."
                        )
                    
                    await interaction.response.edit_message(embed=embed, view=None)
            
            await interaction.response.send_message(embed=embed, view=QuickSetupView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(ClickUpSetup(bot))