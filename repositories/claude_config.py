from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import ClaudeConfig, async_session
from services.security import encrypt_token, decrypt_token
from loguru import logger

class ClaudeConfigRepository:
    """Repository for managing Claude AI configuration"""
    
    @staticmethod
    async def create_or_update_config(
        guild_id: int,
        api_key: str,
        added_by_user_id: int,
        model: str = "claude-3-opus-20240229",
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> ClaudeConfig:
        """Create or update Claude configuration for a guild"""
        async with async_session() as session:
            # Encrypt the API key
            encrypted_key = await encrypt_token(api_key)
            
            # Check if config exists
            result = await session.execute(
                select(ClaudeConfig).where(ClaudeConfig.guild_id == guild_id)
            )
            existing_config = result.scalar_one_or_none()
            
            if existing_config:
                # Update existing config
                existing_config.api_key_encrypted = encrypted_key
                existing_config.model = model
                existing_config.max_tokens = max_tokens
                existing_config.temperature = temperature
                existing_config.is_enabled = True
                existing_config.added_by_user_id = added_by_user_id
                
                await session.commit()
                await session.refresh(existing_config)
                
                logger.info(f"Updated Claude config for guild {guild_id}")
                return existing_config
            else:
                # Create new config
                config = ClaudeConfig(
                    guild_id=guild_id,
                    api_key_encrypted=encrypted_key,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    is_enabled=True,
                    added_by_user_id=added_by_user_id
                )
                
                session.add(config)
                await session.commit()
                await session.refresh(config)
                
                logger.info(f"Created Claude config for guild {guild_id}")
                return config
    
    @staticmethod
    async def get_config(guild_id: int) -> Optional[ClaudeConfig]:
        """Get Claude configuration for a guild"""
        async with async_session() as session:
            result = await session.execute(
                select(ClaudeConfig).where(
                    ClaudeConfig.guild_id == guild_id,
                    ClaudeConfig.is_enabled == True
                )
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def update_api_key(guild_id: int, new_api_key: str) -> bool:
        """Update the API key for a guild"""
        async with async_session() as session:
            encrypted_key = await encrypt_token(new_api_key)
            
            result = await session.execute(
                update(ClaudeConfig)
                .where(ClaudeConfig.guild_id == guild_id)
                .values(api_key_encrypted=encrypted_key)
            )
            
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def update_model_settings(
        guild_id: int,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> bool:
        """Update model settings for a guild"""
        async with async_session() as session:
            values = {}
            if model is not None:
                values['model'] = model
            if max_tokens is not None:
                values['max_tokens'] = max_tokens
            if temperature is not None:
                values['temperature'] = temperature
            
            if not values:
                return False
            
            result = await session.execute(
                update(ClaudeConfig)
                .where(ClaudeConfig.guild_id == guild_id)
                .values(**values)
            )
            
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def disable_claude(guild_id: int) -> bool:
        """Disable Claude for a guild"""
        async with async_session() as session:
            result = await session.execute(
                update(ClaudeConfig)
                .where(ClaudeConfig.guild_id == guild_id)
                .values(is_enabled=False)
            )
            
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def enable_claude(guild_id: int) -> bool:
        """Enable Claude for a guild"""
        async with async_session() as session:
            result = await session.execute(
                update(ClaudeConfig)
                .where(ClaudeConfig.guild_id == guild_id)
                .values(is_enabled=True)
            )
            
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def get_decrypted_api_key(config: ClaudeConfig) -> str:
        """Get the decrypted API key"""
        return await decrypt_token(config.api_key_encrypted)
    
    @staticmethod
    async def delete_config(guild_id: int) -> bool:
        """Delete Claude configuration for a guild"""
        async with async_session() as session:
            result = await session.execute(
                select(ClaudeConfig).where(ClaudeConfig.guild_id == guild_id)
            )
            config = result.scalar_one_or_none()
            
            if config:
                await session.delete(config)
                await session.commit()
                return True
            
            return False