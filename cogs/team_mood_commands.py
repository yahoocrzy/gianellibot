import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from services.team_mood_service import TeamMoodService
from repositories.team_mood_repository import TeamMoodRepository
from repositories.reaction_roles import ReactionRoleRepository
from utils.embed_factory import EmbedFactory
from loguru import logger

class TeamMoodCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(name="team-mood-setup", description="Set up the team mood status system")
    @app_commands.describe(channel="The channel to post the status message in (default: current channel)")
    @app_commands.default_permissions(administrator=True)
    async def team_mood_setup(self, interaction: discord.Interaction, 
                            channel: Optional[discord.TextChannel] = None):
        """Set up the team mood status system with one command"""
        await interaction.response.defer(ephemeral=True)
        
        # Use current channel if none specified
        target_channel = channel or interaction.channel
        
        try:
            # Check if system already exists
            existing_config = await TeamMoodRepository.get_config(interaction.guild.id)
            if existing_config and existing_config.enabled:
                embed = EmbedFactory.create_warning_embed(
                    "System Already Active",
                    "Team mood system is already set up. Use `/team-mood-remove` first to reconfigure."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Run the automated setup
            result = await TeamMoodService.setup_team_mood(
                interaction.guild, 
                target_channel
            )
            
            if result['success']:
                # Build success message with role mentions
                roles = result['roles']
                embed = EmbedFactory.create_success_embed(
                    "Team Mood System Setup Complete!",
                    f"✅ **Created/Updated 4 status roles:**\n"
                    f"   • {roles['ready'].mention} - Available for work\n"
                    f"   • {roles['phone'].mention} - Limited availability\n"
                    f"   • {roles['dnd'].mention} - Do not disturb\n"
                    f"   • {roles['away'].mention} - Away/Need time\n\n"
                    f"✅ **Posted status message in** {target_channel.mention}\n"
                    f"✅ **Configured reaction roles automatically**\n"
                    f"✅ **System is now active!**\n\n"
                    f"Team members can now click reactions to set their status.\n"
                    f"Removing a reaction will remove the status role."
                )
                embed.set_footer(text="Tip: Pin the status message for easy access!")
            else:
                embed = EmbedFactory.create_error_embed(
                    "Setup Failed",
                    f"Error: {result['error']}\n\n"
                    f"Please ensure ClickBot has 'Manage Roles' permission and try again."
                )
                
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Team mood setup error: {e}")
            embed = EmbedFactory.create_error_embed(
                "Setup Error",
                f"An unexpected error occurred: {str(e)}\n\n"
                f"Please check ClickBot's permissions and try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="team-mood-status", description="Check current team availability")
    async def team_mood_status(self, interaction: discord.Interaction):
        """Display current team member statuses"""
        await interaction.response.defer()
        
        try:
            config = await TeamMoodRepository.get_config(interaction.guild.id)
            if not config:
                embed = EmbedFactory.create_warning_embed(
                    "No Team Mood System",
                    "Team mood system is not set up in this server. Use `/team-mood-setup` to configure it."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Get status counts
            status_counts = await TeamMoodService.get_status_counts(interaction.guild)
            total = sum(status_counts.values())
            
            embed = discord.Embed(
                title="📊 Team Availability Status",
                color=0x5865F2,
                timestamp=discord.utils.utcnow()
            )
            
            # Add status breakdown
            status_text = ""
            for status_key, emoji in TeamMoodService.STATUS_EMOJIS.items():
                name = TeamMoodService.STATUS_NAMES[status_key]
                count = status_counts.get(status_key, 0)
                percentage = (count / total * 100) if total > 0 else 0
                status_text += f"{emoji} **{name}**: {count} ({percentage:.1f}%)\n"
            
            embed.add_field(
                name="Current Status Distribution",
                value=status_text + f"\n👥 **Total Team Members with Status**: {total}",
                inline=False
            )
            
            # Add channel info
            channel = interaction.guild.get_channel(config.channel_id)
            if channel:
                embed.add_field(
                    name="Status Message Location",
                    value=f"📍 {channel.mention}",
                    inline=False
                )
            
            embed.set_footer(text="Use reactions on the status message to update your availability")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Team mood status error: {e}")
            embed = EmbedFactory.create_error_embed(
                "Status Check Error",
                f"Failed to retrieve team status: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="team-mood-remove", description="Remove the team mood system")
    @app_commands.describe(delete_roles="Whether to delete the status roles (default: False)")
    @app_commands.default_permissions(administrator=True)
    async def team_mood_remove(self, interaction: discord.Interaction, 
                             delete_roles: bool = False):
        """Remove the team mood system and optionally delete roles"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            config = await TeamMoodRepository.get_config(interaction.guild.id)
            if not config:
                embed = EmbedFactory.create_warning_embed(
                    "No Configuration Found",
                    "Team mood system is not set up in this server."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Delete the status message if it exists
            try:
                channel = interaction.guild.get_channel(config.channel_id)
                if channel:
                    message = await channel.fetch_message(config.message_id)
                    await message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
            
            # Remove reaction role entries
            await ReactionRoleRepository.delete_by_message(
                config.guild_id, 
                config.message_id
            )
            
            # Optionally delete the roles
            deleted_roles = []
            if delete_roles:
                role_ids = [
                    config.role_ready_id,
                    config.role_phone_id,
                    config.role_dnd_id,
                    config.role_away_id
                ]
                
                for role_id in role_ids:
                    if role_id:
                        role = interaction.guild.get_role(role_id)
                        if role:
                            try:
                                await role.delete(reason="Team mood system removal")
                                deleted_roles.append(role.name)
                            except discord.Forbidden:
                                pass
            
            # Delete configuration
            await TeamMoodRepository.delete_config(interaction.guild.id)
            
            # Build response
            description = "✅ Team mood system has been removed.\n"
            description += "✅ Status message deleted.\n"
            description += "✅ Reaction roles cleared.\n"
            
            if deleted_roles:
                description += f"✅ Deleted roles: {', '.join(deleted_roles)}"
            else:
                description += "ℹ️ Status roles were preserved (use `delete_roles=True` to remove them)"
            
            embed = EmbedFactory.create_success_embed(
                "Team Mood System Removed",
                description
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Team mood removal error: {e}")
            embed = EmbedFactory.create_error_embed(
                "Removal Error",
                f"Failed to remove team mood system: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        
    @app_commands.command(name="team-mood-refresh", description="Refresh the team mood message")
    @app_commands.default_permissions(administrator=True)
    async def team_mood_refresh(self, interaction: discord.Interaction):
        """Recreate the team mood message if it was deleted"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            config = await TeamMoodRepository.get_config(interaction.guild.id)
            if not config:
                embed = EmbedFactory.create_warning_embed(
                    "No Configuration Found",
                    "Team mood system is not set up in this server. Use `/team-mood-setup` to configure it."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Get the channel
            channel = interaction.guild.get_channel(config.channel_id)
            if not channel:
                embed = EmbedFactory.create_error_embed(
                    "Channel Not Found",
                    "The configured channel no longer exists. Please run `/team-mood-setup` again."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Generate new status embed and send
            embed_msg = await TeamMoodService.generate_status_embed()
            message = await channel.send(embed=embed_msg)
            
            # Add reactions in proper order
            status_order = ['ready', 'phone', 'dnd', 'away', 'reset']
            for status in status_order:
                await message.add_reaction(TeamMoodService.STATUS_EMOJIS[status])
            
            # Update message ID in config
            config.message_id = message.id
            await TeamMoodRepository.create_config(
                guild_id=config.guild_id,
                channel_id=config.channel_id,
                message_id=message.id,
                role_ready_id=config.role_ready_id,
                role_phone_id=config.role_phone_id,
                role_dnd_id=config.role_dnd_id,
                role_away_id=config.role_away_id
            )
            
            # Update reaction role entries
            await ReactionRoleRepository.delete_by_message(config.guild_id, config.message_id)
            
            reaction_configs = [
                (TeamMoodService.STATUS_EMOJIS['ready'], config.role_ready_id),
                (TeamMoodService.STATUS_EMOJIS['phone'], config.role_phone_id),
                (TeamMoodService.STATUS_EMOJIS['dnd'], config.role_dnd_id),
                (TeamMoodService.STATUS_EMOJIS['away'], config.role_away_id)
            ]
            
            for emoji, role_id in reaction_configs:
                if role_id:
                    await ReactionRoleRepository.create(
                        guild_id=config.guild_id,
                        message_id=message.id,
                        channel_id=channel.id,
                        emoji=emoji,
                        role_id=role_id,
                        exclusive=False,
                        embed_color="#5865F2"
                    )
            
            # Add reset reaction entry
            await ReactionRoleRepository.create(
                guild_id=config.guild_id,
                message_id=message.id,
                channel_id=channel.id,
                emoji=TeamMoodService.STATUS_EMOJIS['reset'],
                role_id=0,  # Special value for reset
                exclusive=False,
                embed_color="#5865F2"
            )
            
            embed = EmbedFactory.create_success_embed(
                "Team Mood Message Refreshed",
                f"✅ New status message created in {channel.mention}\n"
                f"✅ Reaction roles reconfigured\n"
                f"✅ System is now active again!"
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Team mood refresh error: {e}")
            embed = EmbedFactory.create_error_embed(
                "Refresh Error",
                f"Failed to refresh team mood message: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="team-mood-test-nickname", description="Test nickname functionality (Debug)")
    @app_commands.describe(user="User to test nickname update on", emoji="Emoji to add (optional)")
    @app_commands.default_permissions(administrator=True)
    async def team_mood_test_nickname(self, interaction: discord.Interaction, 
                                    user: discord.Member, emoji: str = "✅"):
        """Test command to manually update a user's nickname with status emoji"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Test the nickname update function directly
            await TeamMoodService.update_member_nickname(user, emoji)
            
            embed = EmbedFactory.create_success_embed(
                "Nickname Test Complete",
                f"Attempted to update {user.mention}'s nickname with emoji: {emoji}\n"
                f"Check the bot logs for detailed results."
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Nickname test error: {e}")
            embed = EmbedFactory.create_error_embed(
                "Nickname Test Failed",
                f"Error testing nickname update: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TeamMoodCommands(bot))