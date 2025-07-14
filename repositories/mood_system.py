from sqlalchemy import Column, Integer, BigInteger, JSON, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from database.models import Base, async_session
from sqlalchemy import select, update, delete
from typing import Optional, Dict, Any
from loguru import logger

class MoodSystemConfig(Base):
    __tablename__ = "mood_system_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id = Column(BigInteger, nullable=False, unique=True)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=False)
    mood_roles = Column(JSON, nullable=False)  # {emoji: role_id}
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MoodSystemRepository:
    """Repository for mood system configuration"""
    
    @staticmethod
    async def create_or_update_config(
        guild_id: int,
        channel_id: int,
        message_id: int,
        mood_roles: Dict[str, int]
    ) -> Optional[MoodSystemConfig]:
        """Create or update mood system configuration"""
        try:
            async with async_session() as session:
                # Check if config exists
                result = await session.execute(
                    select(MoodSystemConfig).where(MoodSystemConfig.guild_id == guild_id)
                )
                existing_config = result.scalar_one_or_none()
                
                if existing_config:
                    # Update existing
                    existing_config.channel_id = channel_id
                    existing_config.message_id = message_id
                    existing_config.mood_roles = mood_roles
                    existing_config.is_active = True
                    existing_config.updated_at = datetime.utcnow()
                    
                    await session.commit()
                    await session.refresh(existing_config)
                    return existing_config
                else:
                    # Create new
                    config = MoodSystemConfig(
                        guild_id=guild_id,
                        channel_id=channel_id,
                        message_id=message_id,
                        mood_roles=mood_roles,
                        is_active=True
                    )
                    
                    session.add(config)
                    await session.commit()
                    await session.refresh(config)
                    return config
                    
        except Exception as e:
            logger.error(f"Error creating/updating mood system config: {e}")
            return None
    
    @staticmethod
    async def get_config(guild_id: int) -> Optional[MoodSystemConfig]:
        """Get mood system configuration for a guild"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(MoodSystemConfig).where(
                        MoodSystemConfig.guild_id == guild_id,
                        MoodSystemConfig.is_active == True
                    )
                )
                return result.scalar_one_or_none()
                
        except Exception as e:
            logger.error(f"Error getting mood system config: {e}")
            return None
    
    @staticmethod
    async def remove_config(guild_id: int) -> bool:
        """Remove mood system configuration"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    delete(MoodSystemConfig).where(MoodSystemConfig.guild_id == guild_id)
                )
                await session.commit()
                return result.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error removing mood system config: {e}")
            return False
    
    @staticmethod
    async def deactivate_config(guild_id: int) -> bool:
        """Deactivate mood system without deleting"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    update(MoodSystemConfig)
                    .where(MoodSystemConfig.guild_id == guild_id)
                    .values(is_active=False, updated_at=datetime.utcnow())
                )
                await session.commit()
                return result.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error deactivating mood system config: {e}")
            return False
    
    @staticmethod
    async def get_all_active_configs() -> list[MoodSystemConfig]:
        """Get all active mood system configurations"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(MoodSystemConfig).where(MoodSystemConfig.is_active == True)
                )
                return result.scalars().all()
                
        except Exception as e:
            logger.error(f"Error getting all mood system configs: {e}")
            return []