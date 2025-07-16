import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime
from services.clickup_api import ClickUpAPI
from repositories.clickup_oauth_workspaces import ClickUpOAuthWorkspaceRepository
from utils.embed_factory import EmbedFactory
from utils.enhanced_selections import (
    ListSelectView, TaskSelectView, UserSelectView, 
    PrioritySelectView, StatusSelectView
)
from utils.helpers import parse_due_date
from loguru import logger

class ClickUpTasksEnhanced(commands.Cog):
    """Enhanced ClickUp task management with dropdowns for everything"""
    
    def __init__(self, bot):
        self.bot = bot
        self.list_cache = {}  # Cache lists by guild_id
        self.cache_ttl = 300  # 5 minutes
    
    async def get_api(self, guild_id: int) -> Optional[ClickUpAPI]:
        """Get ClickUp API instance for the guild using OAuth2 workspace repository"""
        # Get default workspace
        default_workspace = await ClickUpOAuthWorkspaceRepository.get_default_workspace(guild_id)
        if not default_workspace:
            return None
            
        # Get OAuth2 access token
        token = await ClickUpOAuthWorkspaceRepository.get_access_token(default_workspace)
        if not token:
            return None
            
        return ClickUpAPI(token)
    
    @app_commands.command(name="task-create", description="Create a new ClickUp task with dropdown selections only")
    async def task_create(self, interaction: discord.Interaction):
        """Create a task with full dropdown support"""
        # Check if configured
        api = await self.get_api(interaction.guild_id)
        if not api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/clickup-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Defer immediately
        await interaction.response.defer(ephemeral=True)
        
        try:
            async with api:
                # Get workspace and lists quickly
                workspaces = await api.get_workspaces()
                if not workspaces:
                    embed = EmbedFactory.create_error_embed(
                        "No Workspaces",
                        "No workspaces found."
                    )
                    await interaction.followup.send(embed=embed)
                    return
                
                # Quick list selection
                workspace_id = workspaces[0]['id']
                spaces = await api.get_spaces(workspace_id)
                
                all_lists = []
                # Limit spaces to prevent timeout
                for space in spaces[:2]:  # Reduced from 3 to 2
                    try:
                        lists = await api.get_lists(space['id'])
                        for lst in lists[:10]:  # Limit lists per space
                            lst['space_name'] = space['name']
                            all_lists.append(lst)
                    except Exception as e:
                        logger.warning(f"Failed to get lists for space {space['name']}: {e}")
                        continue
            
            if not all_lists:
                embed = EmbedFactory.create_error_embed(
                    "No Lists",
                    "No lists found. Please create a list in ClickUp first."
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Step 1: Select task template
            embed = EmbedFactory.create_info_embed(
                "Select Task Type",
                "Choose what type of task you want to create:"
            )
            
            class TaskTypeSelect(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=180)
                    self.selected_name = None
                    self.selected_description = None
                    
                    task_types = [
                        {"name": "Bug Fix - Critical", "desc": "High priority bug requiring immediate attention"},
                        {"name": "Feature Implementation", "desc": "New feature development work"},
                        {"name": "Code Review", "desc": "Review and approve code changes"},
                        {"name": "Documentation Update", "desc": "Update or create documentation"},
                        {"name": "Testing & QA", "desc": "Testing and quality assurance work"},
                        {"name": "Performance Optimization", "desc": "Improve system performance and efficiency"},
                        {"name": "Security Enhancement", "desc": "Security improvements and hardening"},
                        {"name": "UI/UX Improvement", "desc": "User interface and experience enhancements"},
                        {"name": "Database Migration", "desc": "Database schema or data migration work"},
                        {"name": "Deployment Task", "desc": "Infrastructure and deployment related work"},
                        {"name": "Research & Investigation", "desc": "Research new technologies or investigate issues"},
                        {"name": "Meeting & Planning", "desc": "Team meetings and project planning sessions"}
                    ]
                    
                    options = []
                    for task_type in task_types:
                        options.append(
                            discord.SelectOption(
                                label=task_type["name"],
                                value=f"{task_type['name']}||{task_type['desc']}",
                                description=task_type["desc"][:100]
                            )
                        )
                    
                    select = discord.ui.Select(
                        placeholder="Choose a task type...",
                        options=options
                    )
                    select.callback = self.select_callback
                    self.add_item(select)
                
                async def select_callback(self, select_interaction: discord.Interaction):
                    parts = select_interaction.data['values'][0].split('||')
                    self.selected_name = parts[0]
                    self.selected_description = parts[1]
                    self.stop()
                    await select_interaction.response.defer_update()
            
            task_type_select = TaskTypeSelect()
            await interaction.followup.send(embed=embed, view=task_type_select)
            
            timed_out = await task_type_select.wait()
            
            if timed_out or not task_type_select.selected_name:
                if timed_out:
                    embed = EmbedFactory.create_error_embed("Timeout", "Selection timed out. Please try again.")
                    await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Step 2: Show list selection
            embed = EmbedFactory.create_info_embed(
                "Select List",
                f"Creating task: **{task_type_select.selected_name}**\n\nWhere should I create this task?"
            )
            
            class ListSelect(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=180)
                    self.selected_list = None
                    
                    options = []
                    for lst in all_lists[:25]:
                        options.append(
                            discord.SelectOption(
                                label=lst['name'],
                                value=lst['id'],
                                description=f"Space: {lst.get('space_name', 'Unknown')}"
                            )
                        )
                    
                    select = discord.ui.Select(
                        placeholder="Choose a list...",
                        options=options
                    )
                    select.callback = self.select_callback
                    self.add_item(select)
                
                async def select_callback(self, select_interaction: discord.Interaction):
                    self.selected_list = next((l for l in all_lists if l['id'] == select_interaction.data['values'][0]), None)
                    self.stop()
                    await select_interaction.response.defer_update()
            
            list_select = ListSelect()
            await interaction.followup.send(embed=embed, view=list_select)
            
            timed_out = await list_select.wait()
            
            if timed_out or not list_select.selected_list:
                if timed_out:
                    embed = EmbedFactory.create_error_embed("Timeout", "Selection timed out. Please try again.")
                    await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Step 3: Select priority
            embed = EmbedFactory.create_info_embed(
                "Select Priority",
                f"Creating task: **{task_type_select.selected_name}**\n\nChoose priority level:"
            )
            
            priority_view = PrioritySelectView()
            await interaction.followup.send(embed=embed, view=priority_view, ephemeral=True)
            
            timed_out = await priority_view.wait()
            
            if timed_out or not priority_view.selected_priority:
                embed = EmbedFactory.create_info_embed("Cancelled", "Task creation cancelled.")
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Step 4: Select assignee (optional)
            embed = EmbedFactory.create_info_embed(
                "Assign User (Optional)",
                "Would you like to assign this task to someone?"
            )
            
            class AssignChoice(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                    self.assign = None
                
                @discord.ui.button(label="Yes, assign someone", style=discord.ButtonStyle.primary)
                async def yes_assign(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.assign = True
                    self.stop()
                    await button_interaction.response.defer_update()
                
                @discord.ui.button(label="No, skip assignment", style=discord.ButtonStyle.secondary)
                async def no_assign(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.assign = False
                    self.stop()
                    await button_interaction.response.defer_update()
            
            assign_choice = AssignChoice()
            await interaction.edit_original_response(embed=embed, view=assign_choice)
            
            timed_out = await assign_choice.wait()
            
            if timed_out:
                embed = EmbedFactory.create_error_embed("Timeout", "Selection timed out. Task will be created without assignee.")
                await interaction.edit_original_response(embed=embed, view=None)
                assign_choice.assign = False
            
            assignee_ids = []
            if assign_choice.assign:
                # Get workspace ID
                workspace = await ClickUpOAuthWorkspaceRepository.get_default_workspace(interaction.guild_id)
                if workspace:
                    user_view = UserSelectView(api, workspace.workspace_id)
                    await user_view.start(interaction)
                    
                    timed_out = await user_view.wait()
                    
                    if not timed_out and user_view.selected_user_id:
                        assignee_ids = [int(user_view.selected_user_id)]
            
            # Create the task
            embed = EmbedFactory.create_info_embed(
                "Creating Task",
                "⏳ Creating your task..."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            try:
                # Create task data
                task_data = {
                    "name": task_type_select.selected_name,
                    "description": task_type_select.selected_description,
                    "priority": {"priority": priority_view.selected_priority} if priority_view.selected_priority else None,
                    "assignees": assignee_ids
                }
                
                result = await api.create_task(list_select.selected_list['id'], **task_data)
                
                # Success embed
                embed = EmbedFactory.create_success_embed(
                    "Task Created Successfully",
                    f"✅ Created task: **{task_type_select.selected_name}**"
                )
                
                embed.add_field(name="List", value=list_select.selected_list['name'], inline=True)
                embed.add_field(name="Priority", value=priority_view.selected_priority.title(), inline=True)
                
                if assignee_ids:
                    embed.add_field(name="Assigned to", value=user_view.selected_user_name, inline=True)
                
                # Note: No due date in this simplified version
                
                if result.get('url'):
                    embed.add_field(name="View Task", value=f"[Click here]({result['url']})", inline=False)
                
                await interaction.edit_original_response(embed=embed)
                
            except Exception as e:
                logger.error(f"Error creating task: {e}")
                embed = EmbedFactory.create_error_embed(
                    "Task Creation Failed",
                    f"❌ Failed to create task: {str(e)}"
                )
                await interaction.edit_original_response(embed=embed)
        except Exception as e:
            logger.error(f"Error in task creation flow: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error",
                f"An error occurred: {str(e)}"
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="task-update", description="Update an existing task with dropdown selections only")
    async def task_update(self, interaction: discord.Interaction):
        """Update a task with full dropdown support"""
        api = await self.get_api(interaction.guild_id)
        if not api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/clickup-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with api:
            # Step 1: Select list
            list_view = ListSelectView(api)
            await list_view.start(interaction)
            
            timed_out = await list_view.wait()
            
            if timed_out or not list_view.selected_list_id:
                if timed_out:
                    embed = EmbedFactory.create_error_embed("Timeout", "List selection timed out. Please try again.")
                    await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Step 2: Select task
            task_view = TaskSelectView(api, list_view.selected_list_id)
            await task_view.start(interaction)
            
            timed_out = await task_view.wait()
            
            if timed_out or not task_view.selected_task_id:
                if timed_out:
                    embed = EmbedFactory.create_error_embed("Timeout", "Task selection timed out. Please try again.")
                    await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Step 3: What to update?
            embed = EmbedFactory.create_info_embed(
                "Update Task",
                f"Updating: **{task_view.selected_task_name}**\n\nWhat would you like to update?"
            )
            
            class UpdateChoice(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=120)
                    self.update_status = False
                    self.update_priority = False
                    self.update_assignee = False
                    self.confirmed = False
                
                @discord.ui.button(label="Status", style=discord.ButtonStyle.primary, row=0)
                async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.update_status = not self.update_status
                    button.style = discord.ButtonStyle.success if self.update_status else discord.ButtonStyle.primary
                    await interaction.response.edit_message(view=self)
                
                @discord.ui.button(label="Priority", style=discord.ButtonStyle.primary, row=0)
                async def priority_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.update_priority = not self.update_priority
                    button.style = discord.ButtonStyle.success if self.update_priority else discord.ButtonStyle.primary
                    await interaction.response.edit_message(view=self)
                
                @discord.ui.button(label="Assignee", style=discord.ButtonStyle.primary, row=0)
                async def assignee_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.update_assignee = not self.update_assignee
                    button.style = discord.ButtonStyle.success if self.update_assignee else discord.ButtonStyle.primary
                    await interaction.response.edit_message(view=self)
                
                @discord.ui.button(label="Continue", style=discord.ButtonStyle.success, row=1)
                async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if not any([self.update_status, self.update_priority, self.update_assignee]):
                        await interaction.response.send_message("Please select at least one field to update.", ephemeral=True)
                        return
                    self.confirmed = True
                    self.stop()
                    await interaction.response.defer_update()
            
            update_choice = UpdateChoice()
            await interaction.edit_original_response(embed=embed, view=update_choice)
            
            timed_out = await update_choice.wait()
            
            if timed_out or not update_choice.confirmed:
                embed = EmbedFactory.create_info_embed("Cancelled", "Update cancelled.")
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Show update options selection first
            embed = EmbedFactory.create_info_embed(
                "Task Update Options",
                "What would you like to update for this task?"
            )
            
            class UpdateOptionsSelect(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=300)
                    self.update_name = False
                    self.update_desc = False
                    self.selected_name = None
                    self.selected_desc = None
                
                @discord.ui.button(label="Update Name", style=discord.ButtonStyle.primary)
                async def update_name_btn(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.update_name = True
                    button.style = discord.ButtonStyle.success
                    await button_interaction.response.edit_message(view=self)
                
                @discord.ui.button(label="Update Description", style=discord.ButtonStyle.primary)
                async def update_desc_btn(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.update_desc = True
                    button.style = discord.ButtonStyle.success
                    await button_interaction.response.edit_message(view=self)
                
                @discord.ui.button(label="Continue", style=discord.ButtonStyle.success, row=1)
                async def continue_btn(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    if not self.update_name and not self.update_desc and not update_choice.update_status and not update_choice.update_priority and not update_choice.update_assignee:
                        await button_interaction.response.send_message("Please select at least one field to update.", ephemeral=True)
                        return
                    self.stop()
                    await button_interaction.response.defer_update()
            
            update_opts = UpdateOptionsSelect()
            await interaction.edit_original_response(embed=embed, view=update_opts)
            
            timed_out = await update_opts.wait()
            if timed_out:
                embed = EmbedFactory.create_error_embed("Timeout", "Update options selection timed out.")
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Collect updates
            updates = {}
            
            # Handle name update with dropdown
            if update_opts.update_name:
                embed = EmbedFactory.create_info_embed(
                    "Select New Name",
                    "Choose a new name for the task:"
                )
                
                class NameSelect(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=300)
                        self.selected_name = None
                        
                        name_options = [
                            "Fix critical bug", "Implement new feature", "Update documentation",
                            "Refactor code", "Add unit tests", "Optimize performance",
                            "Security update", "UI improvements", "Database migration",
                            "Deploy to production", "Code review", "Bug investigation",
                            "Feature enhancement", "System maintenance", "User research"
                        ]
                        
                        options = []
                        for name in name_options:
                            options.append(
                                discord.SelectOption(
                                    label=name,
                                    value=name,
                                    description="Select this name"
                                )
                            )
                        
                        select = discord.ui.Select(
                            placeholder="Choose a new task name...",
                            options=options
                        )
                        select.callback = self.name_callback
                        self.add_item(select)
                    
                    async def name_callback(self, select_interaction: discord.Interaction):
                        self.selected_name = select_interaction.data['values'][0]
                        self.stop()
                        await select_interaction.response.defer_update()
                
                name_view = NameSelect()
                await interaction.edit_original_response(embed=embed, view=name_view)
                
                timed_out = await name_view.wait()
                if not timed_out and name_view.selected_name:
                    updates['name'] = name_view.selected_name
            
            # Handle description update with dropdown
            if update_opts.update_desc:
                embed = EmbedFactory.create_info_embed(
                    "Select New Description",
                    "Choose a new description for the task:"
                )
                
                class DescSelect(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=300)
                        self.selected_desc = None
                        
                        desc_options = [
                            "High priority task requiring immediate attention",
                            "Standard maintenance and improvement work",
                            "Customer-requested feature enhancement",
                            "Bug fix to improve system stability",
                            "Documentation update for better clarity",
                            "Performance optimization work",
                            "Security enhancement and hardening",
                            "User experience improvement",
                            "Infrastructure and deployment task",
                            "Research and analysis work",
                            "Testing and quality assurance",
                            "No description needed"
                        ]
                        
                        options = []
                        for desc in desc_options:
                            options.append(
                                discord.SelectOption(
                                    label=desc[:100],
                                    value=desc,
                                    description="Select this description"
                                )
                            )
                        
                        select = discord.ui.Select(
                            placeholder="Choose a new description...",
                            options=options
                        )
                        select.callback = self.desc_callback
                        self.add_item(select)
                    
                    async def desc_callback(self, select_interaction: discord.Interaction):
                        self.selected_desc = select_interaction.data['values'][0]
                        if self.selected_desc == "No description needed":
                            self.selected_desc = ""
                        self.stop()
                        await select_interaction.response.defer_update()
                
                desc_view = DescSelect()
                await interaction.edit_original_response(embed=embed, view=desc_view)
                
                timed_out = await desc_view.wait()
                if not timed_out and desc_view.selected_desc is not None:
                    updates['description'] = desc_view.selected_desc
            
            # Status update
            if update_choice.update_status:
                status_view = StatusSelectView(api, list_view.selected_list_id)
                await status_view.start(interaction)
                timed_out = await status_view.wait()
                if timed_out:
                    embed = EmbedFactory.create_error_embed("Timeout", "Status selection timed out.")
                    await interaction.edit_original_response(embed=embed, view=None)
                    return
                
                if status_view.selected_status:
                    updates['status'] = status_view.selected_status
            
            # Priority update
            if update_choice.update_priority:
                priority_view = PrioritySelectView()
                embed = EmbedFactory.create_info_embed("Select Priority", "Choose new priority level:")
                await interaction.edit_original_response(embed=embed, view=priority_view)
                timed_out = await priority_view.wait()
                
                if not timed_out and priority_view.selected_priority:
                    updates['priority'] = {"priority": priority_view.selected_priority}
            
            # Assignee update
            if update_choice.update_assignee:
                workspace = await ClickUpOAuthWorkspaceRepository.get_default_workspace(interaction.guild_id)
                if workspace:
                    user_view = UserSelectView(api, workspace.workspace_id)
                    await user_view.start(interaction)
                    timed_out = await user_view.wait()
                    
                    if not timed_out and user_view.selected_user_id:
                        updates['assignees'] = [int(user_view.selected_user_id)]
            
            # Apply updates
            try:
                await api.update_task(task_view.selected_task_id, **updates)
                
                embed = EmbedFactory.create_success_embed(
                    "Task Updated",
                    f"✅ Successfully updated: **{task_view.selected_task_name}**"
                )
                
                if 'name' in updates:
                    embed.add_field(name="New Name", value=updates['name'], inline=True)
                if 'status' in updates:
                    embed.add_field(name="Status", value=updates['status'].title(), inline=True)
                if 'priority' in updates:
                    embed.add_field(name="Priority", value=priority_view.selected_priority.title(), inline=True)
                if 'assignees' in updates:
                    embed.add_field(name="Assigned to", value=user_view.selected_user_name, inline=True)
                
                await interaction.edit_original_response(embed=embed)
                
            except Exception as e:
                logger.error(f"Error updating task: {e}")
                embed = EmbedFactory.create_error_embed(
                    "Update Failed",
                    f"❌ Failed to update task: {str(e)}"
                )
                await interaction.edit_original_response(embed=embed)
    
    @app_commands.command(name="task-list", description="List tasks with interactive filtering")
    async def task_list(self, interaction: discord.Interaction):
        """List tasks with dropdown selections"""
        api = await self.get_api(interaction.guild_id)
        if not api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/clickup-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Defer immediately since list selection takes time
        await interaction.response.defer(ephemeral=True)
        
        async with api:
            # Get the default workspace from the repository
            default_workspace = await ClickUpOAuthWorkspaceRepository.get_default_workspace(interaction.guild_id)
            if not default_workspace:
                embed = EmbedFactory.create_error_embed(
                    "No Default Workspace",
                    "No default workspace set. Run `/clickup-setup` first."
                )
                await interaction.followup.send(embed=embed)
                return
            
            workspace_id = default_workspace.workspace_id
            
            # Get spaces from the default workspace
            spaces = await api.get_spaces(workspace_id)
            if not spaces:
                embed = EmbedFactory.create_error_embed(
                    "No Spaces",
                    "No spaces found in workspace."
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Check cache first
            import time
            cache_key = f"{interaction.guild_id}_{workspace_id}"
            cached_data = self.list_cache.get(cache_key)
            
            if cached_data and (time.time() - cached_data['timestamp']) < self.cache_ttl:
                all_lists = cached_data['lists']
            else:
                # Get all lists from all spaces for quick selection
                all_lists = []
                # Limit to avoid timeout
                for space in spaces[:2]:  # Reduced to 2 spaces
                    try:
                        lists = await api.get_lists(space['id'])
                        for lst in lists[:10]:  # Limit lists per space
                            lst['space_name'] = space['name']
                            all_lists.append(lst)
                    except Exception as e:
                        logger.warning(f"Failed to get lists for space {space['name']}: {e}")
                        continue
                
                # Cache the results
                self.list_cache[cache_key] = {
                    'lists': all_lists,
                    'timestamp': time.time()
                }
                
            if not all_lists:
                embed = EmbedFactory.create_error_embed(
                    "No Lists",
                    "No lists found in any space."
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Show list selection
            embed = EmbedFactory.create_info_embed(
                "Select List",
                "Choose a list to view tasks:"
            )
            
            class QuickListSelect(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=180)
                    self.selected_list = None
                    
                    options = []
                    for lst in all_lists[:25]:
                        options.append(
                            discord.SelectOption(
                                label=lst['name'],
                                value=lst['id'],
                                description=f"Space: {lst.get('space_name', 'Unknown')}"
                            )
                        )
                    
                    select = discord.ui.Select(
                        placeholder="Choose a list...",
                        options=options
                    )
                    select.callback = self.select_callback
                    self.add_item(select)
                
                async def select_callback(self, select_interaction: discord.Interaction):
                    self.selected_list = next((l for l in all_lists if l['id'] == select_interaction.data['values'][0]), None)
                    self.stop()
                    await select_interaction.response.defer_update()
            
            list_select = QuickListSelect()
            await interaction.followup.send(embed=embed, view=list_select)
            
            timed_out = await list_select.wait()
            
            if timed_out or not list_select.selected_list:
                if timed_out:
                    embed = EmbedFactory.create_error_embed("Timeout", "Selection timed out. Please try again.")
                    await interaction.edit_original_response(embed=embed, view=None)
                return
            
            selected_list = list_select.selected_list
            
            # Fetch tasks
            embed = EmbedFactory.create_info_embed(
                "Loading Tasks",
                f"⏳ Loading tasks from **{selected_list['name']}**..."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            try:
                tasks = await api.get_tasks(selected_list['id'])
                
                if not tasks:
                    embed = EmbedFactory.create_info_embed(
                        "No Tasks",
                        f"No tasks found in **{selected_list['name']}**"
                    )
                    await interaction.edit_original_response(embed=embed)
                    return
                
                # Group by status
                status_groups = {}
                for task in tasks:
                    status = task.get('status', {}).get('status', 'No Status')
                    if status not in status_groups:
                        status_groups[status] = []
                    status_groups[status].append(task)
                
                # Create embed
                embed = EmbedFactory.create_info_embed(
                    f"Tasks in {selected_list['name']}",
                    f"Found **{len(tasks)}** task(s)"
                )
                
                for status, group_tasks in list(status_groups.items())[:5]:  # Limit to 5 statuses
                    task_list = []
                    for task in group_tasks[:5]:  # Limit to 5 tasks per status
                        assignees = task.get('assignees', [])
                        assignee = f" ({assignees[0]['username']})" if assignees else ""
                        priority = task.get('priority', {})
                        priority_icon = {
                            'urgent': '🔴',
                            'high': '🟠',
                            'normal': '🟡',
                            'low': '🔵'
                        }.get(priority.get('priority', ''), '⚪')
                        
                        task_list.append(f"{priority_icon} **{task['name']}**{assignee}")
                    
                    if task_list:
                        embed.add_field(
                            name=f"{status.title()} ({len(group_tasks)})",
                            value="\n".join(task_list),
                            inline=False
                        )
                
                await interaction.edit_original_response(embed=embed)
                
            except Exception as e:
                logger.error(f"Error listing tasks: {e}")
                embed = EmbedFactory.create_error_embed(
                    "Error",
                    f"Failed to load tasks: {str(e)}"
                )
                await interaction.edit_original_response(embed=embed)
    
    @app_commands.command(name="task-delete", description="Delete a task with confirmation")
    async def task_delete(self, interaction: discord.Interaction):
        """Delete a task with dropdown selection"""
        api = await self.get_api(interaction.guild_id)
        if not api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/clickup-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with api:
            # Select list
            list_view = ListSelectView(api)
            await list_view.start(interaction)
            
            timed_out = await list_view.wait()
            
            if timed_out or not list_view.selected_list_id:
                if timed_out:
                    embed = EmbedFactory.create_error_embed("Timeout", "List selection timed out. Please try again.")
                    await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Select task
            task_view = TaskSelectView(api, list_view.selected_list_id)
            await task_view.start(interaction)
            
            timed_out = await task_view.wait()
            
            if timed_out or not task_view.selected_task_id:
                if timed_out:
                    embed = EmbedFactory.create_error_embed("Timeout", "Task selection timed out. Please try again.")
                    await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Confirm deletion
            embed = EmbedFactory.create_warning_embed(
                "Confirm Deletion",
                f"Are you sure you want to delete:\n**{task_view.selected_task_name}**?\n\n"
                "⚠️ This action cannot be undone!"
            )
            
            class DeleteConfirm(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=30)
                    self.confirmed = False
                
                @discord.ui.button(label="Delete Task", style=discord.ButtonStyle.danger)
                async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.confirmed = True
                    self.stop()
                    await button_interaction.response.defer_update()
                
                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    self.stop()
                    await button_interaction.response.defer_update()
            
            confirm_view = DeleteConfirm()
            await interaction.edit_original_response(embed=embed, view=confirm_view)
            
            timed_out = await confirm_view.wait()
            
            if timed_out or not confirm_view.confirmed:
                embed = EmbedFactory.create_info_embed("Cancelled", "Task deletion cancelled.")
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Delete the task
            try:
                await api.delete_task(task_view.selected_task_id)
                
                embed = EmbedFactory.create_success_embed(
                    "Task Deleted",
                    f"✅ Successfully deleted: **{task_view.selected_task_name}**"
                )
                await interaction.edit_original_response(embed=embed, view=None)
                
            except Exception as e:
                logger.error(f"Error deleting task: {e}")
                embed = EmbedFactory.create_error_embed(
                    "Deletion Failed",
                    f"❌ Failed to delete task: {str(e)}"
                )
                await interaction.edit_original_response(embed=embed, view=None)

async def setup(bot):
    await bot.add_cog(ClickUpTasksEnhanced(bot))