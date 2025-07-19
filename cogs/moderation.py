import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime
from utils.embed_factory import EmbedFactory
from loguru import logger

class ClearConfirmView(discord.ui.View):
    def __init__(self, clear_data: dict, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.clear_data = clear_data
        self.confirmed = False
    
    @discord.ui.button(label="🗑️ Confirm Clear", style=discord.ButtonStyle.danger)
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        if hasattr(self, '_responded'):
            return
            
        self._responded = True
        self.confirmed = True
        self.stop()
        
        # Show clearing progress
        await interaction.response.edit_message(content="🗑️ Clearing messages...", embed=None, view=None)
        
        try:
            channel = self.clear_data['channel']
            amount = self.clear_data['amount']
            
            if amount == "all":
                # Clear entire chat history in batches
                total_deleted = 0
                batch_size = 100
                
                while True:
                    # Get messages in batches
                    messages = [message async for message in channel.history(limit=batch_size)]
                    if not messages:
                        break
                    
                    # Delete messages (Discord bulk delete for efficiency)
                    deleted = await channel.delete_messages(messages)
                    total_deleted += len(deleted)
                    
                    # Break if we deleted fewer than batch_size (reached end)
                    if len(messages) < batch_size:
                        break
                
                result_text = f"✅ Cleared **entire chat history** ({total_deleted} messages)"
            else:
                # Clear specific amount
                deleted_messages = await channel.purge(limit=amount, bulk=True)
                total_deleted = len(deleted_messages)
                result_text = f"✅ Cleared **{total_deleted}** messages"
            
            # Create success embed
            embed = EmbedFactory.create_success_embed(
                "Chat Cleared Successfully",
                result_text + f" from {channel.mention}"
            )
            
            embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Timestamp", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=False)
            
            await interaction.edit_original_response(embed=embed)
            
            # Log the action
            logger.info(f"Cleared {total_deleted} messages from {channel.name} by {interaction.user}")
            
        except discord.Forbidden:
            embed = EmbedFactory.create_error_embed(
                "Permission Error",
                "❌ I don't have permission to delete messages in this channel."
            )
            await interaction.edit_original_response(embed=embed)
        except discord.HTTPException as e:
            embed = EmbedFactory.create_error_embed(
                "Clear Failed",
                f"❌ Failed to clear messages: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        if hasattr(self, '_responded'):
            return
            
        self._responded = True
        self.confirmed = False
        self.stop()
        
        embed = EmbedFactory.create_info_embed(
            "Clear Cancelled",
            "❌ Message clearing has been cancelled."
        )
        await interaction.response.edit_message(embed=embed, view=None)

class Moderation(commands.Cog):
    """Moderation commands for server management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="clear", description="Clear messages from a channel")
    @app_commands.describe(
        amount="Number of messages to clear (1-1000), or 'all' to clear entire chat",
        channel="Channel to clear from (default: current channel)"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: str,
        channel: Optional[discord.TextChannel] = None
    ):
        """Clear messages from a channel - supports specific amounts or entire chat"""
        
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
        
        # Parse amount parameter
        if amount.lower() == "all":
            clear_amount = "all"
            amount_text = "**entire chat history**"
            danger_level = "EXTREME"
        else:
            try:
                clear_amount = int(amount)
                if clear_amount < 1 or clear_amount > 1000:
                    await interaction.response.send_message(
                        "❌ Amount must be between 1 and 1000, or 'all' to clear entire chat.",
                        ephemeral=True
                    )
                    return
                amount_text = f"**{clear_amount}** messages"
                danger_level = "HIGH" if clear_amount >= 50 else "MEDIUM"
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid amount. Use a number (1-1000) or 'all' to clear entire chat.",
                    ephemeral=True
                )
                return
        
        # Prepare clear data
        clear_data = {
            'channel': target_channel,
            'amount': clear_amount
        }
        
        # Create confirmation embed
        if danger_level == "EXTREME":
            embed_color = 0xFF0000  # Red
            warning_text = "🚨 **DANGER**: This will delete ALL messages in the channel!"
        elif danger_level == "HIGH":
            embed_color = 0xFF6600  # Orange
            warning_text = "⚠️ **WARNING**: This will delete a large number of messages!"
        else:
            embed_color = 0xFFCC00  # Yellow
            warning_text = "⚠️ **CAUTION**: This action cannot be undone!"
        
        embed = discord.Embed(
            title="Confirm Message Clear",
            description=f"You are about to clear {amount_text} from {target_channel.mention}",
            color=embed_color
        )
        
        embed.add_field(name="⚠️ Warning", value=warning_text, inline=False)
        embed.add_field(name="Channel", value=target_channel.mention, inline=True)
        embed.add_field(name="Requested by", value=interaction.user.mention, inline=True)
        embed.set_footer(text="You have 60 seconds to confirm or cancel this action.")
        
        # Always show confirmation for safety
        view = ClearConfirmView(clear_data)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        # Wait for confirmation with timeout
        timed_out = await view.wait()
        
        if timed_out or not view.confirmed:
            # User didn't confirm or timed out
            timeout_embed = EmbedFactory.create_info_embed(
                "Clear Cancelled" if not timed_out else "Clear Timed Out",
                "❌ Message clearing cancelled. No messages were deleted." if not timed_out else "❌ Clear confirmation timed out. No messages were deleted."
            )
            try:
                await interaction.edit_original_response(embed=timeout_embed, view=None)
            except discord.NotFound:
                # Message was already edited/deleted
                pass

async def setup(bot):
    await bot.add_cog(Moderation(bot))