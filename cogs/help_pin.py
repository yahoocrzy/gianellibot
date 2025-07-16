import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.embed_factory import EmbedFactory
from repositories.server_config import ServerConfigRepository
from repositories.clickup_oauth_workspaces import ClickUpOAuthWorkspaceRepository
from repositories.claude_config import ClaudeConfigRepository
from loguru import logger

class HelpPin(commands.Cog):
    """Commands for pinning help messages"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="setup-help-pin", description="Pin a help message in a channel")
    @app_commands.default_permissions(administrator=True)
    async def setup_help_pin(self, interaction: discord.Interaction):
        """Set up a pinned help message"""
        
        # Channel selection dropdown
        embed = EmbedFactory.create_info_embed(
            "📌 Setup Help Pin",
            "Select a channel where you'd like to pin the help message:"
        )
        
        class ChannelSelectView(discord.ui.View):
            def __init__(self, guild: discord.Guild):
                super().__init__(timeout=180)
                self.selected_channel = None
                
                # Get text channels
                channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages]
                
                # Create channel dropdown
                options = []
                for channel in channels[:25]:  # Discord limit
                    options.append(
                        discord.SelectOption(
                            label=channel.name,
                            value=str(channel.id),
                            description=f"Category: {channel.category.name if channel.category else 'None'}"
                        )
                    )
                
                channel_select = discord.ui.Select(
                    placeholder="Choose a channel...",
                    options=options
                )
                channel_select.callback = self.channel_callback
                self.add_item(channel_select)
            
            async def channel_callback(self, interaction: discord.Interaction):
                self.selected_channel = int(interaction.data['values'][0])
                self.stop()
                await interaction.response.defer()
        
        view = ChannelSelectView(interaction.guild)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        await view.wait()
        
        if not view.selected_channel:
            return
        
        # Get the channel
        channel = interaction.guild.get_channel(view.selected_channel)
        if not channel:
            embed = EmbedFactory.create_error_embed(
                "Channel Not Found",
                "The selected channel could not be found."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Create comprehensive help embed
        help_embed = await self._create_help_embed(interaction.guild_id)
        
        # Create interactive help view
        help_view = InteractiveHelpView(self.bot)
        
        try:
            # Send and pin the message
            message = await channel.send(embed=help_embed, view=help_view)
            await message.pin()
            
            # Save pin info to database
            repo = ServerConfigRepository()
            await repo.update_config(
                interaction.guild_id,
                help_pin_channel_id=channel.id,
                help_pin_message_id=message.id
            )
            
            # Success message
            success_embed = EmbedFactory.create_success_embed(
                "✅ Help Message Pinned",
                f"Successfully pinned help message in {channel.mention}\n\n"
                f"[Jump to message]({message.jump_url})"
            )
            
            await interaction.edit_original_response(embed=success_embed, view=None)
            
        except discord.Forbidden:
            embed = EmbedFactory.create_error_embed(
                "Permission Error",
                "I don't have permission to send messages or pin in that channel."
            )
            await interaction.edit_original_response(embed=embed, view=None)
        except Exception as e:
            logger.error(f"Error pinning help message: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error",
                f"Failed to pin help message: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed, view=None)
    
    @app_commands.command(name="update-help-pin", description="Update the pinned help message")
    @app_commands.default_permissions(administrator=True)
    async def update_help_pin(self, interaction: discord.Interaction):
        """Update existing pinned help message"""
        
        # Get pin info from database
        repo = ServerConfigRepository()
        config = await repo.get_config(interaction.guild_id)
        
        if not config or not config.get('help_pin_message_id'):
            embed = EmbedFactory.create_error_embed(
                "No Pin Found",
                "No help pin has been set up yet. Use `/setup-help-pin` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Find the message
        channel = interaction.guild.get_channel(config['help_pin_channel_id'])
        if not channel:
            embed = EmbedFactory.create_error_embed(
                "Channel Not Found",
                "The help pin channel no longer exists."
            )
            await interaction.followup.send(embed=embed)
            return
        
        try:
            message = await channel.fetch_message(config['help_pin_message_id'])
            
            # Update with new embed
            help_embed = await self._create_help_embed(interaction.guild_id)
            help_view = InteractiveHelpView(self.bot)
            
            await message.edit(embed=help_embed, view=help_view)
            
            embed = EmbedFactory.create_success_embed(
                "✅ Help Pin Updated",
                f"Successfully updated the help message in {channel.mention}\n\n"
                f"[Jump to message]({message.jump_url})"
            )
            await interaction.followup.send(embed=embed)
            
        except discord.NotFound:
            embed = EmbedFactory.create_error_embed(
                "Message Not Found",
                "The pinned help message was deleted. Use `/setup-help-pin` to create a new one."
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error updating help pin: {e}")
            embed = EmbedFactory.create_error_embed(
                "Update Failed",
                f"Failed to update help message: {str(e)}"
            )
            await interaction.followup.send(embed=embed)
    
    async def _create_help_embed(self, guild_id: int) -> discord.Embed:
        """Create comprehensive help embed"""
        
        # Check configuration status
        workspaces = await ClickUpOAuthWorkspaceRepository.get_all_workspaces(guild_id)
        claude_config = await ClaudeConfigRepository.get_config(guild_id)
        
        # Create main embed
        embed = discord.Embed(
            title="🤖 ClickBot Command Center",
            description=(
                "Welcome to ClickBot - Your all-in-one ClickUp integration!\n\n"
                "**All commands use interactive dropdowns - no typing required!**\n"
                "Click the buttons below to explore different features."
            ),
            color=discord.Color.blue()
        )
        
        # Quick status
        clickup_status = "✅ Configured" if workspaces else "❌ Not configured"
        ai_status = "✅ Enabled" if claude_config else "❌ Not configured"
        
        embed.add_field(
            name="📊 System Status",
            value=f"**ClickUp:** {clickup_status}\n**AI Assistant:** {ai_status}",
            inline=False
        )
        
        # Getting started
        if not workspaces:
            embed.add_field(
                name="🚀 Quick Start",
                value=(
                    "1️⃣ Run `/clickup-setup` to connect ClickUp\n"
                    "2️⃣ Run `/claude-setup` to enable AI features\n"
                    "3️⃣ Start using `/task-create` to manage tasks!"
                ),
                inline=False
            )
        
        # Command categories preview
        embed.add_field(
            name="📋 Task Management",
            value="Create, update, list, and delete tasks",
            inline=True
        )
        
        embed.add_field(
            name="📅 Calendar & Planning",
            value="View tasks in calendar, check due dates",
            inline=True
        )
        
        embed.add_field(
            name="🤖 AI Assistant",
            value="Natural language task management",
            inline=True
        )
        
        embed.add_field(
            name="🏢 Workspaces",
            value="Manage multiple ClickUp workspaces",
            inline=True
        )
        
        embed.add_field(
            name="🎭 Reaction Roles",
            value="Auto-assign roles with reactions",
            inline=True
        )
        
        embed.add_field(
            name="🛡️ Moderation",
            value="Advanced message management",
            inline=True
        )
        
        # Tips
        embed.add_field(
            name="💡 Pro Tips",
            value=(
                "• All commands use dropdowns - no IDs to type!\n"
                "• Support for multiple workspaces\n"
                "• AI understands natural language\n"
                "• Calendar view for better planning\n"
                "• Secure encrypted token storage"
            ),
            inline=False
        )
        
        embed.set_footer(text="Click the buttons below to explore commands by category")
        embed.timestamp = discord.utils.utcnow()
        
        return embed


class InteractiveHelpView(discord.ui.View):
    """Interactive buttons for help categories"""
    
    def __init__(self, bot):
        super().__init__(timeout=None)  # Persistent view
        self.bot = bot
    
    @discord.ui.button(label="Task Management", style=discord.ButtonStyle.primary, emoji="📋", custom_id="help_tasks")
    async def task_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show task management commands"""
        embed = EmbedFactory.create_info_embed(
            "📋 Task Management Commands",
            "All commands use interactive dropdowns!"
        )
        
        commands = [
            ("**/task-create**", "Create a new task with full dropdown selections"),
            ("**/task-update**", "Update existing tasks interactively"),
            ("**/task-list**", "View tasks with filtering options"),
            ("**/task-delete**", "Delete tasks with confirmation"),
            ("**/task-comment**", "Add comments to tasks"),
            ("**/task-assign**", "Assign tasks to team members")
        ]
        
        for cmd, desc in commands:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Calendar", style=discord.ButtonStyle.primary, emoji="📅", custom_id="help_calendar")
    async def calendar_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show calendar commands"""
        embed = EmbedFactory.create_info_embed(
            "📅 Calendar & Planning Commands",
            "View and manage tasks by date!"
        )
        
        commands = [
            ("**/calendar**", "Interactive monthly calendar view"),
            ("**/upcoming**", "See tasks for the next N days"),
            ("**/today**", "View all tasks due today"),
            ("**/overdue**", "List all overdue tasks")
        ]
        
        for cmd, desc in commands:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="AI Assistant", style=discord.ButtonStyle.primary, emoji="🤖", custom_id="help_ai")
    async def ai_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show AI commands"""
        embed = EmbedFactory.create_info_embed(
            "🤖 AI Assistant Commands",
            "Powerful AI features for task management!"
        )
        
        commands = [
            ("**/ai**", "AI assistant with dropdown action selection"),
            ("**/ai-chat**", "Start conversational AI mode"),
            ("**/ai-analyze-tasks**", "Get AI insights on your tasks"),
            ("**/claude-setup**", "Configure Claude AI"),
            ("**/claude-settings**", "Adjust AI model settings")
        ]
        
        for cmd, desc in commands:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        embed.add_field(
            name="🎯 AI Capabilities",
            value=(
                "• Create tasks from natural language\n"
                "• Analyze task priorities and workload\n"
                "• Generate reports and summaries\n"
                "• Smart task filtering and search\n"
                "• Bulk operations on multiple tasks"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Workspaces", style=discord.ButtonStyle.primary, emoji="🏢", custom_id="help_workspace")
    async def workspace_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show workspace commands"""
        embed = EmbedFactory.create_info_embed(
            "🏢 Workspace Management",
            "Manage multiple ClickUp workspaces!"
        )
        
        commands = [
            ("**/clickup-setup**", "Complete ClickUp setup and configuration"),
            ("**/workspace-add**", "Add additional ClickUp workspaces"),
            ("**/workspace-list**", "View all configured workspaces"),
            ("**/workspace-switch**", "Change default workspace"),
            ("**/workspace-remove**", "Remove a workspace")
        ]
        
        for cmd, desc in commands:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="More Features", style=discord.ButtonStyle.secondary, emoji="➕", custom_id="help_more")
    async def more_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show additional features"""
        embed = EmbedFactory.create_info_embed(
            "➕ Additional Features",
            "More powerful features!"
        )
        
        embed.add_field(
            name="🎭 Reaction Roles",
            value=(
                "**/reaction-roles-setup** - Create reaction role messages\n"
                "**/reaction-roles-list** - View all reaction roles"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Moderation",
            value=(
                "**/purge** - Delete messages with filters\n"
                "**/purge-user** - Delete messages from specific user\n"
                "**/purge-bots** - Clean up bot messages\n"
                "**/clear-channel** - Clear entire channel (admin)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📌 Help & Setup",
            value=(
                "**/help** - Show help information\n"
                "**/about** - Bot information\n"
                "**/setup-help-pin** - Pin this help message\n"
                "**/update-help-pin** - Update pinned help"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpPin(bot))