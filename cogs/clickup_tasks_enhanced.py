import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime
from services.clickup_api import ClickUpAPI
from repositories.server_config import ServerConfigRepository
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
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
    
    async def get_api(self, guild_id: int) -> Optional[ClickUpAPI]:
        """Get ClickUp API instance for the guild"""
        # Try new multi-workspace system first
        workspace = await ClickUpWorkspaceRepository.get_default_workspace(guild_id)
        if workspace:
            token = await ClickUpWorkspaceRepository.get_decrypted_token(workspace)
            return ClickUpAPI(token)
        
        # Fall back to old system
        config = await ServerConfigRepository.get_server_config(guild_id)
        if config and config.clickup_token_encrypted:
            from services.security import decrypt_token
            token = await decrypt_token(config.clickup_token_encrypted)
            return ClickUpAPI(token)
        
        return None
    
    @app_commands.command(name="task-create", description="Create a new ClickUp task with interactive selections")
    @app_commands.describe(
        name="Name of the task",
        description="Task description (optional)",
        due_date="Due date (e.g., '2d', 'tomorrow', '2024-12-31')"
    )
    async def task_create(
        self,
        interaction: discord.Interaction,
        name: str,
        description: Optional[str] = None,
        due_date: Optional[str] = None
    ):
        """Create a task with full dropdown support"""
        # Check if configured
        api = await self.get_api(interaction.guild_id)
        if not api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/clickup-setup` or `/workspace-add` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with api:
            # Step 1: Select list
            list_view = ListSelectView(api)
            await list_view.start(interaction)
            
            # Wait for list selection
            await list_view.wait()
            
            if not list_view.selected_list_id:
                return  # User cancelled
            
            # Step 2: Select priority
            embed = EmbedFactory.create_info_embed(
                "Select Priority",
                f"Creating task: **{name}**\n\nChoose priority level:"
            )
            
            priority_view = PrioritySelectView()
            await interaction.followup.send(embed=embed, view=priority_view, ephemeral=True)
            
            await priority_view.wait()
            
            if not priority_view.selected_priority:
                embed = EmbedFactory.create_info_embed("Cancelled", "Task creation cancelled.")
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Step 3: Select assignee (optional)
            embed = EmbedFactory.create_info_embed(
                "Assign User (Optional)",
                "Would you like to assign this task to someone?"
            )
            
            class AssignChoice(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                    self.assign = None
                
                @discord.ui.button(label="Yes, assign someone", style=discord.ButtonStyle.primary)
                async def yes_assign(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.assign = True
                    self.stop()
                    await interaction.response.defer()
                
                @discord.ui.button(label="No, skip assignment", style=discord.ButtonStyle.secondary)
                async def no_assign(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.assign = False
                    self.stop()
                    await interaction.response.defer()
            
            assign_choice = AssignChoice()
            await interaction.edit_original_response(embed=embed, view=assign_choice)
            
            await assign_choice.wait()
            
            assignee_ids = []
            if assign_choice.assign:
                # Get workspace ID
                workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
                if workspace:
                    user_view = UserSelectView(api, workspace.workspace_id)
                    await user_view.start(interaction)
                    
                    await user_view.wait()
                    
                    if user_view.selected_user_id:
                        assignee_ids = [int(user_view.selected_user_id)]
            
            # Create the task
            embed = EmbedFactory.create_info_embed(
                "Creating Task",
                "⏳ Creating your task..."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            try:
                # Parse due date
                due_date_unix = None
                if due_date:
                    parsed_date = parse_due_date(due_date)
                    if parsed_date:
                        due_date_unix = int(parsed_date.timestamp() * 1000)
                
                # Create task
                task_data = {
                    "name": name,
                    "description": description or "",
                    "priority": {"priority": priority_view.selected_priority} if priority_view.selected_priority else None,
                    "due_date": due_date_unix,
                    "assignees": assignee_ids
                }
                
                result = await api.create_task(list_view.selected_list_id, **task_data)
                
                # Success embed
                embed = EmbedFactory.create_success_embed(
                    "Task Created Successfully",
                    f"✅ Created task: **{name}**"
                )
                
                embed.add_field(name="List", value=list_view.selected_list_name, inline=True)
                embed.add_field(name="Priority", value=priority_view.selected_priority.title(), inline=True)
                
                if assignee_ids:
                    embed.add_field(name="Assigned to", value=user_view.selected_user_name, inline=True)
                
                if due_date_unix:
                    embed.add_field(name="Due Date", value=f"<t:{int(due_date_unix/1000)}:F>", inline=True)
                
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
    
    @app_commands.command(name="task-update", description="Update an existing task with dropdowns")
    @app_commands.describe(
        new_name="New name for the task",
        new_description="New description"
    )
    async def task_update(
        self,
        interaction: discord.Interaction,
        new_name: Optional[str] = None,
        new_description: Optional[str] = None
    ):
        """Update a task with full dropdown support"""
        api = await self.get_api(interaction.guild_id)
        if not api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/clickup-setup` or `/workspace-add` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with api:
            # Step 1: Select list
            list_view = ListSelectView(api)
            await list_view.start(interaction)
            
            await list_view.wait()
            
            if not list_view.selected_list_id:
                return
            
            # Step 2: Select task
            task_view = TaskSelectView(api, list_view.selected_list_id)
            await task_view.start(interaction)
            
            await task_view.wait()
            
            if not task_view.selected_task_id:
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
                    await interaction.response.defer()
            
            update_choice = UpdateChoice()
            await interaction.edit_original_response(embed=embed, view=update_choice)
            
            await update_choice.wait()
            
            if not update_choice.confirmed:
                embed = EmbedFactory.create_info_embed("Cancelled", "Update cancelled.")
                await interaction.edit_original_response(embed=embed, view=None)
                return
            
            # Collect updates
            updates = {}
            
            if new_name:
                updates['name'] = new_name
            if new_description is not None:
                updates['description'] = new_description
            
            # Status update
            if update_choice.update_status:
                status_view = StatusSelectView(api, list_view.selected_list_id)
                await status_view.start(interaction)
                await status_view.wait()
                
                if status_view.selected_status:
                    updates['status'] = status_view.selected_status
            
            # Priority update
            if update_choice.update_priority:
                priority_view = PrioritySelectView()
                embed = EmbedFactory.create_info_embed("Select Priority", "Choose new priority level:")
                await interaction.edit_original_response(embed=embed, view=priority_view)
                await priority_view.wait()
                
                if priority_view.selected_priority:
                    updates['priority'] = {"priority": priority_view.selected_priority}
            
            # Assignee update
            if update_choice.update_assignee:
                workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
                if workspace:
                    user_view = UserSelectView(api, workspace.workspace_id)
                    await user_view.start(interaction)
                    await user_view.wait()
                    
                    if user_view.selected_user_id:
                        updates['assignees'] = [int(user_view.selected_user_id)]
            
            # Apply updates
            try:
                await api.update_task(task_view.selected_task_id, **updates)
                
                embed = EmbedFactory.create_success_embed(
                    "Task Updated",
                    f"✅ Successfully updated: **{task_view.selected_task_name}**"
                )
                
                if new_name:
                    embed.add_field(name="New Name", value=new_name, inline=True)
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
                "ClickUp hasn't been set up yet. Use `/clickup-setup` or `/workspace-add` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with api:
            # Select list
            list_view = ListSelectView(api)
            await list_view.start(interaction)
            
            await list_view.wait()
            
            if not list_view.selected_list_id:
                return
            
            # Fetch tasks
            embed = EmbedFactory.create_info_embed(
                "Loading Tasks",
                f"⏳ Loading tasks from **{list_view.selected_list_name}**..."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            try:
                tasks = await api.get_tasks(list_view.selected_list_id)
                
                if not tasks:
                    embed = EmbedFactory.create_info_embed(
                        "No Tasks",
                        f"No tasks found in **{list_view.selected_list_name}**"
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
                    f"Tasks in {list_view.selected_list_name}",
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
                "ClickUp hasn't been set up yet. Use `/clickup-setup` or `/workspace-add` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with api:
            # Select list
            list_view = ListSelectView(api)
            await list_view.start(interaction)
            
            await list_view.wait()
            
            if not list_view.selected_list_id:
                return
            
            # Select task
            task_view = TaskSelectView(api, list_view.selected_list_id)
            await task_view.start(interaction)
            
            await task_view.wait()
            
            if not task_view.selected_task_id:
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
                async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.confirmed = True
                    self.stop()
                    await interaction.response.defer()
                
                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.stop()
                    await interaction.response.defer()
            
            confirm_view = DeleteConfirm()
            await interaction.edit_original_response(embed=embed, view=confirm_view)
            
            await confirm_view.wait()
            
            if not confirm_view.confirmed:
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