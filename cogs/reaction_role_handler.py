import discord
from discord.ext import commands
from repositories.reaction_roles import ReactionRoleRepository
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
            if await TeamMoodService.is_team_mood_role(guild.id, role.id):
                # Remove other mood roles first
                await TeamMoodService.remove_other_mood_roles(member, role)
            
            # Add the role
            if role not in member.roles:
                try:
                    await member.add_roles(role, reason="Reaction role assignment")
                    logger.info(f"Added role {role.name} to {member.display_name} in {guild.name}")
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
                except discord.Forbidden:
                    logger.error(f"Missing permissions to remove role {role.name} from {member.display_name}")
                except discord.HTTPException as e:
                    logger.error(f"Failed to remove role {role.name} from {member.display_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in on_raw_reaction_remove: {e}")

async def setup(bot):
    await bot.add_cog(ReactionRoleHandler(bot))