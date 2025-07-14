import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio
from services.clickup_api import ClickUpAPI
from services.security import security_service
from repositories.server_config import ServerConfigRepository
from utils.embed_factory import EmbedFactory
from utils.helpers import parse_due_date, format_task_status
from loguru import logger

class TaskView(discord.ui.View):
    def __init__(self, task_data: dict, api: ClickUpAPI):
        super().__init__(timeout=180)
        self.task_data = task_data
        self.api = api
        
    @discord.ui.button(label="Complete", style=discord.ButtonStyle.success)
    async def complete_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.api.update_task(self.task_data['id'], status='complete')
            embed = EmbedFactory.create_success_embed(
                "Task Completed",
                f"✅ Task '{self.task_data['name']}' marked as complete!"
            )
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to complete task: {str(e)}",
                ephemeral=True
            )
    
    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary)
    async def edit_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditTaskModal(self.task_data, self.api)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Confirmation view
        confirm_view = ConfirmDeleteView(self.task_data, self.api)
        embed = EmbedFactory.create_warning_embed(
            "Confirm Deletion",
            f"Are you sure you want to delete task '{self.task_data['name']}'?"
        )
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)

class EditTaskModal(discord.ui.Modal, title="Edit Task"):
    def __init__(self, task_data: dict, api: ClickUpAPI):
        super().__init__()
        self.task_data = task_data
        self.api = api
        
        # Pre-fill with current values
        self.name = discord.ui.TextInput(
            label="Task Name",
            default=task_data['name'],
            max_length=200
        )
        self.description = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            default=task_data.get('description', ''),
            required=False,
            max_length=1000
        )
        
        self.add_item(self.name)
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.api.update_task(
                self.task_data['id'],
                name=self.name.value,
                description=self.description.value
            )
            
            embed = EmbedFactory.create_success_embed(
                "Task Updated",
                f"✅ Task '{self.name.value}' has been updated!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to update task: {str(e)}",
                ephemeral=True
            )

class ConfirmDeleteView(discord.ui.View):
    def __init__(self, task_data: dict, api: ClickUpAPI):
        super().__init__(timeout=30)
        self.task_data = task_data
        self.api = api
    
    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.api.delete_task(self.task_data['id'])
            embed = EmbedFactory.create_success_embed(
                "Task Deleted",
                f"Task '{self.task_data['name']}' has been deleted."
            )
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception as e:
            await interaction.response.send_message(
                f"Failed to delete task: {str(e)}",
                ephemeral=True
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Deletion cancelled.",
            embed=None,
            view=None
        )

class ClickUpTasks(commands.Cog):
    """ClickUp task management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        # Add the command group to the bot tree
        self.bot.tree.add_command(self.task_group)
    
    async def cog_unload(self):
        """Called when the cog is unloaded"""
        # Remove the command group from the bot tree
        self.bot.tree.remove_command(self.task_group.name)
    
    async def _get_api(self, guild_id: int) -> Optional[ClickUpAPI]:
        """Get ClickUp API instance for guild"""
        repo = ServerConfigRepository()
        config = await repo.get_config(guild_id)
        
        if not config or not config.get('clickup_token_encrypted'):
            return None
            
        token = security_service.decrypt(config['clickup_token_encrypted'])
        return ClickUpAPI(token)
    
    # Create an app_commands group for slash commands
    task_group = app_commands.Group(name="task", description="ClickUp task management commands")
    
    @task_group.command(name="create", description="Create a new task")
    @app_commands.describe(
        name="Task name",
        description="Task description",
        list_id="List ID (optional, uses default if not provided)",
        priority="Priority (1=Urgent, 2=High, 3=Normal, 4=Low)",
        due_date="Due date (e.g., 'tomorrow', 'next week', '2024-01-15')"
    )
    async def create_task(
        self,
        interaction: discord.Interaction,
        name: str,
        description: Optional[str] = None,
        list_id: Optional[str] = None,
        priority: Optional[int] = 3,
        due_date: Optional[str] = None
    ):
        """Create a new task"""
        api = await self._get_api(interaction.guild.id)
        if not api:
            await interaction.response.send_message("❌ ClickUp is not configured. Run `/clickup-setup` first.", ephemeral=True)
            return
        
        async with api:
            try:
                # Parse due date if provided
                due_timestamp = None
                if due_date:
                    parsed_date = parse_due_date(due_date)
                    if parsed_date:
                        due_timestamp = int(parsed_date.timestamp() * 1000)
                
                # Get default list if not provided
                if not list_id:
                    # This would come from user preferences or server config
                    await interaction.response.send_message("❌ Please provide a list ID or set a default list.", ephemeral=True)
                    return
                
                # Create task
                task_data = {
                    "name": name,
                    "priority": priority
                }
                
                if description:
                    task_data["description"] = description
                if due_timestamp:
                    task_data["due_date"] = due_timestamp
                
                task = await api.create_task(list_id, **task_data)
                
                # Create response embed
                embed = discord.Embed(
                    title="✅ Task Created",
                    color=discord.Color.green()
                )
                embed.add_field(name="Name", value=task['name'], inline=False)
                embed.add_field(name="ID", value=task['id'], inline=True)
                embed.add_field(name="Status", value=task['status']['status'], inline=True)
                
                if task.get('url'):
                    embed.add_field(name="Link", value=f"[Open in ClickUp]({task['url']})", inline=False)
                
                # Add task action buttons
                view = TaskView(task, api)
                await interaction.response.send_message(embed=embed, view=view)
                
            except Exception as e:
                logger.error(f"Failed to create task: {e}")
                await interaction.response.send_message(f"❌ Failed to create task: {str(e)}", ephemeral=True)
    
    @task_group.command(name="list", description="List tasks")
    @app_commands.describe(
        list_id="List ID to fetch tasks from",
        status="Filter by status",
        assignee="Filter by assignee (user mention or ID)"
    )
    async def list_tasks(
        self,
        interaction: discord.Interaction,
        list_id: str,
        status: Optional[str] = None,
        assignee: Optional[discord.Member] = None
    ):
        """List tasks from a list"""
        api = await self._get_api(interaction.guild.id)
        if not api:
            await interaction.response.send_message("❌ ClickUp is not configured. Run `/clickup-setup` first.", ephemeral=True)
            return
        
        async with api:
            try:
                params = {}
                if status:
                    params['statuses'] = [status]
                if assignee:
                    # You'd need to map Discord user to ClickUp user
                    pass
                
                tasks = await api.get_tasks(list_id, **params)
                
                if not tasks:
                    await interaction.response.send_message("No tasks found.", ephemeral=True)
                    return
                
                # Create paginated embed
                embed = discord.Embed(
                    title="📋 Tasks",
                    color=discord.Color.blue()
                )
                
                for task in tasks[:10]:  # Show first 10
                    status_emoji = format_task_status(task['status']['status'])
                    priority_emoji = ["🔴", "🟠", "🟡", "⚪"][task.get('priority', {}).get('id', 4) - 1]
                    
                    field_value = f"{status_emoji} Status: {task['status']['status']}\n"
                    field_value += f"{priority_emoji} Priority: {task.get('priority', {}).get('priority', 'None')}\n"
                    
                    if task.get('due_date'):
                        due = datetime.fromtimestamp(int(task['due_date']) / 1000)
                        field_value += f"📅 Due: {due.strftime('%Y-%m-%d')}\n"
                    
                    embed.add_field(
                        name=f"{task['name']} ({task['id']})",
                        value=field_value,
                        inline=False
                    )
                
                if len(tasks) > 10:
                    embed.set_footer(text=f"Showing 10 of {len(tasks)} tasks")
                
                await interaction.response.send_message(embed=embed)
                
            except Exception as e:
                logger.error(f"Failed to list tasks: {e}")
                await interaction.response.send_message(f"❌ Failed to list tasks: {str(e)}", ephemeral=True)
    
    @task_group.command(name="update", description="Update a task")
    @app_commands.describe(
        task_id="Task ID to update",
        name="New task name",
        description="New description",
        status="New status",
        priority="New priority (1-4)"
    )
    async def update_task(
        self,
        interaction: discord.Interaction,
        task_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None
    ):
        """Update an existing task"""
        api = await self._get_api(interaction.guild.id)
        if not api:
            await interaction.response.send_message("❌ ClickUp is not configured. Run `/clickup-setup` first.", ephemeral=True)
            return
        
        async with api:
            try:
                update_data = {}
                if name:
                    update_data['name'] = name
                if description is not None:
                    update_data['description'] = description
                if status:
                    update_data['status'] = status
                if priority:
                    update_data['priority'] = priority
                
                task = await api.update_task(task_id, **update_data)
                
                embed = EmbedFactory.create_success_embed(
                    "Task Updated",
                    f"Task '{task['name']}' has been updated successfully."
                )
                embed.add_field(name="ID", value=task['id'], inline=True)
                embed.add_field(name="Status", value=task['status']['status'], inline=True)
                
                await interaction.response.send_message(embed=embed)
                
            except Exception as e:
                logger.error(f"Failed to update task: {e}")
                await interaction.response.send_message(f"❌ Failed to update task: {str(e)}")
    
    @task_group.command(name="delete", description="Delete a task")
    @app_commands.describe(task_id="Task ID to delete")
    async def delete_task(self, interaction: discord.Interaction, task_id: str):
        """Delete a task"""
        api = await self._get_api(interaction.guild.id)
        if not api:
            await interaction.response.send_message("❌ ClickUp is not configured. Run `/clickup-setup` first.", ephemeral=True)
            return
        
        # Confirmation view
        view = ConfirmView()
        await interaction.response.send_message(
            f"⚠️ Are you sure you want to delete task `{task_id}`?",
            view=view
        )
        
        await view.wait()
        
        if view.value:
            async with api:
                try:
                    await api.delete_task(task_id)
                    await interaction.followup.send(f"✅ Task `{task_id}` has been deleted.")
                except Exception as e:
                    logger.error(f"Failed to delete task: {e}")
                    await interaction.followup.send(f"❌ Failed to delete task: {str(e)}")
        else:
            await interaction.followup.send("Task deletion cancelled.")
    
    @task_group.command(name="comment", description="Add a comment to a task")
    @app_commands.describe(
        task_id="Task ID to comment on",
        comment="Comment text"
    )
    async def add_comment(self, interaction: discord.Interaction, task_id: str, *, comment: str):
        """Add a comment to a task"""
        api = await self._get_api(interaction.guild.id)
        if not api:
            await interaction.response.send_message("❌ ClickUp is not configured. Run `/clickup-setup` first.", ephemeral=True)
            return
        
        async with api:
            try:
                result = await api.create_comment(
                    task_id,
                    comment,
                    notify_all=False
                )
                
                await interaction.response.send_message(f"✅ Comment added to task `{task_id}`")
                
            except Exception as e:
                logger.error(f"Failed to add comment: {e}")
                await interaction.response.send_message(f"❌ Failed to add comment: {str(e)}")
    
    @task_group.command(name="assign", description="Assign users to a task")
    @app_commands.describe(
        task_id="Task ID to assign user to",
        user="Discord user to assign"
    )
    async def assign_task(self, interaction: discord.Interaction, task_id: str, user: discord.Member):
        """Assign a user to a task"""
        
        api = await self._get_api(interaction.guild.id)
        if not api:
            await interaction.response.send_message("❌ ClickUp is not configured. Run `/clickup-setup` first.", ephemeral=True)
            return
        
        # Note: You would need to implement Discord -> ClickUp user mapping
        await interaction.response.send_message("⚠️ User mapping between Discord and ClickUp is not yet implemented.")

class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.edit_message(content="Confirmed.", view=None)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.edit_message(content="Cancelled.", view=None)

async def setup(bot):
    await bot.add_cog(ClickUpTasks(bot))