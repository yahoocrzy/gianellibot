import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Union, Literal
from datetime import datetime, timedelta
from utils.embed_factory import EmbedFactory
from loguru import logger

class PurgeConfirmView(discord.ui.View):
    def __init__(self, purge_data: dict, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.purge_data = purge_data
        self.confirmed = False
    
    @discord.ui.button(label="Confirm Purge", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_purge(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Prevent multiple clicks
        if hasattr(self, '_responded'):
            return
            
        self._responded = True
        self.confirmed = True
        self.stop()
        
        # Perform the actual purge
        await interaction.response.edit_message(content="🗑️ Purging messages...", embed=None, view=None)
        
        try:
            deleted_messages = await self.purge_data['channel'].purge(
                limit=self.purge_data['amount'],
                check=self.purge_data.get('check'),
                before=self.purge_data.get('before'),
                after=self.purge_data.get('after'),
                around=self.purge_data.get('around'),
                oldest_first=self.purge_data.get('oldest_first', False),
                bulk=True
            )
            
            # Create success embed
            embed = EmbedFactory.create_success_embed(
                "Messages Purged Successfully",
                f"✅ Deleted **{len(deleted_messages)}** messages from {self.purge_data['channel'].mention}"
            )
            
            embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Channel", value=self.purge_data['channel'].mention, inline=True)
            embed.add_field(name="Timestamp", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=False)
            
            # Add filter information if applicable
            if self.purge_data.get('user'):
                embed.add_field(name="User Filter", value=self.purge_data['user'].mention, inline=True)
            if self.purge_data.get('contains'):
                embed.add_field(name="Content Filter", value=f"`{self.purge_data['contains']}`", inline=True)
            
            await interaction.edit_original_response(embed=embed)
            
            # Log the action
            logger.info(f"Purged {len(deleted_messages)} messages from {self.purge_data['channel'].name} by {interaction.user}")
            
        except discord.Forbidden:
            embed = EmbedFactory.create_error_embed(
                "Permission Error",
                "❌ I don't have permission to delete messages in this channel."
            )
            await interaction.edit_original_response(embed=embed)
        except discord.HTTPException as e:
            embed = EmbedFactory.create_error_embed(
                "Purge Failed",
                f"❌ Failed to purge messages: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_purge(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Prevent multiple clicks
        if hasattr(self, '_responded'):
            return
            
        self._responded = True
        self.confirmed = False
        self.stop()
        
        embed = EmbedFactory.create_info_embed(
            "Purge Cancelled",
            "❌ Message purge has been cancelled."
        )
        await interaction.response.edit_message(embed=embed, view=None)

class Moderation(commands.Cog):
    """Moderation commands for server management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="purge", description="Delete multiple messages from a channel")
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        user="Only delete messages from this user",
        contains="Only delete messages containing this text",
        channel="Channel to purge from (default: current channel)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
        user: Optional[discord.Member] = None,
        contains: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None
    ):
        """Purge messages with various filters and safety confirmations"""
        
        # Use current channel if none specified
        target_channel = channel or interaction.channel
        
        # Check if bot has required permissions
        bot_permissions = target_channel.permissions_for(interaction.guild.me)
        if not bot_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ I don't have permission to manage messages in that channel.",
                ephemeral=True
            )
            return
        
        if not bot_permissions.read_message_history:
            await interaction.response.send_message(
                "❌ I don't have permission to read message history in that channel.",
                ephemeral=True
            )
            return
        
        # Check if user has required permissions
        user_permissions = target_channel.permissions_for(interaction.user)
        if not user_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You don't have permission to manage messages in that channel.",
                ephemeral=True
            )
            return
        
        # Build check function for filtering
        def check(message):
            # Skip pinned messages
            if message.pinned:
                return False
            
            # User filter
            if user and message.author != user:
                return False
            
            # Content filter
            if contains and contains.lower() not in message.content.lower():
                return False
            
            # Don't delete messages older than 14 days (Discord limitation)
            if datetime.utcnow() - message.created_at > timedelta(days=14):
                return False
            
            return True
        
        # Prepare purge data
        purge_data = {
            'channel': target_channel,
            'amount': amount,
            'check': check if (user or contains) else None,
            'user': user,
            'contains': contains
        }
        
        # Create confirmation embed
        embed = EmbedFactory.create_warning_embed(
            "Confirm Message Purge",
            f"⚠️ You are about to delete up to **{amount}** messages from {target_channel.mention}"
        )
        
        # Add filter information
        filters = []
        if user:
            filters.append(f"👤 **User:** {user.mention}")
        if contains:
            filters.append(f"💬 **Contains:** `{contains}`")
        if not filters:
            filters.append("🔄 **No filters** - All recent messages")
        
        embed.add_field(name="Filters Applied", value="\n".join(filters), inline=False)
        embed.add_field(name="⚠️ Warning", value="This action cannot be undone!", inline=False)
        embed.set_footer(text="You have 60 seconds to confirm or cancel this action.")
        
        # Show confirmation dialog
        if amount >= 10:  # Show confirmation for 10+ messages
            view = PurgeConfirmView(purge_data)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            # Wait for confirmation with timeout
            timed_out = await view.wait()
            
            if timed_out or not view.confirmed:
                # User didn't confirm or timed out
                timeout_embed = EmbedFactory.create_info_embed(
                    "Purge Cancelled" if not timed_out else "Purge Timed Out",
                    "❌ Purge cancelled. No messages were deleted." if not timed_out else "❌ Purge confirmation timed out. No messages were deleted."
                )
                try:
                    await interaction.edit_original_response(embed=timeout_embed, view=None)
                except discord.NotFound:
                    # Message was already edited/deleted
                    pass
        else:
            # For small amounts, purge immediately
            await interaction.response.defer(ephemeral=True)
            
            try:
                deleted_messages = await target_channel.purge(
                    limit=amount,
                    check=check if (user or contains) else None,
                    bulk=True
                )
                
                embed = EmbedFactory.create_success_embed(
                    "Messages Purged",
                    f"✅ Deleted **{len(deleted_messages)}** messages from {target_channel.mention}"
                )
                
                embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
                if user:
                    embed.add_field(name="User Filter", value=user.mention, inline=True)
                if contains:
                    embed.add_field(name="Content Filter", value=f"`{contains}`", inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                logger.info(f"Purged {len(deleted_messages)} messages from {target_channel.name} by {interaction.user}")
                
            except discord.Forbidden:
                embed = EmbedFactory.create_error_embed(
                    "Permission Error",
                    "❌ I don't have permission to delete messages in this channel."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            except discord.HTTPException as e:
                embed = EmbedFactory.create_error_embed(
                    "Purge Failed",
                    f"❌ Failed to purge messages: {str(e)}"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="purge-user", description="Delete all recent messages from a specific user")
    @app_commands.describe(
        user="User whose messages to delete",
        amount="Number of messages to check (1-100, default: 50)",
        channel="Channel to purge from (default: current channel)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def purge_user(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 100] = 50,
        channel: Optional[discord.TextChannel] = None
    ):
        """Convenient command to purge messages from a specific user"""
        
        # Call the main purge command with user filter
        await self.purge(interaction, amount, user=user, channel=channel)
    
    @app_commands.command(name="purge-bots", description="Delete all recent messages from bots")
    @app_commands.describe(
        amount="Number of messages to check (1-100, default: 50)",
        channel="Channel to purge from (default: current channel)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def purge_bots(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100] = 50,
        channel: Optional[discord.TextChannel] = None
    ):
        """Delete all recent bot messages"""
        
        target_channel = channel or interaction.channel
        
        # Check permissions
        bot_permissions = target_channel.permissions_for(interaction.guild.me)
        if not bot_permissions.manage_messages or not bot_permissions.read_message_history:
            await interaction.response.send_message(
                "❌ I don't have permission to manage messages in that channel.",
                ephemeral=True
            )
            return
        
        user_permissions = target_channel.permissions_for(interaction.user)
        if not user_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You don't have permission to manage messages in that channel.",
                ephemeral=True
            )
            return
        
        def bot_check(message):
            return message.author.bot and not message.pinned and \
                   datetime.utcnow() - message.created_at < timedelta(days=14)
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            deleted_messages = await target_channel.purge(
                limit=amount,
                check=bot_check,
                bulk=True
            )
            
            embed = EmbedFactory.create_success_embed(
                "Bot Messages Purged",
                f"✅ Deleted **{len(deleted_messages)}** bot messages from {target_channel.mention}"
            )
            embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Messages Checked", value=str(amount), inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            logger.info(f"Purged {len(deleted_messages)} bot messages from {target_channel.name} by {interaction.user}")
            
        except Exception as e:
            embed = EmbedFactory.create_error_embed(
                "Purge Failed",
                f"❌ Failed to purge bot messages: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="clear-channel", description="Delete ALL messages in a channel (DANGEROUS)")
    @app_commands.describe(
        channel="Channel to completely clear (default: current channel)",
        confirm_text="Type 'DELETE ALL' to confirm this dangerous action"
    )
    @app_commands.default_permissions(administrator=True)
    async def clear_channel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        confirm_text: str = ""
    ):
        """Completely clear a channel - requires admin permissions and confirmation"""
        
        target_channel = channel or interaction.channel
        
        # Require exact confirmation text
        if confirm_text != "DELETE ALL":
            embed = EmbedFactory.create_warning_embed(
                "Confirmation Required",
                f"⚠️ To clear **ALL** messages from {target_channel.mention}, "
                "you must type exactly `DELETE ALL` in the confirm_text parameter.\n\n"
                "**This will delete EVERY message in the channel!**"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check permissions
        bot_permissions = target_channel.permissions_for(interaction.guild.me)
        if not bot_permissions.manage_messages or not bot_permissions.read_message_history:
            await interaction.response.send_message(
                "❌ I don't have permission to manage messages in that channel.",
                ephemeral=True
            )
            return
        
        embed = EmbedFactory.create_warning_embed(
            "Confirm Channel Clearing",
            f"🚨 **DANGER**: You are about to delete **ALL** messages from {target_channel.mention}\n\n"
            "This action is **IRREVERSIBLE** and will delete:\n"
            "• All message history\n"
            "• All attachments\n"
            "• All embeds\n"
            "• Everything in the channel"
        )
        embed.set_footer(text="This action requires administrator permissions and cannot be undone!")
        
        # Create a special confirmation view for this dangerous action
        class ClearChannelView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.confirmed = False
            
            @discord.ui.button(label="YES, DELETE EVERYTHING", style=discord.ButtonStyle.danger)
            async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.confirmed = True
                self.stop()
                
                await interaction.response.edit_message(
                    content="🗑️ Clearing channel... This may take a while...",
                    embed=None,
                    view=None
                )
                
                try:
                    # Delete messages in batches
                    deleted_count = 0
                    while True:
                        messages = []
                        async for message in target_channel.history(limit=100):
                            if datetime.utcnow() - message.created_at < timedelta(days=14):
                                messages.append(message)
                        
                        if not messages:
                            break
                        
                        await target_channel.delete_messages(messages)
                        deleted_count += len(messages)
                        
                        if len(messages) < 100:
                            break
                    
                    # Handle old messages (>14 days) individually
                    old_messages = []
                    async for message in target_channel.history(limit=None):
                        old_messages.append(message)
                    
                    for message in old_messages:
                        try:
                            await message.delete()
                            deleted_count += 1
                        except:
                            continue
                    
                    success_embed = EmbedFactory.create_success_embed(
                        "Channel Cleared",
                        f"✅ Successfully cleared {target_channel.mention}\n"
                        f"**Total messages deleted:** {deleted_count}"
                    )
                    success_embed.add_field(name="Cleared by", value=interaction.user.mention, inline=True)
                    success_embed.add_field(name="Timestamp", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=True)
                    
                    await interaction.edit_original_response(embed=success_embed)
                    
                    logger.warning(f"CHANNEL CLEARED: {target_channel.name} by {interaction.user} - {deleted_count} messages deleted")
                    
                except Exception as e:
                    error_embed = EmbedFactory.create_error_embed(
                        "Clear Failed",
                        f"❌ Failed to clear channel: {str(e)}"
                    )
                    await interaction.edit_original_response(embed=error_embed)
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.confirmed = False
                self.stop()
                
                cancel_embed = EmbedFactory.create_info_embed(
                    "Channel Clear Cancelled",
                    "❌ Channel clearing has been cancelled. No messages were deleted."
                )
                await interaction.response.edit_message(embed=cancel_embed, view=None)
        
        view = ClearChannelView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))