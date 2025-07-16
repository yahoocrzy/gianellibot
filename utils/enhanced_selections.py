import discord
from typing import Optional, List, Dict
from services.clickup_api import ClickUpAPI
from repositories.clickup_oauth_workspaces import ClickUpOAuthWorkspaceRepository
from utils.embed_factory import EmbedFactory
from loguru import logger

class ListSelectView(discord.ui.View):
    """Interactive list selection with workspace -> space -> folder -> list hierarchy"""
    
    def __init__(self, api: ClickUpAPI, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.api = api
        self.selected_list_id = None
        self.selected_list_name = None
        self.current_workspace = None
        self.current_space = None
        
    async def start(self, interaction: discord.Interaction):
        """Start the selection process"""
        try:
            # Use the default workspace instead of checking all API workspaces
            default_workspace = await ClickUpOAuthWorkspaceRepository.get_default_workspace(interaction.guild_id)
            if not default_workspace:
                embed = EmbedFactory.create_error_embed(
                    "No Default Workspace",
                    "No default workspace set. Run `/clickup-setup` first."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Use the configured default workspace directly
            self.current_workspace = {'id': default_workspace.workspace_id, 'name': default_workspace.workspace_name}
            await self.show_spaces(interaction)
                
        except Exception as e:
            logger.error(f"Error in list selection: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error",
                f"Failed to load workspaces: {str(e)}"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def show_workspaces(self, interaction: discord.Interaction, workspaces: List[Dict]):
        """Show workspace selection dropdown"""
        self.clear_items()
        
        options = []
        for ws in workspaces[:25]:  # Discord limit
            options.append(
                discord.SelectOption(
                    label=ws['name'],
                    value=ws['id'],
                    description=f"ID: {ws['id']}"
                )
            )
        
        select = discord.ui.Select(
            placeholder="Choose a workspace...",
            options=options
        )
        select.callback = self.workspace_callback
        self.add_item(select)
        
        embed = EmbedFactory.create_info_embed(
            "Select Workspace",
            "Choose a workspace to browse:"
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def workspace_callback(self, interaction: discord.Interaction):
        """Handle workspace selection"""
        workspace_id = interaction.data['values'][0]
        self.current_workspace = {'id': workspace_id}
        await self.show_spaces(interaction)
    
    async def show_spaces(self, interaction: discord.Interaction):
        """Show space selection dropdown"""
        await interaction.response.defer()
        
        try:
            spaces = await self.api.get_spaces(self.current_workspace['id'])
            
            if not spaces:
                embed = EmbedFactory.create_error_embed(
                    "No Spaces",
                    "No spaces found in this workspace."
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # If only one space, skip selection
            if len(spaces) == 1:
                self.current_space = spaces[0]
                await self.show_folders_and_lists(interaction)
                return
            
            self.clear_items()
            
            options = []
            for space in spaces[:25]:
                options.append(
                    discord.SelectOption(
                        label=space['name'],
                        value=space['id'],
                        description=f"ID: {space['id']}"
                    )
                )
            
            select = discord.ui.Select(
                placeholder="Choose a space...",
                options=options
            )
            select.callback = self.space_callback
            self.add_item(select)
            
            # Add back button
            back_button = discord.ui.Button(label="← Back", style=discord.ButtonStyle.secondary)
            back_button.callback = self.back_to_workspaces
            self.add_item(back_button)
            
            embed = EmbedFactory.create_info_embed(
                "Select Space",
                f"Choose a space from the workspace:"
            )
            
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error loading spaces: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error",
                f"Failed to load spaces: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed, view=None)
    
    async def space_callback(self, interaction: discord.Interaction):
        """Handle space selection"""
        space_id = interaction.data['values'][0]
        self.current_space = {'id': space_id}
        await self.show_folders_and_lists(interaction)
    
    async def show_folders_and_lists(self, interaction: discord.Interaction):
        """Show folders and lists in a space"""
        await interaction.response.defer()
        
        try:
            # Get folders and folderless lists
            folders = await self.api.get_folders(self.current_space['id'])
            lists = await self.api.get_lists(self.current_space['id'])
            
            self.clear_items()
            
            options = []
            
            # Add folderless lists
            for lst in lists:
                options.append(
                    discord.SelectOption(
                        label=f"📋 {lst['name']}",
                        value=f"list_{lst['id']}",
                        description="List (no folder)"
                    )
                )
            
            # Add folders
            for folder in folders:
                options.append(
                    discord.SelectOption(
                        label=f"📁 {folder['name']}",
                        value=f"folder_{folder['id']}",
                        description="Folder (click to see lists)"
                    )
                )
            
            if not options:
                embed = EmbedFactory.create_error_embed(
                    "No Lists",
                    "No lists or folders found in this space."
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            select = discord.ui.Select(
                placeholder="Choose a list or folder...",
                options=options[:25]
            )
            select.callback = self.folder_or_list_callback
            self.add_item(select)
            
            # Add back button
            back_button = discord.ui.Button(label="← Back to Spaces", style=discord.ButtonStyle.secondary)
            back_button.callback = self.back_to_spaces
            self.add_item(back_button)
            
            embed = EmbedFactory.create_info_embed(
                "Select List or Folder",
                "Choose a list or browse a folder:"
            )
            
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error loading lists: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error",
                f"Failed to load lists: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed, view=None)
    
    async def folder_or_list_callback(self, interaction: discord.Interaction):
        """Handle folder or list selection"""
        value = interaction.data['values'][0]
        
        if value.startswith('list_'):
            # List selected
            self.selected_list_id = value.replace('list_', '')
            # Get list name from the option
            for option in interaction.message.components[0].options:
                if option.value == value:
                    self.selected_list_name = option.label.replace('📋 ', '')
                    break
            self.stop()
            
            embed = EmbedFactory.create_success_embed(
                "List Selected",
                f"Selected list: **{self.selected_list_name}**"
            )
            await interaction.response.edit_message(embed=embed, view=None)
            
        elif value.startswith('folder_'):
            # Folder selected - show its lists
            folder_id = value.replace('folder_', '')
            await self.show_folder_lists(interaction, folder_id)
    
    async def show_folder_lists(self, interaction: discord.Interaction, folder_id: str):
        """Show lists within a folder"""
        await interaction.response.defer()
        
        try:
            lists = await self.api.get_folder_lists(folder_id)
            
            if not lists:
                embed = EmbedFactory.create_error_embed(
                    "No Lists",
                    "No lists found in this folder."
                )
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            self.clear_items()
            
            options = []
            for lst in lists[:25]:
                options.append(
                    discord.SelectOption(
                        label=lst['name'],
                        value=lst['id'],
                        description=f"List ID: {lst['id']}"
                    )
                )
            
            select = discord.ui.Select(
                placeholder="Choose a list...",
                options=options
            )
            select.callback = self.list_callback
            self.add_item(select)
            
            # Add back button
            back_button = discord.ui.Button(label="← Back to Folders", style=discord.ButtonStyle.secondary)
            back_button.callback = self.back_to_folders
            self.add_item(back_button)
            
            embed = EmbedFactory.create_info_embed(
                "Select List",
                "Choose a list from the folder:"
            )
            
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error loading folder lists: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error", 
                f"Failed to load lists: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed, view=None)
    
    async def list_callback(self, interaction: discord.Interaction):
        """Handle final list selection"""
        self.selected_list_id = interaction.data['values'][0]
        # Get list name from the option
        for option in interaction.message.components[0].options:
            if option.value == self.selected_list_id:
                self.selected_list_name = option.label
                break
        self.stop()
        
        embed = EmbedFactory.create_success_embed(
            "List Selected",
            f"Selected list: **{self.selected_list_name}**"
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def back_to_workspaces(self, interaction: discord.Interaction):
        """Go back to workspace selection"""
        workspaces = await self.api.get_workspaces()
        await self.show_workspaces(interaction, workspaces)
    
    async def back_to_spaces(self, interaction: discord.Interaction):
        """Go back to space selection"""
        await self.show_spaces(interaction)
    
    async def back_to_folders(self, interaction: discord.Interaction):
        """Go back to folder/list selection"""
        await self.show_folders_and_lists(interaction)


class TaskSelectView(discord.ui.View):
    """Interactive task selection from a list"""
    
    def __init__(self, api: ClickUpAPI, list_id: str, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.api = api
        self.list_id = list_id
        self.selected_task_id = None
        self.selected_task_name = None
    
    async def start(self, interaction: discord.Interaction):
        """Start task selection"""
        await interaction.response.defer()
        
        try:
            tasks = await self.api.get_tasks(self.list_id)
            
            if not tasks:
                embed = EmbedFactory.create_error_embed(
                    "No Tasks",
                    "No tasks found in this list."
                )
                await interaction.edit_original_response(embed=embed)
                return
            
            # Group tasks by status
            task_groups = {}
            for task in tasks:
                status = task.get('status', {}).get('status', 'No Status')
                if status not in task_groups:
                    task_groups[status] = []
                task_groups[status].append(task)
            
            options = []
            for status, group_tasks in task_groups.items():
                for task in group_tasks[:20]:  # Limit per status
                    # Format task info
                    assignees = task.get('assignees', [])
                    assignee_str = f" ({assignees[0]['username']})" if assignees else ""
                    
                    options.append(
                        discord.SelectOption(
                            label=f"{task['name'][:80]}{assignee_str}",
                            value=task['id'],
                            description=f"{status} • Priority: {task.get('priority', {}).get('priority', 'None')}"
                        )
                    )
                    
                    if len(options) >= 25:  # Discord limit
                        break
                
                if len(options) >= 25:
                    break
            
            select = discord.ui.Select(
                placeholder="Choose a task...",
                options=options
            )
            select.callback = self.task_callback
            self.add_item(select)
            
            embed = EmbedFactory.create_info_embed(
                "Select Task",
                f"Found {len(tasks)} task(s) in the list. Showing up to 25:"
            )
            
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error loading tasks: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error",
                f"Failed to load tasks: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed)
    
    async def task_callback(self, interaction: discord.Interaction):
        """Handle task selection"""
        self.selected_task_id = interaction.data['values'][0]
        # Get task name from the option
        for option in interaction.message.components[0].options:
            if option.value == self.selected_task_id:
                self.selected_task_name = option.label
                break
        self.stop()
        
        embed = EmbedFactory.create_success_embed(
            "Task Selected",
            f"Selected task: **{self.selected_task_name}**"
        )
        await interaction.response.edit_message(embed=embed, view=None)


class UserSelectView(discord.ui.View):
    """Interactive user/assignee selection from ClickUp"""
    
    def __init__(self, api: ClickUpAPI, workspace_id: str, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.api = api
        self.workspace_id = workspace_id
        self.selected_user_id = None
        self.selected_user_name = None
    
    async def start(self, interaction: discord.Interaction):
        """Start user selection"""
        await interaction.response.defer()
        
        try:
            # Get workspace members
            members = await self.api.get_workspace_members(self.workspace_id)
            
            if not members:
                embed = EmbedFactory.create_error_embed(
                    "No Members",
                    "No members found in this workspace."
                )
                await interaction.edit_original_response(embed=embed)
                return
            
            options = []
            for member in members[:25]:
                user = member.get('user', {})
                options.append(
                    discord.SelectOption(
                        label=user.get('username', 'Unknown'),
                        value=str(user.get('id', '')),
                        description=user.get('email', 'No email')[:100]
                    )
                )
            
            select = discord.ui.Select(
                placeholder="Choose a user to assign...",
                options=options
            )
            select.callback = self.user_callback
            self.add_item(select)
            
            embed = EmbedFactory.create_info_embed(
                "Select User",
                f"Choose a user from the workspace ({len(members)} members):"
            )
            
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error",
                f"Failed to load users: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed)
    
    async def user_callback(self, interaction: discord.Interaction):
        """Handle user selection"""
        self.selected_user_id = interaction.data['values'][0]
        # Get user name from the option
        for option in interaction.message.components[0].options:
            if option.value == self.selected_user_id:
                self.selected_user_name = option.label
                break
        self.stop()
        
        embed = EmbedFactory.create_success_embed(
            "User Selected",
            f"Selected user: **{self.selected_user_name}**"
        )
        await interaction.response.edit_message(embed=embed, view=None)


class PrioritySelectView(discord.ui.View):
    """Priority selection dropdown"""
    
    def __init__(self, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.selected_priority = None
        
        priorities = [
            ("🔴 Urgent", "urgent", "Highest priority"),
            ("🟠 High", "high", "High priority"),
            ("🟡 Normal", "normal", "Normal priority"),
            ("🔵 Low", "low", "Low priority")
        ]
        
        options = [
            discord.SelectOption(label=label, value=value, description=desc)
            for label, value, desc in priorities
        ]
        
        select = discord.ui.Select(
            placeholder="Choose priority level...",
            options=options
        )
        select.callback = self.priority_callback
        self.add_item(select)
    
    async def priority_callback(self, interaction: discord.Interaction):
        """Handle priority selection"""
        self.selected_priority = interaction.data['values'][0]
        self.stop()
        
        embed = EmbedFactory.create_success_embed(
            "Priority Selected",
            f"Selected priority: **{self.selected_priority.title()}**"
        )
        await interaction.response.edit_message(embed=embed, view=None)


class StatusSelectView(discord.ui.View):
    """Status selection dropdown"""
    
    def __init__(self, api: ClickUpAPI, list_id: str, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.api = api
        self.list_id = list_id
        self.selected_status = None
    
    async def start(self, interaction: discord.Interaction):
        """Load and show available statuses"""
        await interaction.response.defer()
        
        try:
            # Get list details to find available statuses
            list_details = await self.api.get_list(self.list_id)
            statuses = list_details.get('statuses', [])
            
            if not statuses:
                # Default statuses
                statuses = [
                    {'status': 'to do', 'color': '#87909e'},
                    {'status': 'in progress', 'color': '#5a55ca'},
                    {'status': 'done', 'color': '#6bc950'}
                ]
            
            options = []
            for status in statuses[:25]:
                # Create color emoji based on status color
                color_emoji = "⚪"
                if status.get('color'):
                    if 'green' in status['color'].lower():
                        color_emoji = "🟢"
                    elif 'blue' in status['color'].lower():
                        color_emoji = "🔵"
                    elif 'red' in status['color'].lower():
                        color_emoji = "🔴"
                    elif 'yellow' in status['color'].lower():
                        color_emoji = "🟡"
                    elif 'purple' in status['color'].lower():
                        color_emoji = "🟣"
                
                options.append(
                    discord.SelectOption(
                        label=f"{color_emoji} {status['status'].title()}",
                        value=status['status']
                    )
                )
            
            select = discord.ui.Select(
                placeholder="Choose status...",
                options=options
            )
            select.callback = self.status_callback
            self.add_item(select)
            
            embed = EmbedFactory.create_info_embed(
                "Select Status",
                "Choose a status for the task:"
            )
            
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error loading statuses: {e}")
            # Fallback to default statuses
            options = [
                discord.SelectOption(label="📝 To Do", value="to do"),
                discord.SelectOption(label="🔄 In Progress", value="in progress"),
                discord.SelectOption(label="✅ Done", value="done")
            ]
            
            select = discord.ui.Select(
                placeholder="Choose status...",
                options=options
            )
            select.callback = self.status_callback
            self.add_item(select)
            
            embed = EmbedFactory.create_info_embed(
                "Select Status",
                "Choose a status for the task:"
            )
            
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def status_callback(self, interaction: discord.Interaction):
        """Handle status selection"""
        self.selected_status = interaction.data['values'][0]
        self.stop()
        
        embed = EmbedFactory.create_success_embed(
            "Status Selected",
            f"Selected status: **{self.selected_status.title()}**"
        )
        await interaction.response.edit_message(embed=embed, view=None)