from typing import Optional, List, Dict, Any
from sqlalchemy import select, delete
from database.models import ReactionRole, async_session
from loguru import logger

class ReactionRoleRepository:
    def __init__(self):
        pass
    
    async def add_reaction_role(
        self,
        guild_id: int,
        message_id: int,
        channel_id: int,
        emoji: str,
        role_id: int,
        exclusive: bool = False
    ) -> None:
        """Add a reaction role mapping"""
        async with async_session() as session:
            reaction_role = ReactionRole(
                guild_id=guild_id,
                message_id=message_id,
                channel_id=channel_id,
                emoji=emoji,
                role_id=role_id,
                exclusive=exclusive
            )
            session.add(reaction_role)
            await session.commit()
            logger.info(f"Added reaction role mapping for guild {guild_id}")
    
    async def get_reaction_roles(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all reaction roles for a guild"""
        async with async_session() as session:
            result = await session.execute(
                select(ReactionRole).where(ReactionRole.guild_id == guild_id)
            )
            roles = result.scalars().all()
            
            return [
                {
                    "id": role.id,
                    "guild_id": role.guild_id,
                    "message_id": role.message_id,
                    "channel_id": role.channel_id,
                    "emoji": role.emoji,
                    "role_id": role.role_id,
                    "exclusive": role.exclusive
                }
                for role in roles
            ]
    
    async def get_reaction_role_by_message_emoji(
        self,
        message_id: int,
        emoji: str
    ) -> Optional[Dict[str, Any]]:
        """Get reaction role by message and emoji"""
        async with async_session() as session:
            result = await session.execute(
                select(ReactionRole).where(
                    ReactionRole.message_id == message_id,
                    ReactionRole.emoji == emoji
                )
            )
            role = result.scalar_one_or_none()
            
            if role:
                return {
                    "id": role.id,
                    "guild_id": role.guild_id,
                    "message_id": role.message_id,
                    "channel_id": role.channel_id,
                    "emoji": role.emoji,
                    "role_id": role.role_id,
                    "exclusive": role.exclusive
                }
            return None
    
    async def remove_reaction_role(self, reaction_role_id: int) -> None:
        """Remove a reaction role mapping"""
        async with async_session() as session:
            await session.execute(
                delete(ReactionRole).where(ReactionRole.id == reaction_role_id)
            )
            await session.commit()
    
    async def remove_reaction_roles_by_message(self, message_id: int) -> None:
        """Remove all reaction roles for a message"""
        async with async_session() as session:
            await session.execute(
                delete(ReactionRole).where(ReactionRole.message_id == message_id)
            )
            await session.commit()