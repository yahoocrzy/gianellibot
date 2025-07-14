from typing import Optional, List
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import ClickUpWorkspace, async_session
from services.security import encrypt_token, decrypt_token
from loguru import logger

class ClickUpWorkspaceRepository:
    """Repository for managing multiple ClickUp workspaces per server"""
    
    @staticmethod
    async def create_workspace(
        guild_id: int,
        workspace_id: str,
        workspace_name: str,
        token: str,
        added_by_user_id: int,
        is_default: bool = False
    ) -> ClickUpWorkspace:
        """Create a new workspace entry"""
        async with async_session() as session:
            # Encrypt the token
            encrypted_token = await encrypt_token(token)
            
            # If this is set as default, unset any existing default
            if is_default:
                await session.execute(
                    update(ClickUpWorkspace)
                    .where(and_(
                        ClickUpWorkspace.guild_id == guild_id,
                        ClickUpWorkspace.is_default == True
                    ))
                    .values(is_default=False)
                )
            
            # Create new workspace
            workspace = ClickUpWorkspace(
                guild_id=guild_id,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                token_encrypted=encrypted_token,
                added_by_user_id=added_by_user_id,
                is_default=is_default,
                is_active=True
            )
            
            session.add(workspace)
            await session.commit()
            await session.refresh(workspace)
            
            logger.info(f"Created workspace {workspace_name} ({workspace_id}) for guild {guild_id}")
            return workspace
    
    @staticmethod
    async def get_workspace(guild_id: int, workspace_id: str) -> Optional[ClickUpWorkspace]:
        """Get a specific workspace"""
        async with async_session() as session:
            result = await session.execute(
                select(ClickUpWorkspace).where(
                    and_(
                        ClickUpWorkspace.guild_id == guild_id,
                        ClickUpWorkspace.workspace_id == workspace_id,
                        ClickUpWorkspace.is_active == True
                    )
                )
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def get_default_workspace(guild_id: int) -> Optional[ClickUpWorkspace]:
        """Get the default workspace for a guild"""
        async with async_session() as session:
            result = await session.execute(
                select(ClickUpWorkspace).where(
                    and_(
                        ClickUpWorkspace.guild_id == guild_id,
                        ClickUpWorkspace.is_default == True,
                        ClickUpWorkspace.is_active == True
                    )
                )
            )
            workspace = result.scalar_one_or_none()
            
            # If no default, get the first active workspace
            if not workspace:
                result = await session.execute(
                    select(ClickUpWorkspace).where(
                        and_(
                            ClickUpWorkspace.guild_id == guild_id,
                            ClickUpWorkspace.is_active == True
                        )
                    ).order_by(ClickUpWorkspace.created_at)
                )
                workspace = result.scalar_one_or_none()
            
            return workspace
    
    @staticmethod
    async def get_all_workspaces(guild_id: int) -> List[ClickUpWorkspace]:
        """Get all active workspaces for a guild"""
        async with async_session() as session:
            result = await session.execute(
                select(ClickUpWorkspace).where(
                    and_(
                        ClickUpWorkspace.guild_id == guild_id,
                        ClickUpWorkspace.is_active == True
                    )
                ).order_by(ClickUpWorkspace.workspace_name)
            )
            return result.scalars().all()
    
    @staticmethod
    async def set_default_workspace(guild_id: int, workspace_id: str) -> bool:
        """Set a workspace as default"""
        async with async_session() as session:
            # Unset current default
            await session.execute(
                update(ClickUpWorkspace)
                .where(and_(
                    ClickUpWorkspace.guild_id == guild_id,
                    ClickUpWorkspace.is_default == True
                ))
                .values(is_default=False)
            )
            
            # Set new default
            result = await session.execute(
                update(ClickUpWorkspace)
                .where(and_(
                    ClickUpWorkspace.guild_id == guild_id,
                    ClickUpWorkspace.workspace_id == workspace_id,
                    ClickUpWorkspace.is_active == True
                ))
                .values(is_default=True)
            )
            
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def update_workspace_token(guild_id: int, workspace_id: str, new_token: str) -> bool:
        """Update the token for a workspace"""
        async with async_session() as session:
            encrypted_token = await encrypt_token(new_token)
            
            result = await session.execute(
                update(ClickUpWorkspace)
                .where(and_(
                    ClickUpWorkspace.guild_id == guild_id,
                    ClickUpWorkspace.workspace_id == workspace_id
                ))
                .values(token_encrypted=encrypted_token)
            )
            
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def deactivate_workspace(guild_id: int, workspace_id: str) -> bool:
        """Deactivate a workspace (soft delete)"""
        async with async_session() as session:
            result = await session.execute(
                update(ClickUpWorkspace)
                .where(and_(
                    ClickUpWorkspace.guild_id == guild_id,
                    ClickUpWorkspace.workspace_id == workspace_id
                ))
                .values(is_active=False, is_default=False)
            )
            
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def get_decrypted_token(workspace: ClickUpWorkspace) -> str:
        """Get the decrypted token for a workspace"""
        return await decrypt_token(workspace.token_encrypted)
    
    @staticmethod
    async def workspace_exists(guild_id: int, workspace_id: str) -> bool:
        """Check if a workspace already exists"""
        async with async_session() as session:
            result = await session.execute(
                select(ClickUpWorkspace).where(
                    and_(
                        ClickUpWorkspace.guild_id == guild_id,
                        ClickUpWorkspace.workspace_id == workspace_id
                    )
                )
            )
            return result.scalar_one_or_none() is not None