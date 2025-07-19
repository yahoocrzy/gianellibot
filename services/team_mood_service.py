from typing import Dict, List, Optional
import discord
from repositories.team_mood_repository import TeamMoodRepository
from repositories.reaction_roles import ReactionRoleRepository

class TeamMoodService:
    STATUS_EMOJIS = {
        'ready': '✅',
        'phone': '⚠️',
        'dnd': '🛑',
        'away': '💤'
    }
    
    STATUS_NAMES = {
        'ready': '✅ Ready to Work',
        'phone': '⚠️ Phone Only',
        'dnd': '🛑 Do not disturb!',
        'away': '💤 Need time'
    }
    
    STATUS_COLORS = {
        'ready': 0x00D166,  # Green
        'phone': 0xFEE75C,  # Yellow
        'dnd': 0xED4245,    # Red
        'away': 0x5DADE2    # Bright Blue
    }
    
    @staticmethod
    async def setup_team_mood(guild: discord.Guild, channel: discord.TextChannel) -> Dict:
        """Complete automated setup process for team mood system"""
        try:
            # Step 1: Create or update the four status roles
            roles = await TeamMoodService.create_status_roles(guild)
            
            # Step 2: Create and send the status embed message
            embed = await TeamMoodService.generate_status_embed()
            message = await channel.send(embed=embed)
            
            # Step 3: Add reaction emojis in order
            for emoji in TeamMoodService.STATUS_EMOJIS.values():
                await message.add_reaction(emoji)
            
            # Step 4: Configure reaction roles for each emoji-role pair
            reaction_configs = [
                (TeamMoodService.STATUS_EMOJIS['ready'], roles['ready']),
                (TeamMoodService.STATUS_EMOJIS['phone'], roles['phone']),
                (TeamMoodService.STATUS_EMOJIS['dnd'], roles['dnd']),
                (TeamMoodService.STATUS_EMOJIS['away'], roles['away'])
            ]
            
            for emoji, role in reaction_configs:
                # Create reaction role entry with exclusive=False
                await ReactionRoleRepository.create(
                    guild_id=guild.id,
                    message_id=message.id,
                    channel_id=channel.id,
                    emoji=emoji,
                    role_id=role.id,
                    exclusive=False,  # Important: allows status removal
                    embed_color="#5865F2"
                )
            
            # Step 5: Save team mood configuration
            await TeamMoodRepository.create_config(
                guild_id=guild.id,
                channel_id=channel.id,
                message_id=message.id,
                role_ready_id=roles['ready'].id,
                role_phone_id=roles['phone'].id,
                role_dnd_id=roles['dnd'].id,
                role_away_id=roles['away'].id
            )
            
            # Step 6: Pin the message for easy access
            try:
                await message.pin(reason="Team Mood Status System")
            except discord.Forbidden:
                pass  # Continue if can't pin
            
            return {
                'success': True,
                'message': message,
                'roles': roles,
                'channel': channel
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
        
    @staticmethod
    async def create_status_roles(guild: discord.Guild) -> Dict[str, discord.Role]:
        """Create the four status roles with appropriate colors"""
        role_configs = {
            'ready': {'name': TeamMoodService.STATUS_NAMES['ready'], 'color': TeamMoodService.STATUS_COLORS['ready']},
            'phone': {'name': TeamMoodService.STATUS_NAMES['phone'], 'color': TeamMoodService.STATUS_COLORS['phone']},
            'dnd': {'name': TeamMoodService.STATUS_NAMES['dnd'], 'color': TeamMoodService.STATUS_COLORS['dnd']},
            'away': {'name': TeamMoodService.STATUS_NAMES['away'], 'color': TeamMoodService.STATUS_COLORS['away']}
        }
        
        created_roles = {}
        
        for key, config in role_configs.items():
            # Check if role already exists
            existing_role = discord.utils.get(guild.roles, name=config['name'])
            
            if existing_role:
                # Update existing role color if needed
                if existing_role.color.value != config['color']:
                    try:
                        await existing_role.edit(color=discord.Color(config['color']))
                    except discord.Forbidden:
                        pass  # Continue if can't edit color
                created_roles[key] = existing_role
            else:
                # Create new role
                role = await guild.create_role(
                    name=config['name'],
                    color=discord.Color(config['color']),
                    mentionable=False,
                    reason="ClickBot Team Mood System Setup"
                )
                created_roles[key] = role
                
        return created_roles
        
    @staticmethod
    async def generate_status_embed() -> discord.Embed:
        """Generate the team status embed message"""
        embed = discord.Embed(
            title="Team Status Update",
            description=(
                "**Set your current availability status:**\n\n"
                f"{TeamMoodService.STATUS_EMOJIS['ready']} **{TeamMoodService.STATUS_NAMES['ready']}** - Available for tasks and collaboration\n"
                f"{TeamMoodService.STATUS_EMOJIS['phone']} **{TeamMoodService.STATUS_NAMES['phone']}** - Limited availability, urgent matters only\n"
                f"{TeamMoodService.STATUS_EMOJIS['dnd']} **{TeamMoodService.STATUS_NAMES['dnd']}** - Focus mode, please don't interrupt\n"
                f"{TeamMoodService.STATUS_EMOJIS['away']} **{TeamMoodService.STATUS_NAMES['away']}** - Taking a break, will respond later\n\n"
                "*Click a reaction to update your status. Remove to clear.*"
            ),
            color=0x5865F2
        )
        embed.set_footer(text="Powered by ClickBot Team Mood System")
        return embed
    
    @staticmethod
    async def is_team_mood_role(guild_id: int, role_id: int) -> bool:
        """Check if a role is part of the team mood system"""
        config = await TeamMoodRepository.get_config(guild_id)
        if not config:
            return False
        
        mood_roles = [config.role_ready_id, config.role_phone_id, 
                      config.role_dnd_id, config.role_away_id]
        return role_id in mood_roles
    
    @staticmethod
    async def remove_other_mood_roles(member: discord.Member, new_role: discord.Role):
        """Remove other mood roles when a new one is selected"""
        config = await TeamMoodRepository.get_config(member.guild.id)
        if not config:
            return
        
        mood_role_ids = [config.role_ready_id, config.role_phone_id, 
                         config.role_dnd_id, config.role_away_id]
        
        # Remove all mood roles except the new one
        for role in member.roles:
            if role.id in mood_role_ids and role.id != new_role.id:
                try:
                    await member.remove_roles(role, reason="Team mood status change")
                except discord.Forbidden:
                    pass  # Continue if can't remove role
    
    @staticmethod
    async def get_status_counts(guild: discord.Guild) -> Dict[str, int]:
        """Get count of members with each status"""
        config = await TeamMoodRepository.get_config(guild.id)
        if not config:
            return {}
        
        counts = {'ready': 0, 'phone': 0, 'dnd': 0, 'away': 0}
        
        # Count members with each role
        if config.role_ready_id:
            role = guild.get_role(config.role_ready_id)
            if role:
                counts['ready'] = len(role.members)
        
        if config.role_phone_id:
            role = guild.get_role(config.role_phone_id)
            if role:
                counts['phone'] = len(role.members)
        
        if config.role_dnd_id:
            role = guild.get_role(config.role_dnd_id)
            if role:
                counts['dnd'] = len(role.members)
        
        if config.role_away_id:
            role = guild.get_role(config.role_away_id)
            if role:
                counts['away'] = len(role.members)
        
        return counts
    
    @staticmethod
    async def update_member_nickname(member: discord.Member, status_emoji: str = None):
        """Update member nickname to show status emoji at the end"""
        try:
            # Get the original nickname (without any status emojis)
            current_nick = member.display_name
            
            # Remove any existing status emojis from the end of nickname
            emoji_list = ['✅', '⚠️', '🛑', '💤']
            original_nick = current_nick
            for emoji in emoji_list:
                if original_nick.endswith(' ' + emoji):
                    original_nick = original_nick[:-2]  # Remove space and emoji
                    break
            
            # Set new nickname with status emoji at the end
            if status_emoji:
                new_nick = f"{original_nick} {status_emoji}"
                # Discord nickname limit is 32 characters
                if len(new_nick) > 32:
                    # Truncate the original name to fit
                    max_name_length = 32 - 2  # Account for space and emoji
                    original_nick = original_nick[:max_name_length]
                    new_nick = f"{original_nick} {status_emoji}"
            else:
                new_nick = original_nick
            
            # Only update if the nickname actually changed
            if member.display_name != new_nick:
                await member.edit(nick=new_nick, reason="Team mood status update")
                
        except discord.Forbidden:
            pass  # Can't change nickname, continue without error
        except discord.HTTPException:
            pass  # Other Discord error, continue without error
    
    @staticmethod
    def get_emoji_for_role(role_id: int, config) -> Optional[str]:
        """Get the emoji associated with a specific role"""
        if role_id == config.role_ready_id:
            return TeamMoodService.STATUS_EMOJIS['ready']
        elif role_id == config.role_phone_id:
            return TeamMoodService.STATUS_EMOJIS['phone']
        elif role_id == config.role_dnd_id:
            return TeamMoodService.STATUS_EMOJIS['dnd']
        elif role_id == config.role_away_id:
            return TeamMoodService.STATUS_EMOJIS['away']
        return None