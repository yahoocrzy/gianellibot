from typing import Optional, List
from sqlalchemy import select, delete
from database.models import ReactionRole, async_session
from datetime import datetime

class ReactionRoleRepository:
    @staticmethod
    async def create(guild_id: int, message_id: int, channel_id: int, 
                    emoji: str, role_id: int, exclusive: bool = False, 
                    embed_color: Optional[str] = None) -> ReactionRole:
        """Create a new reaction role mapping"""
        async with async_session() as session:
            reaction_role = ReactionRole(
                guild_id=guild_id,
                message_id=message_id,
                channel_id=channel_id,
                emoji=emoji,
                role_id=role_id,
                exclusive=exclusive,
                embed_color=embed_color
            )
            session.add(reaction_role)
            await session.commit()
            await session.refresh(reaction_role)
            return reaction_role
    
    @staticmethod
    async def get_by_message_and_emoji(guild_id: int, message_id: int, emoji: str) -> Optional[ReactionRole]:
        """Get reaction role by message and emoji"""
        async with async_session() as session:
            stmt = select(ReactionRole).where(
                ReactionRole.guild_id == guild_id,
                ReactionRole.message_id == message_id,
                ReactionRole.emoji == emoji
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_for_message(guild_id: int, message_id: int) -> List[ReactionRole]:
        """Get all reaction roles for a specific message"""
        async with async_session() as session:
            stmt = select(ReactionRole).where(
                ReactionRole.guild_id == guild_id,
                ReactionRole.message_id == message_id
            )
            result = await session.execute(stmt)
            return result.scalars().all()
    
    @staticmethod
    async def delete_by_message(guild_id: int, message_id: int) -> bool:
        """Delete all reaction roles for a message"""
        async with async_session() as session:
            stmt = delete(ReactionRole).where(
                ReactionRole.guild_id == guild_id,
                ReactionRole.message_id == message_id
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def delete_by_role(guild_id: int, role_id: int) -> bool:
        """Delete all reaction roles for a specific role"""
        async with async_session() as session:
            stmt = delete(ReactionRole).where(
                ReactionRole.guild_id == guild_id,
                ReactionRole.role_id == role_id
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0