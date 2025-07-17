from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import async_session, ClickUpWorkspace, ClickUpOAuthState
from services.clickup_oauth import clickup_oauth
from loguru import logger

class ClickUpOAuthWorkspaceRepository:
    """Repository for managing ClickUp OAuth2 workspaces"""
    
    @staticmethod
    async def create_oauth_state(guild_id: int, user_id: int) -> tuple[str, str]:
        """Create OAuth2 state for security and return state and auth URL"""
        try:
            # Generate state and auth URL
            auth_url, state = clickup_oauth.generate_auth_url()
            
            # Store state in database
            async with async_session() as session:
                # Clean up expired states first
                await ClickUpOAuthWorkspaceRepository.cleanup_expired_states(session)
                
                oauth_state = ClickUpOAuthState(
                    state=state,
                    guild_id=guild_id,
                    user_id=user_id,
                    expires_at=datetime.utcnow() + timedelta(minutes=10)
                )
                session.add(oauth_state)
                await session.commit()
                
                logger.info(f"Created OAuth state for guild {guild_id}, user {user_id}")
                return state, auth_url
                
        except Exception as e:
            logger.error(f"Error creating OAuth state: {e}")
            raise
    
    @staticmethod
    async def validate_oauth_state(state: str) -> Optional[tuple[int, int]]:
        """Validate OAuth2 state and return guild_id, user_id if valid"""
        try:
            async with async_session() as session:
                # Find and validate state
                stmt = select(ClickUpOAuthState).where(
                    and_(
                        ClickUpOAuthState.state == state,
                        ClickUpOAuthState.expires_at > datetime.utcnow()
                    )
                )
                result = await session.execute(stmt)
                oauth_state = result.scalar_one_or_none()
                
                if oauth_state:
                    guild_id = oauth_state.guild_id
                    user_id = oauth_state.user_id
                    
                    # Delete used state
                    await session.delete(oauth_state)
                    await session.commit()
                    
                    logger.info(f"Validated OAuth state for guild {guild_id}, user {user_id}")
                    return guild_id, user_id
                else:
                    logger.warning(f"Invalid or expired OAuth state: {state}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error validating OAuth state: {e}")
            return None
    
    @staticmethod
    async def cleanup_expired_states(session: AsyncSession):
        """Clean up expired OAuth states"""
        try:
            stmt = select(ClickUpOAuthState).where(
                ClickUpOAuthState.expires_at <= datetime.utcnow()
            )
            result = await session.execute(stmt)
            expired_states = result.scalars().all()
            
            for state in expired_states:
                await session.delete(state)
                
            if expired_states:
                logger.info(f"Cleaned up {len(expired_states)} expired OAuth states")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired states: {e}")
    
    @staticmethod
    async def save_workspace_from_oauth(
        guild_id: int, 
        user_id: int, 
        access_token: str, 
        workspaces: List[dict]
    ) -> List[ClickUpWorkspace]:
        """Save workspaces from OAuth2 authorization"""
        try:
            async with async_session() as session:
                saved_workspaces = []
                
                for workspace_data in workspaces:
                    workspace_id = workspace_data.get('id')
                    workspace_name = workspace_data.get('name')
                    
                    if not workspace_id or not workspace_name:
                        continue
                    
                    # Check if workspace already exists for this guild
                    stmt = select(ClickUpWorkspace).where(
                        and_(
                            ClickUpWorkspace.guild_id == guild_id,
                            ClickUpWorkspace.workspace_id == workspace_id
                        )
                    )
                    result = await session.execute(stmt)
                    existing_workspace = result.scalar_one_or_none()
                    
                    if existing_workspace:
                        # Update existing workspace with new token
                        existing_workspace.access_token = access_token
                        existing_workspace.workspace_name = workspace_name
                        existing_workspace.is_active = True
                        existing_workspace.authorized_at = datetime.utcnow()
                        existing_workspace.updated_at = datetime.utcnow()
                        saved_workspaces.append(existing_workspace)
                        logger.info(f"Updated existing workspace {workspace_name} for guild {guild_id}")
                    else:
                        # Create new workspace
                        workspace = ClickUpWorkspace(
                            guild_id=guild_id,
                            workspace_id=workspace_id,
                            workspace_name=workspace_name,
                            access_token=access_token,
                            added_by_user_id=user_id
                        )
                        session.add(workspace)
                        saved_workspaces.append(workspace)
                        logger.info(f"Created new workspace {workspace_name} for guild {guild_id}")
                
                # Set first workspace as default if no default exists
                if saved_workspaces:
                    default_check = select(ClickUpWorkspace).where(
                        and_(
                            ClickUpWorkspace.guild_id == guild_id,
                            ClickUpWorkspace.is_default == True
                        )
                    )
                    result = await session.execute(default_check)
                    has_default = result.scalar_one_or_none()
                    
                    if not has_default and saved_workspaces:
                        saved_workspaces[0].is_default = True
                        logger.info(f"Set {saved_workspaces[0].workspace_name} as default workspace")
                
                await session.commit()
                return saved_workspaces
                
        except Exception as e:
            logger.error(f"Error saving workspaces from OAuth: {e}")
            raise
    
    @staticmethod
    async def get_all_workspaces(guild_id: int) -> List[ClickUpWorkspace]:
        """Get all workspaces for a guild"""
        try:
            async with async_session() as session:
                stmt = select(ClickUpWorkspace).where(
                    and_(
                        ClickUpWorkspace.guild_id == guild_id,
                        ClickUpWorkspace.is_active == True
                    )
                ).order_by(ClickUpWorkspace.is_default.desc(), ClickUpWorkspace.created_at)
                
                result = await session.execute(stmt)
                workspaces = result.scalars().all()
                return list(workspaces)
                
        except Exception as e:
            logger.error(f"Error getting workspaces for guild {guild_id}: {e}")
            return []
    
    @staticmethod
    async def get_default_workspace(guild_id: int) -> Optional[ClickUpWorkspace]:
        """Get the default workspace for a guild"""
        try:
            async with async_session() as session:
                # First try to get explicitly set default
                stmt = select(ClickUpWorkspace).where(
                    and_(
                        ClickUpWorkspace.guild_id == guild_id,
                        ClickUpWorkspace.is_default == True,
                        ClickUpWorkspace.is_active == True
                    )
                )
                result = await session.execute(stmt)
                workspace = result.scalar_one_or_none()
                
                if workspace:
                    return workspace
                
                # If no default set, get the first active workspace
                stmt = select(ClickUpWorkspace).where(
                    and_(
                        ClickUpWorkspace.guild_id == guild_id,
                        ClickUpWorkspace.is_active == True
                    )
                ).order_by(ClickUpWorkspace.created_at)
                
                result = await session.execute(stmt)
                workspace = result.scalar_one_or_none()
                return workspace
                
        except Exception as e:
            logger.error(f"Error getting default workspace for guild {guild_id}: {e}")
            return None
    
    @staticmethod
    async def set_default_workspace(guild_id: int, workspace_db_id: int) -> bool:
        """Set a workspace as the default for a guild"""
        try:
            async with async_session() as session:
                # Remove default from all workspaces in this guild
                stmt = select(ClickUpWorkspace).where(
                    and_(
                        ClickUpWorkspace.guild_id == guild_id,
                        ClickUpWorkspace.is_active == True
                    )
                )
                result = await session.execute(stmt)
                workspaces = result.scalars().all()
                
                for workspace in workspaces:
                    workspace.is_default = (workspace.id == workspace_db_id)
                
                await session.commit()
                logger.info(f"Set workspace {workspace_db_id} as default for guild {guild_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error setting default workspace: {e}")
            return False
    
    @staticmethod
    async def remove_workspace(workspace_db_id: int) -> bool:
        """Remove a workspace"""
        try:
            async with async_session() as session:
                stmt = select(ClickUpWorkspace).where(ClickUpWorkspace.id == workspace_db_id)
                result = await session.execute(stmt)
                workspace = result.scalar_one_or_none()
                
                if workspace:
                    await session.delete(workspace)
                    await session.commit()
                    logger.info(f"Removed workspace {workspace.workspace_name}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error removing workspace: {e}")
            return False
    
    @staticmethod
    async def get_access_token(workspace: ClickUpWorkspace) -> Optional[str]:
        """Get access token for a workspace (OAuth2 tokens don't need decryption)"""
        try:
            if workspace and workspace.access_token:
                # Test token validity
                is_valid = await clickup_oauth.test_token(workspace.access_token)
                if is_valid:
                    return workspace.access_token
                else:
                    logger.warning(f"Access token for workspace {workspace.workspace_name} is invalid")
                    return None
            return None
            
        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return None
    
    @staticmethod
    async def get_best_token(workspace: ClickUpWorkspace) -> Optional[str]:
        """Get the best available token: personal API token if available, otherwise OAuth2 token"""
        try:
            # Try personal API token first (full access)
            if workspace and workspace.personal_api_token:
                logger.info(f"Using personal API token for workspace {workspace.workspace_name}")
                return workspace.personal_api_token
            
            # Fall back to OAuth2 token
            if workspace and workspace.access_token:
                is_valid = await clickup_oauth.test_token(workspace.access_token)
                if is_valid:
                    logger.info(f"Using OAuth2 token for workspace {workspace.workspace_name}")
                    return workspace.access_token
                else:
                    logger.warning(f"OAuth2 token for workspace {workspace.workspace_name} is invalid")
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting best token: {e}")
            return None
    
    @staticmethod
    async def set_personal_api_token(workspace_db_id: int, personal_token: str) -> bool:
        """Set personal API token for a workspace"""
        try:
            async with async_session() as session:
                stmt = select(ClickUpWorkspace).where(ClickUpWorkspace.id == workspace_db_id)
                result = await session.execute(stmt)
                workspace = result.scalar_one_or_none()
                
                if workspace:
                    workspace.personal_api_token = personal_token
                    workspace.updated_at = datetime.utcnow()
                    await session.commit()
                    logger.info(f"Set personal API token for workspace {workspace.workspace_name}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error setting personal API token: {e}")
            return False