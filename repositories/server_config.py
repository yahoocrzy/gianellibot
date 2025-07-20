from typing import Optional, Dict, Any
from sqlalchemy import select, update
from database.models import ServerConfig, async_session
from loguru import logger

class ServerConfigRepository:
    def __init__(self):
        pass
    
    async def get_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get server configuration"""
        async with async_session() as session:
            result = await session.execute(
                select(ServerConfig).where(ServerConfig.guild_id == guild_id)
            )
            config = result.scalar_one_or_none()
            
            if config:
                return {
                    "guild_id": config.guild_id,
                    "prefix": config.prefix,
                    "claude_enabled": config.claude_enabled,
                    "setup_complete": config.setup_complete,
                    "config_data": config.config_data
                }
            return None
    
    async def save_config(
        self,
        guild_id: int,
        setup_complete: bool = True,
        **kwargs
    ) -> None:
        """Save or update server configuration"""
        async with async_session() as session:
            # Check if config exists
            result = await session.execute(
                select(ServerConfig).where(ServerConfig.guild_id == guild_id)
            )
            config = result.scalar_one_or_none()
            
            if config:
                # Update existing
                config.setup_complete = setup_complete
                if kwargs.get('config_data'):
                    config.config_data = kwargs['config_data']
            else:
                # Create new
                config = ServerConfig(
                    guild_id=guild_id,
                    setup_complete=setup_complete,
                    config_data=kwargs.get('config_data', {})
                )
                session.add(config)
            
            await session.commit()
            logger.info(f"Saved config for guild {guild_id}")
    
    async def update_prefix(self, guild_id: int, prefix: str) -> None:
        """Update server prefix"""
        async with async_session() as session:
            await session.execute(
                update(ServerConfig)
                .where(ServerConfig.guild_id == guild_id)
                .values(prefix=prefix)
            )
            await session.commit()
    
    async def delete_config(self, guild_id: int) -> None:
        """Delete server configuration"""
        async with async_session() as session:
            result = await session.execute(
                select(ServerConfig).where(ServerConfig.guild_id == guild_id)
            )
            config = result.scalar_one_or_none()
            if config:
                await session.delete(config)
                await session.commit()