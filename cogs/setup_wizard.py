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
            "• `/select-list` - Browse and select ClickUp lists with dropdowns\n"
            "• `/task-create` - Create a new ClickUp task\n"
            "• `/task-list` - List tasks from a ClickUp list\n"
            "• `/task-update` - Update an existing task\n"
            "• `/task-delete` - Delete a task (with confirmation)\n"
            "• `/task-comment` - Add comments to tasks\n"
            "• `/task-assign` - Assign users to tasks\n\n"
            "**Getting Started:**\n"
            "• Use `/select-list` to browse your ClickUp hierarchy and get list IDs\n"
            "• Then use `/task-create` with the list ID to create your first task\n"
            "• All commands use modern Discord slash command interface with interactive dropdowns"
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

class SetupWizard(commands.Cog):
    """Interactive setup wizard for the bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="clickup-setup", description="Start the ClickUp bot setup wizard")
    @app_commands.describe()
    @app_commands.default_permissions(administrator=True)
    async def clickup_setup(self, interaction: discord.Interaction):
        """Start interactive setup wizard"""
        embed = EmbedFactory.create_info_embed(
            "ClickUp Bot Setup Wizard",
            "Welcome! Let's set up your ClickUp integration.\n\n"
            "**What you'll need:**\n"
            "• Your ClickUp API token\n"
            "• Administrator permissions\n\n"
            "Ready to begin?"
        )
        
        view = SetupStartView(self.bot, interaction)
        await interaction.response.send_message(embed=embed, view=view)

class SetupStartView(discord.ui.View):
    def __init__(self, bot, interaction):
        super().__init__(timeout=180)
        self.bot = bot
        self.interaction = interaction
    
    @discord.ui.button(label="Start Setup", style=discord.ButtonStyle.primary)
    async def start_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check existing config
        repo = ServerConfigRepository()
        config = await repo.get_config(interaction.guild_id)
        
        if config and config.get('setup_complete'):
            view = ReconfigureView(self.bot, self.interaction)
            embed = EmbedFactory.create_warning_embed(
                "Existing Configuration Found",
                "This server already has a ClickUp configuration.\n"
                "Would you like to reconfigure?"
            )
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            # Start fresh setup
            await interaction.response.send_modal(APITokenModal(SetupView(self.bot, self.interaction)))
    
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