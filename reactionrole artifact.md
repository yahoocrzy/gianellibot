# Team Mood Status System - Implementation Specification for ClickBot

## Executive Summary

This specification details a **fully automated** team mood/status system for ClickBot that requires **only one command** to set up. The system will:

1. **Automatically create 4 Discord roles** (Ready to Work, Phone Only, Do not disturb!, Need time)
2. **Post a formatted status message** with reaction emojis
3. **Configure reaction roles** for each status
4. **Handle exclusive status switching** (only one status at a time)
5. **Allow status removal** by removing reactions

**Zero manual configuration required** - admins just run `/team-mood-setup` and the system is ready.

## Feature Overview

Implement an automated team mood/status system that allows Discord users to set their availability status using reaction roles. This feature should integrate seamlessly with ClickBot's existing architecture and **automatically create all required roles**.

## Automatic Role Creation

The system will **automatically create four Discord roles** when `/team-mood-setup` is run:

1. **Ready to Work** (Green - #00D166)
2. **Phone Only** (Yellow - #FEE75C)
3. **Do not disturb!** (Red - #ED4245)
4. **Need time** (Gray - #747F8D)

### Role Creation Process:
- Checks if roles already exist by name
- Creates new roles if they don't exist
- Updates role colors if they exist but have different colors
- Positions roles appropriately in the hierarchy
- Makes roles non-mentionable by default
- No manual role creation required by admins

## Database Schema Updates

### New Table: `team_mood_config`

```sql
CREATE TABLE team_mood_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    role_ready_id BIGINT,
    role_phone_id BIGINT,
    role_dnd_id BIGINT,
    role_away_id BIGINT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES server_config(guild_id)
);
```

### New Model in `database/models.py`

```python
class TeamMoodConfig(Base):
    __tablename__ = 'team_mood_config'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=False)
    role_ready_id = Column(BigInteger)
    role_phone_id = Column(BigInteger)
    role_dnd_id = Column(BigInteger)
    role_away_id = Column(BigInteger)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

## Repository Layer

### New File: `repositories/team_mood_repository.py`

```python
from typing import Optional
from sqlalchemy import select, update
from database.models import TeamMoodConfig
from database.connection import get_db_session

class TeamMoodRepository:
    @staticmethod
    async def create_config(guild_id: int, channel_id: int, message_id: int, 
                          role_ready_id: int, role_phone_id: int, 
                          role_dnd_id: int, role_away_id: int) -> TeamMoodConfig:
        """Create or update team mood configuration"""
        async with get_db_session() as session:
            # Check if config exists
            stmt = select(TeamMoodConfig).where(TeamMoodConfig.guild_id == guild_id)
            result = await session.execute(stmt)
            config = result.scalar_one_or_none()
            
            if config:
                # Update existing
                config.channel_id = channel_id
                config.message_id = message_id
                config.role_ready_id = role_ready_id
                config.role_phone_id = role_phone_id
                config.role_dnd_id = role_dnd_id
                config.role_away_id = role_away_id
                config.enabled = True
                config.updated_at = datetime.utcnow()
            else:
                # Create new
                config = TeamMoodConfig(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    message_id=message_id,
                    role_ready_id=role_ready_id,
                    role_phone_id=role_phone_id,
                    role_dnd_id=role_dnd_id,
                    role_away_id=role_away_id,
                    enabled=True
                )
                session.add(config)
            
            await session.commit()
            return config
        
    @staticmethod
    async def get_config(guild_id: int) -> Optional[TeamMoodConfig]:
        """Get team mood configuration for a guild"""
        async with get_db_session() as session:
            stmt = select(TeamMoodConfig).where(
                TeamMoodConfig.guild_id == guild_id,
                TeamMoodConfig.enabled == True
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        
    @staticmethod
    async def delete_config(guild_id: int) -> bool:
        """Delete team mood configuration"""
        async with get_db_session() as session:
            stmt = update(TeamMoodConfig).where(
                TeamMoodConfig.guild_id == guild_id
            ).values(enabled=False)
            
            await session.execute(stmt)
            await session.commit()
            return True
            
    @staticmethod
    async def get_all_mood_roles(guild_id: int) -> list[int]:
        """Get all mood role IDs for checking"""
        config = await TeamMoodRepository.get_config(guild_id)
        if not config:
            return []
        
        return [
            config.role_ready_id,
            config.role_phone_id,
            config.role_dnd_id,
            config.role_away_id
        ]
```

## Service Layer

### New File: `services/team_mood_service.py`

```python
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
        'ready': 'Ready to Work',
        'phone': 'Phone Only',
        'dnd': 'Do not disturb!',
        'away': 'Need time'
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
            'ready': {'name': 'Ready to Work', 'color': 0x00D166},  # Green
            'phone': {'name': 'Phone Only', 'color': 0xFEE75C},     # Yellow
            'dnd': {'name': 'Do not disturb!', 'color': 0xED4245},  # Red
            'away': {'name': 'Need time', 'color': 0x747F8D}        # Gray
        }
        
        created_roles = {}
        
        for key, config in role_configs.items():
            # Check if role already exists
            existing_role = discord.utils.get(guild.roles, name=config['name'])
            
            if existing_role:
                # Update existing role color if needed
                if existing_role.color.value != config['color']:
                    await existing_role.edit(color=discord.Color(config['color']))
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
                "✅ **Ready to Work** - Available for tasks and collaboration\n"
                "⚠️ **Phone Only** - Limited availability, urgent matters only\n"
                "🛑 **Do not disturb!** - Focus mode, please don't interrupt\n"
                "💤 **Need time** - Taking a break, will respond later\n\n"
                "*Click a reaction to update your status. Remove to clear.*"
            ),
            color=0x5865F2
        )
        embed.set_footer(text="Powered by ClickBot Team Mood System")
        return embed
```

## Cog Implementation

### New File: `cogs/team_mood_commands.py`

```python
import discord
from discord.ext import commands
from discord import app_commands
from services.team_mood_service import TeamMoodService
from utils.embed_factory import EmbedFactory
from utils.helpers import admin_only

class TeamMoodCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.team_mood_service = TeamMoodService()
        
    @app_commands.command(name="team-mood-setup", description="Set up the team mood status system")
    @app_commands.describe(channel="The channel to post the status message in (default: current channel)")
    @admin_only()
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
            result = await self.team_mood_service.setup_team_mood(
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
            embed = EmbedFactory.create_error_embed(
                "Setup Error",
                f"An unexpected error occurred: {str(e)}\n\n"
                f"Please check ClickBot's permissions and try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="team-mood-status", description="Check current team availability")
    async def team_mood_status(self, interaction: discord.Interaction):
        """Display current team member statuses"""
        # Implementation to show who has what status
        
    @app_commands.command(name="team-mood-remove", description="Remove the team mood system")
    @admin_only()
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
            embed = EmbedFactory.create_error_embed(
                "Removal Error",
                f"Failed to remove team mood system: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        
    @app_commands.command(name="team-mood-refresh", description="Refresh the team mood message")
    @admin_only()
    async def team_mood_refresh(self, interaction: discord.Interaction):
        """Recreate the team mood message if it was deleted"""
        # Implementation to recreate message

async def setup(bot):
    await bot.add_cog(TeamMoodCommands(bot))
```

## Integration Points

### 1. Modify `main.py` to load the new cog:

```python
# In the load_extensions method, add:
'cogs.team_mood_commands',
```

### 2. Update `cogs/reaction_roles.py` to handle mood status exclusivity:

```python
# Add method to check if a reaction role is part of team mood system
async def is_team_mood_role(self, guild_id: int, role_id: int) -> bool:
    """Check if a role is part of the team mood system"""
    config = await TeamMoodRepository.get_config(guild_id)
    if not config:
        return False
    
    mood_roles = [config.role_ready_id, config.role_phone_id, 
                  config.role_dnd_id, config.role_away_id]
    return role_id in mood_roles

# Add method to remove other mood roles when one is selected
async def remove_other_mood_roles(self, member: discord.Member, new_role: discord.Role):
    """Remove other mood roles when a new one is selected"""
    config = await TeamMoodRepository.get_config(member.guild.id)
    if not config:
        return
    
    mood_role_ids = [config.role_ready_id, config.role_phone_id, 
                     config.role_dnd_id, config.role_away_id]
    
    # Remove all mood roles except the new one
    for role in member.roles:
        if role.id in mood_role_ids and role.id != new_role.id:
            await member.remove_roles(role, reason="Team mood status change")

# In the on_raw_reaction_add handler, add special logic:
if await self.is_team_mood_role(guild.id, role.id):
    # Remove other mood roles first to ensure only one status
    await self.remove_other_mood_roles(member, role)
```

### 3. Add role position management:

```python
# In team_mood_service.py, add method to position roles correctly
@staticmethod
async def position_mood_roles(guild: discord.Guild, roles: Dict[str, discord.Role]):
    """Position mood roles together in the role hierarchy"""
    try:
        # Get ClickBot's highest role position
        bot_member = guild.me
        bot_top_role = bot_member.top_role
        
        # Position mood roles just below bot's role
        position = bot_top_role.position - 1
        
        # Create position mapping (reverse order so ready is on top)
        positions = {
            roles['ready']: position - 3,
            roles['phone']: position - 2,
            roles['dnd']: position - 1,
            roles['away']: position
        }
        
        # Update positions
        await guild.edit_role_positions(positions)
    except discord.Forbidden:
        # Continue even if we can't reposition roles
        pass
```

### 3. Add to `utils/embed_factory.py`:

```python
@staticmethod
def create_team_status_embed(status_counts: Dict[str, int]) -> discord.Embed:
    """Create an embed showing team availability statistics"""
    total = sum(status_counts.values())
    embed = discord.Embed(
        title="📊 Team Availability Status",
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(
        name="Current Status",
        value=(
            f"✅ Ready to Work: **{status_counts.get('ready', 0)}**\n"
            f"⚠️ Phone Only: **{status_counts.get('phone', 0)}**\n"
            f"🛑 Do Not Disturb: **{status_counts.get('dnd', 0)}**\n"
            f"💤 Need Time: **{status_counts.get('away', 0)}**\n"
            f"👥 Total Team: **{total}**"
        ),
        inline=False
    )
    
    return embed
```

## User Flow

### Setup Flow (Admin):
1. Admin runs `/team-mood-setup [channel]`
2. Bot automatically executes these steps:
   
   **Step 1: Role Creation**
   - Creates "Ready to Work" role (Green)
   - Creates "Phone Only" role (Yellow)
   - Creates "Do not disturb!" role (Red)
   - Creates "Need time" role (Gray)
   - Positions roles below ClickBot's role
   - If roles exist, updates their colors
   
   **Step 2: Message Creation**
   - Posts formatted embed with instructions
   - Adds all 4 reaction emojis automatically
   - Attempts to pin the message
   
   **Step 3: Reaction Role Configuration**
   - Links ✅ to "Ready to Work" role
   - Links ⚠️ to "Phone Only" role
   - Links 🛑 to "Do not disturb!" role
   - Links 💤 to "Need time" role
   - Sets all as non-exclusive (for proper removal)
   
   **Step 4: Database Storage**
   - Saves configuration to team_mood_config table
   - Links to existing reaction_role entries
   - Enables mood-exclusive behavior
   
3. Admin receives detailed success message showing:
   - Created role mentions
   - Channel where message was posted
   - Confirmation that system is active
4. System is ready for immediate use

### User Flow:
1. User sees pinned "Team Status Update" message
2. User clicks a reaction emoji (e.g., ✅)
3. Bot assigns "Ready to Work" role
4. If user had another mood role, it's automatically removed
5. User's status is visible in member list
6. To clear status, user removes their reaction

### Status Check Flow:
1. Team member runs `/team-mood-status`
2. Bot displays embed with:
   - Count of members in each status
   - List of who has what status (optional)
   - Percentage breakdown

## Error Handling

### Permission Errors:
- Check bot has Manage Roles permission before starting
- Verify bot role hierarchy allows role creation
- Provide clear error messages with specific missing permissions
- Suggest solutions (e.g., "Move ClickBot's role higher")

### Role Creation Errors:
```python
# In create_status_roles method
try:
    role = await guild.create_role(...)
except discord.Forbidden:
    raise Exception(f"Cannot create role '{config['name']}'. Please ensure ClickBot has 'Manage Roles' permission.")
except discord.HTTPException as e:
    if e.code == 30005:  # Max roles reached
        raise Exception(f"Server has reached maximum role limit (250). Please delete unused roles.")
    raise Exception(f"Failed to create role '{config['name']}': {str(e)}")
```

### Role Conflicts:
- Handle existing roles with same names gracefully
- Update existing roles rather than failing
- Option to use different role names if conflicts exist
- Cleanup orphaned roles from failed setups

### Message Deletion:
- Monitor for message deletion
- Provide refresh command to recreate
- Maintain database consistency
- Auto-cleanup reaction role entries

## Configuration Options

### Add to `ServerConfig` model:
```python
team_mood_enabled = Column(Boolean, default=False)
team_mood_ping_reminders = Column(Boolean, default=True)
team_mood_auto_clear_hours = Column(Integer, default=12)  # Auto-clear after X hours
```

## Testing Requirements

1. Test role creation with existing roles
2. Test reaction role assignment/removal
3. Test exclusive behavior between mood roles
4. Test persistence across bot restarts
5. Test cleanup when message is deleted
6. Test with missing permissions
7. Test status reporting accuracy

## Future Enhancements

1. **ClickUp Integration**: Sync status with ClickUp availability
2. **Scheduled Reminders**: Remind users to update status
3. **Analytics**: Track status patterns over time
4. **Auto-clear**: Clear status after X hours of inactivity
5. **Webhooks**: Send status updates to external systems
6. **Calendar Integration**: Sync with calendar events
7. **Custom Statuses**: Allow guilds to define their own statuses

## Documentation to Generate

1. User guide for team members
2. Admin setup guide
3. Troubleshooting guide
4. Integration guide with other ClickBot features

## Success Metrics

- Setup completes in under 30 seconds
- Zero manual steps required after command
- Clear error messages for all failure cases
- Persistent across bot restarts
- Handles 100+ team members efficiently