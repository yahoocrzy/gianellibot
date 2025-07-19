import discord
from discord.ext import commands
from repositories.reaction_roles import ReactionRoleRepository
from repositories.team_mood_repository import TeamMoodRepository
from services.team_mood_service import TeamMoodService
from loguru import logger

class ReactionRoleHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle reaction addition for role assignment"""
        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return
        
        try:
            # Get guild and member
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
            
            member = guild.get_member(payload.user_id)
            if not member:
                return
            
            # Check for reaction role mapping
            reaction_role = await ReactionRoleRepository.get_by_message_and_emoji(
                guild.id, payload.message_id, str(payload.emoji)
            )
            
            if not reaction_role:
                return
            
            # Get the role
            role = guild.get_role(reaction_role.role_id)
            if not role:
                logger.warning(f"Role {reaction_role.role_id} not found in guild {guild.id}")
                return
            
            # Check if this is a team mood role for exclusive behavior
            is_mood_role = await TeamMoodService.is_team_mood_role(guild.id, role.id)
            if is_mood_role:
                # Remove other mood roles first
                await TeamMoodService.remove_other_mood_roles(member, role)
            
            # Add the role
            if role not in member.roles:
                try:
                    await member.add_roles(role, reason="Reaction role assignment")
                    logger.info(f"Added role {role.name} to {member.display_name} in {guild.name}")
                    
                    # Update nickname with status emoji if this is a mood role
                    if is_mood_role:
                        logger.info(f"Role {role.name} is a team mood role, updating nickname for {member.display_name}")
                        config = await TeamMoodRepository.get_config(guild.id)
                        if config:
                            emoji = TeamMoodService.get_emoji_for_role(role.id, config)
                            logger.info(f"Got emoji '{emoji}' for role {role.name}")
                            await TeamMoodService.update_member_nickname(member, emoji)
                        else:
                            logger.warning(f"No team mood config found for guild {guild.id}")
                    else:
                        logger.info(f"Role {role.name} is not a team mood role, skipping nickname update")
                            
                except discord.Forbidden:
                    logger.error(f"Missing permissions to add role {role.name} to {member.display_name}")
                except discord.HTTPException as e:
                    logger.error(f"Failed to add role {role.name} to {member.display_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in on_raw_reaction_add: {e}")
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle reaction removal for role removal"""
        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return
        
        try:
            # Get guild and member
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
            
            member = guild.get_member(payload.user_id)
            if not member:
                return
            
            # Check for reaction role mapping
            reaction_role = await ReactionRoleRepository.get_by_message_and_emoji(
                guild.id, payload.message_id, str(payload.emoji)
            )
            
            if not reaction_role:
                return
            
            # Get the role
            role = guild.get_role(reaction_role.role_id)
            if not role:
                return
            
            # Remove the role
            if role in member.roles:
                try:
                    await member.remove_roles(role, reason="Reaction role removal")
                    logger.info(f"Removed role {role.name} from {member.display_name} in {guild.name}")
                    
                    # Remove status emoji from nickname if this is a mood role
                    if await TeamMoodService.is_team_mood_role(guild.id, role.id):
                        await TeamMoodService.update_member_nickname(member, None)
                        
                except discord.Forbidden:
                    logger.error(f"Missing permissions to remove role {role.name} from {member.display_name}")
                except discord.HTTPException as e:
                    logger.error(f"Failed to remove role {role.name} from {member.display_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in on_raw_reaction_remove: {e}")
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Monitor nickname changes and remove manually added status emojis"""
        # Only check if nickname changed
        if before.display_name == after.display_name:
            return
        
        # Check if user manually added status emojis to their nickname
        emoji_list = ['✅', '⚠️', '🛑', '💤']
        user_added_emoji = False
        
        for emoji in emoji_list:
            if emoji in after.display_name:
                # Check if they actually have a team mood role for this emoji
                config = await TeamMoodRepository.get_config(after.guild.id)
                if config:
                    user_has_matching_role = False
                    
                    # Check which emoji corresponds to which role they have
                    if emoji == '✅' and config.role_ready_id:
                        role = after.guild.get_role(config.role_ready_id)
                        user_has_matching_role = role in after.roles
                    elif emoji == '⚠️' and config.role_phone_id:
                        role = after.guild.get_role(config.role_phone_id)
                        user_has_matching_role = role in after.roles
                    elif emoji == '🛑' and config.role_dnd_id:
                        role = after.guild.get_role(config.role_dnd_id)
                        user_has_matching_role = role in after.roles
                    elif emoji == '💤' and config.role_away_id:
                        role = after.guild.get_role(config.role_away_id)
                        user_has_matching_role = role in after.roles
                    
                    # If they have the emoji but not the role, they added it manually
                    if not user_has_matching_role:
                        user_added_emoji = True
                        break
        
        # If user manually added emojis, clean their nickname
        if user_added_emoji:
            logger.info(f"User {after.name} manually added status emoji to nickname, cleaning it")
            await TeamMoodService.update_member_nickname(after, None)

async def setup(bot):
    await bot.add_cog(ReactionRoleHandler(bot))