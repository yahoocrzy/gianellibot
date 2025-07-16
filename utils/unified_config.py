"""
Unified configuration system that handles ClickUp workspace configurations
"""
from typing import Optional
from services.clickup_api import ClickUpAPI
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from repositories.server_config import ServerConfigRepository
from loguru import logger

class UnifiedConfigManager:
    """Manages ClickUp workspace configuration system"""
    
    @staticmethod
    async def get_clickup_api(guild_id: int) -> Optional[ClickUpAPI]:
        """
        Get ClickUp API instance from the workspace system
        Returns None if no workspace is configured
        """
        try:
            # Only use the new workspace system
            workspace = await ClickUpWorkspaceRepository.get_default_workspace(guild_id)
            if workspace:
                try:
                    token = await ClickUpWorkspaceRepository.get_decrypted_token(workspace)
                    api = ClickUpAPI(token)
                    # Test the API quickly with proper session management
                    async with api:
                        await api.get_workspaces()
                    # Return a new instance since we closed the test one
                    return ClickUpAPI(token)
                except Exception as e:
                    logger.warning(f"Workspace system failed for guild {guild_id}: {e}")
            
            logger.info(f"No working ClickUp configuration found for guild {guild_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error in unified config manager for guild {guild_id}: {e}")
            return None
    
    @staticmethod
    async def has_any_configuration(guild_id: int) -> bool:
        """Check if guild has ClickUp workspace configuration"""
        try:
            # Only check the new workspace system
            workspace = await ClickUpWorkspaceRepository.get_default_workspace(guild_id)
            return workspace is not None
            
        except Exception as e:
            logger.error(f"Error checking configuration for guild {guild_id}: {e}")
            return False
    
    @staticmethod
    async def migrate_legacy_to_new(guild_id: int, user_id: int) -> bool:
        """
        Migrate legacy ServerConfig to new ClickUpWorkspace system
        Returns True if migration was successful
        """
        try:
            # Check if already has new system
            existing_workspace = await ClickUpWorkspaceRepository.get_default_workspace(guild_id)
            if existing_workspace:
                logger.info(f"Guild {guild_id} already has new workspace system")
                return True
            
            # Get old configuration
            server_repo = ServerConfigRepository()
            config = await server_repo.get_config(guild_id)
            if not config or not config.get('clickup_token_encrypted'):
                logger.info(f"No legacy configuration found for guild {guild_id}")
                return False
            
            # Decrypt old token
            from services.security import decrypt_token
            token = await decrypt_token(config['clickup_token_encrypted'])
            
            # Test token and get workspace info
            api = ClickUpAPI(token)
            workspaces = await api.get_workspaces()
            
            if not workspaces:
                logger.error(f"No workspaces found with legacy token for guild {guild_id}")
                return False
            
            # Find the workspace that matches the old config
            target_workspace = None
            if config.get('clickup_workspace_id'):
                # Find workspace by ID
                target_workspace = next(
                    (ws for ws in workspaces if ws['id'] == config['clickup_workspace_id']), 
                    None
                )
            
            # If no specific workspace or not found, use first one
            if not target_workspace:
                target_workspace = workspaces[0]
            
            # Create new workspace configuration
            new_workspace = await ClickUpWorkspaceRepository.create_workspace(
                guild_id=guild_id,
                workspace_id=target_workspace['id'],
                workspace_name=target_workspace['name'],
                token=token,
                added_by_user_id=user_id
            )
            
            if new_workspace:
                # Set as default
                await ClickUpWorkspaceRepository.set_default_workspace(guild_id, new_workspace.id)
                
                # Clear old configuration (optional - could keep for backup)
                # await server_repo.clear_clickup_config(guild_id)
                
                logger.info(f"Successfully migrated guild {guild_id} from legacy to new system")
                return True
            else:
                logger.error(f"Failed to create new workspace for guild {guild_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error migrating guild {guild_id}: {e}")
            return False
    
    @staticmethod
    async def get_configuration_status(guild_id: int) -> dict:
        """Get detailed status of workspace configuration"""
        status = {
            "has_workspace": False,
            "default_workspace": None,
            "working_api": False,
            "recommendation": "setup_required"
        }
        
        try:
            # Check workspace system
            workspace = await ClickUpWorkspaceRepository.get_default_workspace(guild_id)
            if workspace:
                status["has_workspace"] = True
                status["default_workspace"] = {
                    "id": workspace.workspace_id,
                    "name": workspace.workspace_name
                }
            
            # Test if we can get a working API
            api = await UnifiedConfigManager.get_clickup_api(guild_id)
            if api:
                status["working_api"] = True
                status["recommendation"] = "all_good"
            else:
                if status["has_workspace"]:
                    status["recommendation"] = "token_invalid"
                else:
                    status["recommendation"] = "setup_required"
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting configuration status for guild {guild_id}: {e}")
            status["recommendation"] = "error"
            return status