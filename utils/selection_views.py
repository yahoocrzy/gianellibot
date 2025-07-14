import discord
from typing import Dict, Any, List, Optional, Callable
from services.clickup_api import ClickUpAPI
from loguru import logger

class ClickUpSelectionView(discord.ui.View):
    """Base class for ClickUp entity selection views"""
    
    def __init__(self, api: ClickUpAPI, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.api = api
        self.selected_value = None
        self.callback_func: Optional[Callable] = None
    
    def set_callback(self, callback: Callable):
        """Set callback function to execute when selection is made"""
        self.callback_func = callback

class WorkspaceSelectView(ClickUpSelectionView):
    """Dropdown for selecting ClickUp workspace"""
    
    def __init__(self, api: ClickUpAPI, workspaces: List[Dict[str, Any]], **kwargs):
        super().__init__(api, **kwargs)
        
        # Create dropdown options (Discord limit: 25)
        options = []
        for workspace in workspaces[:25]:
            options.append(discord.SelectOption(
                label=workspace['name'][:100],  # Discord limit: 100 chars
                value=workspace['id'],
                description=f"ID: {workspace['id']}"[:100]
            ))
        
        self.workspace_select = discord.ui.Select(
            placeholder="Choose a workspace...",
            options=options,
            min_values=1,
            max_values=1
        )
        self.workspace_select.callback = self.workspace_callback
        self.add_item(self.workspace_select)
    
    async def workspace_callback(self, interaction: discord.Interaction):
        self.selected_value = self.workspace_select.values[0]
        
        if self.callback_func:
            await self.callback_func(interaction, self.selected_value)
        else:
            await interaction.response.send_message(
                f"Selected workspace: {self.selected_value}", 
                ephemeral=True
            )

class SpaceSelectView(ClickUpSelectionView):
    """Dropdown for selecting ClickUp space"""
    
    def __init__(self, api: ClickUpAPI, workspace_id: str, **kwargs):
        super().__init__(api, **kwargs)
        self.workspace_id = workspace_id
        
        # Add a button to load spaces
        self.load_button = discord.ui.Button(
            label="Load Spaces",
            style=discord.ButtonStyle.primary
        )
        self.load_button.callback = self.load_spaces
        self.add_item(self.load_button)
    
    async def load_spaces(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            spaces = await self.api.get_spaces(self.workspace_id)
            
            if not spaces:
                await interaction.followup.send("No spaces found in this workspace.", ephemeral=True)
                return
            
            # Create dropdown options
            options = []
            for space in spaces[:25]:
                options.append(discord.SelectOption(
                    label=space['name'][:100],
                    value=space['id'],
                    description=f"ID: {space['id']}"[:100]
                ))
            
            self.space_select = discord.ui.Select(
                placeholder="Choose a space...",
                options=options,
                min_values=1,
                max_values=1
            )
            self.space_select.callback = self.space_callback
            
            # Remove load button and add select
            self.clear_items()
            self.add_item(self.space_select)
            
            await interaction.edit_original_response(
                content="Select a space:",
                view=self
            )
            
        except Exception as e:
            logger.error(f"Failed to load spaces: {e}")
            await interaction.followup.send(f"Failed to load spaces: {str(e)}", ephemeral=True)
    
    async def space_callback(self, interaction: discord.Interaction):
        self.selected_value = self.space_select.values[0]
        
        if self.callback_func:
            await self.callback_func(interaction, self.selected_value)
        else:
            await interaction.response.send_message(
                f"Selected space: {self.selected_value}", 
                ephemeral=True
            )

class ListSelectView(ClickUpSelectionView):
    """Dropdown for selecting ClickUp list"""
    
    def __init__(self, api: ClickUpAPI, space_id: str, **kwargs):
        super().__init__(api, **kwargs)
        self.space_id = space_id
        
        # Add a button to load lists
        self.load_button = discord.ui.Button(
            label="Load Lists",
            style=discord.ButtonStyle.primary
        )
        self.load_button.callback = self.load_lists
        self.add_item(self.load_button)
    
    async def load_lists(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            # Get both folderless lists and lists in folders
            folderless_lists = await self.api.get_folderless_lists(self.space_id)
            folders = await self.api.get_folders(self.space_id)
            
            all_lists = []
            
            # Add folderless lists
            for lst in folderless_lists:
                all_lists.append({
                    'id': lst['id'],
                    'name': lst['name'],
                    'folder': 'No Folder'
                })
            
            # Get lists from folders
            for folder in folders:
                try:
                    folder_lists = await self.api.get_lists(folder['id'])
                    for lst in folder_lists:
                        all_lists.append({
                            'id': lst['id'],
                            'name': lst['name'],
                            'folder': folder['name']
                        })
                except Exception as e:
                    logger.warning(f"Failed to get lists from folder {folder['id']}: {e}")
            
            if not all_lists:
                await interaction.followup.send("No lists found in this space.", ephemeral=True)
                return
            
            # Create dropdown options
            options = []
            for lst in all_lists[:25]:
                folder_info = f" ({lst['folder']})" if lst['folder'] != 'No Folder' else ""
                options.append(discord.SelectOption(
                    label=f"{lst['name']}{folder_info}"[:100],
                    value=lst['id'],
                    description=f"ID: {lst['id']}"[:100]
                ))
            
            self.list_select = discord.ui.Select(
                placeholder="Choose a list...",
                options=options,
                min_values=1,
                max_values=1
            )
            self.list_select.callback = self.list_callback
            
            # Remove load button and add select
            self.clear_items()
            self.add_item(self.list_select)
            
            await interaction.edit_original_response(
                content=f"Select a list (found {len(all_lists)} lists):",
                view=self
            )
            
        except Exception as e:
            logger.error(f"Failed to load lists: {e}")
            await interaction.followup.send(f"Failed to load lists: {str(e)}", ephemeral=True)
    
    async def list_callback(self, interaction: discord.Interaction):
        self.selected_value = self.list_select.values[0]
        
        if self.callback_func:
            await self.callback_func(interaction, self.selected_value)
        else:
            await interaction.response.send_message(
                f"Selected list: {self.selected_value}", 
                ephemeral=True
            )

class TaskSelectView(ClickUpSelectionView):
    """Dropdown for selecting ClickUp task"""
    
    def __init__(self, api: ClickUpAPI, list_id: str, **kwargs):
        super().__init__(api, **kwargs)
        self.list_id = list_id
        
        # Add a button to load tasks
        self.load_button = discord.ui.Button(
            label="Load Tasks",
            style=discord.ButtonStyle.primary
        )
        self.load_button.callback = self.load_tasks
        self.add_item(self.load_button)
    
    async def load_tasks(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            tasks = await self.api.get_tasks(self.list_id)
            
            if not tasks:
                await interaction.followup.send("No tasks found in this list.", ephemeral=True)
                return
            
            # Create dropdown options
            options = []
            for task in tasks[:25]:
                status = task.get('status', {}).get('status', 'Unknown')
                options.append(discord.SelectOption(
                    label=f"{task['name']}"[:100],
                    value=task['id'],
                    description=f"Status: {status} | ID: {task['id']}"[:100]
                ))
            
            self.task_select = discord.ui.Select(
                placeholder="Choose a task...",
                options=options,
                min_values=1,
                max_values=1
            )
            self.task_select.callback = self.task_callback
            
            # Remove load button and add select
            self.clear_items()
            self.add_item(self.task_select)
            
            await interaction.edit_original_response(
                content=f"Select a task (found {len(tasks)} tasks):",
                view=self
            )
            
        except Exception as e:
            logger.error(f"Failed to load tasks: {e}")
            await interaction.followup.send(f"Failed to load tasks: {str(e)}", ephemeral=True)
    
    async def task_callback(self, interaction: discord.Interaction):
        self.selected_value = self.task_select.values[0]
        
        if self.callback_func:
            await self.callback_func(interaction, self.selected_value)
        else:
            await interaction.response.send_message(
                f"Selected task: {self.selected_value}", 
                ephemeral=True
            )

class MemberSelectView(ClickUpSelectionView):
    """Dropdown for selecting ClickUp team member"""
    
    def __init__(self, api: ClickUpAPI, workspace_id: str, **kwargs):
        super().__init__(api, **kwargs)
        self.workspace_id = workspace_id
        
        # Add a button to load members
        self.load_button = discord.ui.Button(
            label="Load Members",
            style=discord.ButtonStyle.primary
        )
        self.load_button.callback = self.load_members
        self.add_item(self.load_button)
    
    async def load_members(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            members = await self.api.get_members(self.workspace_id)
            
            if not members:
                await interaction.followup.send("No members found in this workspace.", ephemeral=True)
                return
            
            # Create dropdown options
            options = []
            for member in members[:25]:
                user = member.get('user', {})
                username = user.get('username', 'Unknown')
                email = user.get('email', '')
                options.append(discord.SelectOption(
                    label=username[:100],
                    value=str(user.get('id', '')),
                    description=f"Email: {email}"[:100] if email else f"ID: {user.get('id', '')}"[:100]
                ))
            
            self.member_select = discord.ui.Select(
                placeholder="Choose a member...",
                options=options,
                min_values=1,
                max_values=1
            )
            self.member_select.callback = self.member_callback
            
            # Remove load button and add select
            self.clear_items()
            self.add_item(self.member_select)
            
            await interaction.edit_original_response(
                content=f"Select a member (found {len(members)} members):",
                view=self
            )
            
        except Exception as e:
            logger.error(f"Failed to load members: {e}")
            await interaction.followup.send(f"Failed to load members: {str(e)}", ephemeral=True)
    
    async def member_callback(self, interaction: discord.Interaction):
        self.selected_value = self.member_select.values[0]
        
        if self.callback_func:
            await self.callback_func(interaction, self.selected_value)
        else:
            await interaction.response.send_message(
                f"Selected member: {self.selected_value}", 
                ephemeral=True
            )