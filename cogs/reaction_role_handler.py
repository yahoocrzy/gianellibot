import discord
from discord.ext import commands
from repositories.reaction_roles import ReactionRoleRepository
from repositories.team_mood_repository import TeamMoodRepository
from services.team_mood_service import TeamMoodService
from loguru import logger

class ReactionRoleHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def remove_other_mood_roles_and_reactions(self, member: discord.Member, new_role: discord.Role, message_id: int, channel_id: int):
        """Remove other mood roles and their corresponding reactions from the message"""
        try:
            logger.info(f"Removing other mood roles and reactions for {member.display_name}, keeping role {new_role.name}")
            
            # Get team mood config to know which reactions to check
            config = await TeamMoodRepository.get_config(member.guild.id)
            if not config:
                logger.warning(f"No team mood config found for guild {member.guild.id}")
                return
            
            # Remove other mood roles using the existing service method
            await TeamMoodService.remove_other_mood_roles(member, new_role)
            
            # Get the message to remove old reactions
            channel = member.guild.get_channel(channel_id)
            if not channel:
                logger.warning(f"Channel {channel_id} not found")
                return
            
            try:
                message = await channel.fetch_message(message_id)
            except (discord.NotFound, discord.Forbidden) as e:
                logger.warning(f"Could not fetch mood message {message_id}: {e}")
                return
            
            # Map role IDs to their emojis
            role_emoji_map = {
                config.role_ready_id: TeamMoodService.STATUS_EMOJIS['ready'],
                config.role_phone_id: TeamMoodService.STATUS_EMOJIS['phone'],
                config.role_dnd_id: TeamMoodService.STATUS_EMOJIS['dnd'],
                config.role_away_id: TeamMoodService.STATUS_EMOJIS['away']
            }
            
            # Remove user's reactions from OTHER mood status emojis (not the new one they just clicked)
            # Get the emoji for the new role they're selecting
            new_role_emoji = None
            for role_id, emoji in role_emoji_map.items():
                if role_id == new_role.id:
                    new_role_emoji = emoji
                    break
            
            # Create removal tasks to run in parallel for faster execution
            import asyncio
            removal_tasks = []
            
            for role_id, emoji in role_emoji_map.items():
                if role_id and role_id != new_role.id:  # Only remove OTHER reactions, not the current one
                    # Find the reaction for this emoji
                    for reaction in message.reactions:
                        if str(reaction.emoji) == emoji:
                            # Create a coroutine for removing this reaction
                            removal_tasks.append(self._remove_user_reaction(reaction, member, emoji))
                            break
            
            # Execute all removals in parallel for instant response
            if removal_tasks:
                removed_reactions = await asyncio.gather(*removal_tasks, return_exceptions=True)
                successful_removals = [r for r in removed_reactions if r is not None and not isinstance(r, Exception)]
                if successful_removals:
                    logger.info(f"Successfully removed reactions {successful_removals} for {member.display_name}")
            else:
                logger.info(f"No other mood reactions found for {member.display_name} to remove")
            
        except Exception as e:
            logger.error(f"Error removing other mood roles and reactions: {e}")
    
    async def remove_all_mood_reactions(self, member: discord.Member, message_id: int, channel_id: int):
        """Remove all mood reactions from a user (for reset functionality)"""
        try:
            logger.info(f"Removing all mood reactions for {member.display_name}")
            
            # Get team mood config
            config = await TeamMoodRepository.get_config(member.guild.id)
            if not config:
                logger.warning(f"No team mood config found for guild {member.guild.id}")
                return
            
            # Get the message
            channel = member.guild.get_channel(channel_id)
            if not channel:
                logger.warning(f"Channel {channel_id} not found")
                return
            
            try:
                message = await channel.fetch_message(message_id)
            except (discord.NotFound, discord.Forbidden) as e:
                logger.warning(f"Could not fetch mood message {message_id}: {e}")
                return
            
            # Remove all mood reactions (including reset)
            all_mood_emojis = list(TeamMoodService.STATUS_EMOJIS.values())
            
            removal_tasks = []
            for emoji in all_mood_emojis:
                for reaction in message.reactions:
                    if str(reaction.emoji) == emoji:
                        removal_tasks.append(self._remove_user_reaction(reaction, member, emoji))
                        break
            
            # Execute all removals in parallel
            if removal_tasks:
                import asyncio
                removed_reactions = await asyncio.gather(*removal_tasks, return_exceptions=True)
                successful_removals = [r for r in removed_reactions if r is not None and not isinstance(r, Exception)]
                if successful_removals:
                    logger.info(f"Reset: Removed all reactions {successful_removals} for {member.display_name}")
            else:
                logger.info(f"Reset: No mood reactions found for {member.display_name} to remove")
                
        except Exception as e:
            logger.error(f"Error removing all mood reactions: {e}")
    
    async def _remove_user_reaction(self, reaction: discord.Reaction, member: discord.Member, emoji: str):
        """Helper method to remove a user's reaction and return the emoji if successful"""
        try:
            # Check if user has this reaction first (more efficient than getting all users)
            users = [user async for user in reaction.users()]
            if member in users:
                await reaction.remove(member)
                logger.info(f"Removed {member.display_name}'s reaction {emoji} from mood message")
                return emoji
            return None
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning(f"Could not remove reaction {emoji} for {member.display_name}: {e}")
            return None
    
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
            
            # Check for reset reaction first (before database lookup)
            if str(payload.emoji) == TeamMoodService.STATUS_EMOJIS['reset']:
                logger.info(f"Processing reset reaction for {member.display_name}")
                # Check if this is on a team mood message
                config = await TeamMoodRepository.get_config(guild.id)
                if config and payload.message_id == config.message_id:
                    # Remove all mood roles and clear nickname
                    await TeamMoodService.remove_all_mood_roles(member)
                    await TeamMoodService.update_member_nickname(member, None)
                    
                    # Remove all mood reactions for this user
                    await self.remove_all_mood_reactions(member, payload.message_id, payload.channel_id)
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
            
            # For mood roles, ALWAYS remove other reactions and roles first (even if they already have this role)
            if is_mood_role:
                logger.info(f"Processing mood role {role.name} - removing other mood reactions and roles")
                await self.remove_other_mood_roles_and_reactions(member, role, payload.message_id, payload.channel_id)
                
                # IMPORTANT: Clear nickname first to prevent emoji stacking
                logger.info(f"Clearing nickname before applying new status for {member.display_name}")
                await TeamMoodService.update_member_nickname(member, None)
            
            # Add the role (only if they don't already have it)
            if role not in member.roles:
                try:
                    await member.add_roles(role, reason="Reaction role assignment")
                    logger.info(f"Added role {role.name} to {member.display_name} in {guild.name}")
                            
                except discord.Forbidden:
                    logger.error(f"Missing permissions to add role {role.name} to {member.display_name}")
                except discord.HTTPException as e:
                    logger.error(f"Failed to add role {role.name} to {member.display_name}: {e}")
            else:
                logger.info(f"User {member.display_name} already has role {role.name}")
            
            # Update nickname with status emoji if this is a mood role (always do this for mood roles)
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