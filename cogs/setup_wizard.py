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

class ChannelSelectModal(discord.ui.Modal, title="Select Notification Channel"):
    def __init__(self, setup_view):
        super().__init__()
        self.setup_view = setup_view
    
    channel_mention = discord.ui.TextInput(
        label="Channel for ClickUp Notifications",
        placeholder="#general or channel ID (optional)",
        style=discord.TextStyle.short,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        notification_channel_id = None
        
        if self.channel_mention.value.strip():
            channel_input = self.channel_mention.value.strip()
            
            # Parse channel mention or ID
            channel = None
            if channel_input.startswith('<#') and channel_input.endswith('>'):
                # Channel mention
                channel_id = int(channel_input[2:-1])
                channel = interaction.guild.get_channel(channel_id)
            elif channel_input.startswith('#'):
                # Channel name
                channel_name = channel_input[1:]
                channel = discord.utils.get(interaction.guild.channels, name=channel_name)
            else:
                # Try as channel ID
                try:
                    channel_id = int(channel_input)
                    channel = interaction.guild.get_channel(channel_id)
                except ValueError:
                    pass
            
            if not channel:
                await interaction.response.send_message(
                    "❌ Could not find that channel. Setup will continue without notification channel.",
                    ephemeral=True
                )
            elif not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message(
                    "❌ Please select a text channel. Setup will continue without notification channel.",
                    ephemeral=True
                )
            else:
                notification_channel_id = channel.id
                self.setup_view.config['notification_channel_id'] = notification_channel_id
        
        # Complete setup
        await self._complete_setup(interaction, notification_channel_id)
    
    async def _complete_setup(self, interaction: discord.Interaction, notification_channel_id: Optional[int]):
        # Save configuration
        repo = ServerConfigRepository()
        
        config_data = {
            'encrypted_token': self.setup_view.config['clickup_token'],
            'workspace_id': self.setup_view.config['workspace_id'],
            'setup_complete': True
        }
        
        if notification_channel_id:
            config_data['notification_channel_id'] = notification_channel_id
        
        await repo.save_config(interaction.guild_id, **config_data)
        
        # Create completion message
        channel_text = ""
        if notification_channel_id:
            channel = interaction.guild.get_channel(notification_channel_id)
            channel_text = f"\n**Notification Channel:** {channel.mention if channel else f'<#{notification_channel_id}>'}"
        
        embed = EmbedFactory.create_success_embed(
            "Setup Complete! 🎉",
            f"Your ClickUp integration is now configured.{channel_text}\n\n"
            "**Available Commands:**\n"
            "• `/select-list` - Browse and select ClickUp lists with dropdowns\n"
            "• `/task-create` - Create a new ClickUp task\n"
            "• `/task-list` - List tasks from a ClickUp list\n"
            "• `/task-update` - Update an existing task\n"
            "• `/task-delete` - Delete a task (with confirmation)\n"
            "• `/task-comment` - Add comments to tasks\n"
            "• `/task-assign` - Assign users to tasks\n\n"
            "**AI-Powered Commands:**\n"
            "• `/ai-create-task` - Create tasks using natural language\n"
            "• `/ai-analyze-tasks` - Get AI analysis and suggestions\n"
            "• `/ai-task-suggestions` - Get AI suggestions for specific tasks\n\n"
            "**Other Features:**\n"
            "• `/reaction-roles-setup` - Set up reaction roles with channel selection\n\n"
            "**Getting Started:**\n"
            "• Use `/select-list` to browse your ClickUp hierarchy and get list IDs\n"
            "• Then use `/task-create` with the list ID to create your first task\n"
            "• Try `/ai-create-task` for natural language task creation!"
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

class FinalSetupView(discord.ui.View):
    def __init__(self, setup_view):
        super().__init__(timeout=180)
        self.setup_view = setup_view
    
    @discord.ui.button(label="Complete Setup", style=discord.ButtonStyle.success)
    async def complete_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Show channel selection modal
        modal = ChannelSelectModal(self.setup_view)
        await interaction.response.send_modal(modal)
        # This method is no longer used as setup completion is handled in ChannelSelectModal
        pass

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