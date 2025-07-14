import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict
from utils.embed_factory import EmbedFactory
from repositories.mood_system import MoodSystemRepository
from loguru import logger

class MoodSystem(commands.Cog):
    """Enhanced mood reaction role system with nickname colors and display emojis"""
    
    def __init__(self, bot):
        self.bot = bot
        self.mood_configs = {
            "😄": {
                "name": "Happy",
                "color": 0x00FF00,  # Green
                "role_color": discord.Color.green(),
                "description": "Feeling great and positive!"
            },
            "😢": {
                "name": "Sad", 
                "color": 0x0080FF,  # Blue
                "role_color": discord.Color.blue(),
                "description": "Having a tough time"
            },
            "😠": {
                "name": "Angry",
                "color": 0xFF0000,  # Red
                "role_color": discord.Color.red(), 
                "description": "Feeling frustrated or upset"
            },
            "😴": {
                "name": "Tired",
                "color": 0x800080,  # Purple
                "role_color": discord.Color.purple(),
                "description": "Feeling sleepy or exhausted"
            }
        }
    
    @app_commands.command(name="mood-setup", description="Set up mood reaction roles for this server")
    @app_commands.default_permissions(administrator=True)
    async def mood_setup(self, interaction: discord.Interaction):
        """Set up the mood system"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if already configured
        existing_config = await MoodSystemRepository.get_config(interaction.guild_id)
        
        if existing_config:
            embed = EmbedFactory.create_warning_embed(
                "Mood System Already Set Up",
                "The mood system is already configured for this server."
            )
            
            class OverwriteChoice(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                    self.proceed = False
                
                @discord.ui.button(label="Reconfigure", style=discord.ButtonStyle.danger)
                async def reconfigure(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.proceed = True
                    self.stop()
                    await button_interaction.response.defer_update()
                
                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.stop()
                    await button_interaction.response.defer_update()
            
            choice_view = OverwriteChoice()
            await interaction.followup.send(embed=embed, view=choice_view, ephemeral=True)
            
            timed_out = await choice_view.wait()
            if timed_out or not choice_view.proceed:
                embed = EmbedFactory.create_info_embed("Setup Cancelled", "Mood system setup was cancelled.")
                await interaction.edit_original_response(embed=embed, view=None)
                return
        
        # Channel selection
        embed = EmbedFactory.create_info_embed(
            "Select Mood Channel",
            "Choose which channel to post the mood reaction message in:"
        )
        
        class ChannelSelect(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                self.selected_channel = None
                
                # Get text channels
                channels = [ch for ch in interaction.guild.channels if isinstance(ch, discord.TextChannel)][:25]
                
                options = []
                for channel in channels:
                    options.append(
                        discord.SelectOption(
                            label=f"#{channel.name}",
                            value=str(channel.id),
                            description=f"Category: {channel.category.name if channel.category else 'None'}"
                        )
                    )
                
                select = discord.ui.Select(
                    placeholder="Choose a channel for mood reactions...",
                    options=options
                )
                select.callback = self.channel_callback
                self.add_item(select)
            
            async def channel_callback(self, select_interaction: discord.Interaction):
                self.selected_channel = interaction.guild.get_channel(int(select_interaction.data['values'][0]))
                self.stop()
                await select_interaction.response.defer_update()
        
        channel_view = ChannelSelect()
        await interaction.edit_original_response(embed=embed, view=channel_view)
        
        timed_out = await channel_view.wait()
        if timed_out or not channel_view.selected_channel:
            embed = EmbedFactory.create_error_embed("Timeout", "Channel selection timed out.")
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Create or get mood roles
        embed = EmbedFactory.create_info_embed(
            "Creating Mood Roles",
            "⏳ Setting up mood roles..."
        )
        await interaction.edit_original_response(embed=embed, view=None)
        
        mood_roles = {}
        
        try:
            for emoji, config in self.mood_configs.items():
                role_name = f"Mood: {config['name']}"
                
                # Check if role exists
                existing_role = discord.utils.get(interaction.guild.roles, name=role_name)
                
                if existing_role:
                    mood_roles[emoji] = existing_role
                    # Update role color
                    await existing_role.edit(color=config['role_color'])
                else:
                    # Create new role
                    role = await interaction.guild.create_role(
                        name=role_name,
                        color=config['role_color'],
                        reason="Mood system setup"
                    )
                    mood_roles[emoji] = role
            
            # Create the mood message
            embed = EmbedFactory.create_info_embed(
                "🎭 Mood Selector",
                "React with an emoji below to set your current mood!\n"
                "Your nickname color and display emoji will change to match."
            )
            
            embed.add_field(
                name="Available Moods",
                value="\n".join([
                    f"{emoji} **{config['name']}** - {config['description']}"
                    for emoji, config in self.mood_configs.items()
                ]),
                inline=False
            )
            
            embed.add_field(
                name="How it works",
                value="• React to set your mood\n"
                      "• Your name color changes to match your mood\n"
                      "• The mood emoji appears next to your display name\n"
                      "• React with a different mood to change it\n"
                      "• Remove your reaction to clear your mood",
                inline=False
            )
            
            embed.set_footer(text="Only one mood can be active at a time")
            
            # Send the message
            mood_message = await channel_view.selected_channel.send(embed=embed)
            
            # Add reactions
            for emoji in self.mood_configs.keys():
                await mood_message.add_reaction(emoji)
            
            # Save configuration
            await MoodSystemRepository.create_or_update_config(
                guild_id=interaction.guild_id,
                channel_id=channel_view.selected_channel.id,
                message_id=mood_message.id,
                mood_roles={emoji: role.id for emoji, role in mood_roles.items()}
            )
            
            # Success message
            embed = EmbedFactory.create_success_embed(
                "Mood System Setup Complete!",
                f"✅ Mood reactions are now active in {channel_view.selected_channel.mention}"
            )
            
            embed.add_field(
                name="Roles Created",
                value="\n".join([f"{emoji} {role.mention}" for emoji, role in mood_roles.items()]),
                inline=False
            )
            
            await interaction.edit_original_response(embed=embed)
            
        except discord.Forbidden:
            embed = EmbedFactory.create_error_embed(
                "Permission Error",
                "I don't have permission to create roles or manage this channel."
            )
            await interaction.edit_original_response(embed=embed)
        except Exception as e:
            logger.error(f"Error setting up mood system: {e}")
            embed = EmbedFactory.create_error_embed(
                "Setup Failed",
                f"Failed to set up mood system: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed)
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle mood reaction additions"""
        if payload.user_id == self.bot.user.id:
            return
        
        config = await MoodSystemRepository.get_config(payload.guild_id)
        if not config or payload.message_id != config.message_id:
            return
        
        emoji_str = str(payload.emoji)
        if emoji_str not in self.mood_configs:
            return
        
        try:
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            
            if not member:
                return
            
            # Remove all other mood roles
            for other_emoji, role_id in config.mood_roles.items():
                if other_emoji != emoji_str:
                    role = guild.get_role(role_id)
                    if role and role in member.roles:
                        await member.remove_roles(role, reason="Mood changed")
            
            # Add the new mood role
            new_role = guild.get_role(config.mood_roles[emoji_str])
            if new_role and new_role not in member.roles:
                await member.add_roles(new_role, reason=f"Mood set to {self.mood_configs[emoji_str]['name']}")
            
            # Update nickname with emoji
            try:
                current_nick = member.display_name
                mood_config = self.mood_configs[emoji_str]
                
                # Remove any existing mood emojis
                clean_nick = current_nick
                for emoji in self.mood_configs.keys():
                    clean_nick = clean_nick.replace(f" {emoji}", "").replace(f"{emoji} ", "").replace(emoji, "")
                
                # Add new mood emoji
                new_nick = f"{clean_nick} {emoji_str}"
                
                # Limit nickname length
                if len(new_nick) > 32:
                    new_nick = f"{clean_nick[:29]}... {emoji_str}"
                
                await member.edit(nick=new_nick, reason=f"Mood display update")
                
            except discord.Forbidden:
                # Can't change nickname, that's okay
                pass
            
        except Exception as e:
            logger.error(f"Error handling mood reaction add: {e}")
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle mood reaction removals"""
        if payload.user_id == self.bot.user.id:
            return
        
        config = await MoodSystemRepository.get_config(payload.guild_id)
        if not config or payload.message_id != config.message_id:
            return
        
        emoji_str = str(payload.emoji)
        if emoji_str not in self.mood_configs:
            return
        
        try:
            guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            
            if not member:
                return
            
            # Remove the mood role
            role = guild.get_role(config.mood_roles[emoji_str])
            if role and role in member.roles:
                await member.remove_roles(role, reason="Mood cleared")
            
            # Remove emoji from nickname
            try:
                current_nick = member.display_name
                clean_nick = current_nick.replace(f" {emoji_str}", "").replace(f"{emoji_str} ", "").replace(emoji_str, "").strip()
                
                if clean_nick != current_nick:
                    await member.edit(nick=clean_nick if clean_nick else None, reason="Mood cleared")
                
            except discord.Forbidden:
                # Can't change nickname, that's okay
                pass
            
        except Exception as e:
            logger.error(f"Error handling mood reaction remove: {e}")
    
    @app_commands.command(name="mood-status", description="Check the current mood system status")
    async def mood_status(self, interaction: discord.Interaction):
        """Check mood system status"""
        config = await MoodSystemRepository.get_config(interaction.guild_id)
        
        if not config:
            embed = EmbedFactory.create_info_embed(
                "Mood System Not Set Up",
                "The mood system hasn't been configured for this server.\n"
                "Use `/mood-setup` to get started!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        channel = self.bot.get_channel(config.channel_id)
        
        embed = EmbedFactory.create_info_embed(
            "Mood System Status",
            f"🟢 Active in {channel.mention if channel else 'Unknown Channel'}"
        )
        
        # Count users with each mood
        mood_counts = {}
        for emoji, role_id in config.mood_roles.items():
            role = interaction.guild.get_role(role_id)
            if role:
                mood_counts[emoji] = len(role.members)
            else:
                mood_counts[emoji] = 0
        
        embed.add_field(
            name="Current Mood Distribution",
            value="\n".join([
                f"{emoji} **{self.mood_configs[emoji]['name']}**: {count} members"
                for emoji, count in mood_counts.items()
            ]),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="mood-remove", description="Remove the mood system from this server")
    @app_commands.default_permissions(administrator=True)
    async def mood_remove(self, interaction: discord.Interaction):
        """Remove mood system"""
        config = await MoodSystemRepository.get_config(interaction.guild_id)
        
        if not config:
            embed = EmbedFactory.create_info_embed(
                "No Mood System",
                "There's no mood system configured for this server."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = EmbedFactory.create_warning_embed(
            "Remove Mood System",
            "⚠️ This will:\n"
            "• Delete all mood roles\n"
            "• Remove mood emojis from nicknames\n"
            "• Delete the mood reaction message\n\n"
            "This action cannot be undone!"
        )
        
        class ConfirmRemoval(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.confirmed = False
            
            @discord.ui.button(label="Remove Mood System", style=discord.ButtonStyle.danger)
            async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.confirmed = True
                self.stop()
                await button_interaction.response.defer_update()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.stop()
                await button_interaction.response.defer_update()
        
        confirm_view = ConfirmRemoval()
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
        
        timed_out = await confirm_view.wait()
        if timed_out or not confirm_view.confirmed:
            embed = EmbedFactory.create_info_embed("Cancelled", "Mood system removal cancelled.")
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Remove the system
        try:
            # Delete roles and clean nicknames
            for emoji, role_id in config.mood_roles.items():
                role = interaction.guild.get_role(role_id)
                if role:
                    # Clean nicknames
                    for member in role.members:
                        try:
                            current_nick = member.display_name
                            clean_nick = current_nick.replace(f" {emoji}", "").replace(f"{emoji} ", "").replace(emoji, "").strip()
                            if clean_nick != current_nick:
                                await member.edit(nick=clean_nick if clean_nick else None, reason="Mood system removed")
                        except:
                            pass
                    
                    # Delete role
                    await role.delete(reason="Mood system removed")
            
            # Delete message
            try:
                channel = self.bot.get_channel(config.channel_id)
                if channel:
                    message = await channel.fetch_message(config.message_id)
                    await message.delete()
            except:
                pass
            
            # Remove from database
            await MoodSystemRepository.remove_config(interaction.guild_id)
            
            embed = EmbedFactory.create_success_embed(
                "Mood System Removed",
                "✅ The mood system has been completely removed."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
        except Exception as e:
            logger.error(f"Error removing mood system: {e}")
            embed = EmbedFactory.create_error_embed(
                "Removal Failed", 
                f"Failed to remove mood system: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed, view=None)

async def setup(bot):
    await bot.add_cog(MoodSystem(bot))