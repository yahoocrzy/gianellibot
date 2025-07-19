from typing import Optional, List
from sqlalchemy import select, update, delete
from database.models import TeamMoodConfig, async_session
from datetime import datetime

class TeamMoodRepository:
    @staticmethod
    async def create_config(guild_id: int, channel_id: int, message_id: int, 
                          role_ready_id: int, role_phone_id: int, 
                          role_dnd_id: int, role_away_id: int) -> TeamMoodConfig:
        """Create or update team mood configuration"""
        async with async_session() as session:
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
            await session.refresh(config)
            return config
        
    @staticmethod
    async def get_config(guild_id: int) -> Optional[TeamMoodConfig]:
        """Get team mood configuration for a guild"""
        async with async_session() as session:
            stmt = select(TeamMoodConfig).where(
                TeamMoodConfig.guild_id == guild_id,
                TeamMoodConfig.enabled == True
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        
    @staticmethod
    async def delete_config(guild_id: int) -> bool:
        """Delete team mood configuration"""
        async with async_session() as session:
            stmt = update(TeamMoodConfig).where(
                TeamMoodConfig.guild_id == guild_id
            ).values(enabled=False, updated_at=datetime.utcnow())
            
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
            
    @staticmethod
    async def get_all_mood_roles(guild_id: int) -> List[int]:
        """Get all mood role IDs for checking"""
        config = await TeamMoodRepository.get_config(guild_id)
        if not config:
            return []
        
        roles = []
        if config.role_ready_id:
            roles.append(config.role_ready_id)
        if config.role_phone_id:
            roles.append(config.role_phone_id)
        if config.role_dnd_id:
            roles.append(config.role_dnd_id)
        if config.role_away_id:
            roles.append(config.role_away_id)
            
        return roles