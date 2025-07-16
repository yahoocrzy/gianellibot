import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import json
from datetime import datetime
from services.clickup_api import ClickUpAPI
from services.claude_api import ClaudeAPI
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from repositories.claude_config import ClaudeConfigRepository
from utils.embed_factory import EmbedFactory
from utils.enhanced_selections import ListSelectView, TaskSelectView, UserSelectView
from utils.helpers import parse_due_date
from loguru import logger

class AIActionView(discord.ui.View):
    """View for selecting AI actions"""
    
    def __init__(self, clickup_api: ClickUpAPI, claude_api: ClaudeAPI):
        super().__init__(timeout=300)
        self.clickup_api = clickup_api
        self.claude_api = claude_api
        self.selected_action = None
        
        # Create action dropdown
        options = [
            discord.SelectOption(
                label="Create Task",
                value="create_task",
                description="Create a new task with AI assistance",
                emoji="➕"
            ),
            discord.SelectOption(
                label="Find Tasks",
                value="find_tasks",
                description="Search and filter tasks",
                emoji="🔍"
            ),
            discord.SelectOption(
                label="Update Tasks",
                value="update_tasks",
                description="Modify existing tasks",
                emoji="✏️"
            ),
            discord.SelectOption(
                label="Task Status Report",
                value="status_report",
                description="Get status overview of tasks",
                emoji="📊"
            ),
            discord.SelectOption(
                label="Due Date Analysis",
                value="due_dates",
                description="Analyze upcoming due dates",
                emoji="📅"
            ),
            discord.SelectOption(
                label="Workload Analysis",
                value="workload",
                description="Check team workload distribution",
                emoji="👥"
            ),
            discord.SelectOption(
                label="Priority Review",
                value="priority_review",
                description="Review and suggest task priorities",
                emoji="🎯"
            ),
            discord.SelectOption(
                label="Weekly Summary",
                value="weekly_summary",
                description="Get weekly task summary",
                emoji="📈"
            )
        ]
        
        select = discord.ui.Select(
            placeholder="What would you like AI to help with?",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.action_callback
        self.add_item(select)
    
    async def action_callback(self, interaction: discord.Interaction):
        """Handle action selection"""
        self.selected_action = interaction.data['values'][0]
        self.stop()
        await interaction.response.defer()


class AICreateTaskView(discord.ui.View):
    """View for AI task creation with dropdowns"""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.task_type = None
        self.priority = None
        self.due_option = None
        
    async def start(self, interaction: discord.Interaction):
        """Start the task creation flow"""
        # Task type dropdown
        type_options = [
            discord.SelectOption(label="Bug Fix", value="bug", emoji="🐛"),
            discord.SelectOption(label="Feature", value="feature", emoji="✨"),
            discord.SelectOption(label="Task", value="task", emoji="📋"),
            discord.SelectOption(label="Documentation", value="docs", emoji="📝"),
            discord.SelectOption(label="Testing", value="test", emoji="🧪"),
            discord.SelectOption(label="Meeting", value="meeting", emoji="🤝"),
            discord.SelectOption(label="Review", value="review", emoji="👀"),
            discord.SelectOption(label="Other", value="other", emoji="📌")
        ]
        
        type_select = discord.ui.Select(
            placeholder="Select task type...",
            options=type_options,
            row=0
        )
        type_select.callback = self.type_callback
        self.add_item(type_select)
        
        # Priority dropdown
        priority_options = [
            discord.SelectOption(label="🔴 Urgent", value="urgent"),
            discord.SelectOption(label="🟠 High", value="high"),
            discord.SelectOption(label="🟡 Normal", value="normal"),
            discord.SelectOption(label="🔵 Low", value="low")
        ]
        
        priority_select = discord.ui.Select(
            placeholder="Select priority...",
            options=priority_options,
            row=1
        )
        priority_select.callback = self.priority_callback
        self.add_item(priority_select)
        
        # Due date dropdown
        due_options = [
            discord.SelectOption(label="Today", value="today", emoji="📅"),
            discord.SelectOption(label="Tomorrow", value="tomorrow", emoji="📆"),
            discord.SelectOption(label="This Week", value="this_week", emoji="📍"),
            discord.SelectOption(label="Next Week", value="next_week", emoji="📎"),
            discord.SelectOption(label="This Month", value="this_month", emoji="🗓️"),
            discord.SelectOption(label="No Due Date", value="none", emoji="♾️")
        ]
        
        due_select = discord.ui.Select(
            placeholder="Select due date...",
            options=due_options,
            row=2
        )
        due_select.callback = self.due_callback
        self.add_item(due_select)
        
        # Continue button
        continue_btn = discord.ui.Button(
            label="Continue",
            style=discord.ButtonStyle.success,
            row=3,
            disabled=True
        )
        continue_btn.callback = self.continue_callback
        self.add_item(continue_btn)
        self.continue_button = continue_btn
        
        embed = EmbedFactory.create_info_embed(
            "🤖 AI Task Creation",
            "Select the task details below. I'll help you create it!"
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def type_callback(self, interaction: discord.Interaction):
        self.task_type = interaction.data['values'][0]
        await self.check_complete(interaction)
    
    async def priority_callback(self, interaction: discord.Interaction):
        self.priority = interaction.data['values'][0]
        await self.check_complete(interaction)
    
    async def due_callback(self, interaction: discord.Interaction):
        self.due_option = interaction.data['values'][0]
        await self.check_complete(interaction)
    
    async def check_complete(self, interaction: discord.Interaction):
        """Check if all selections are made"""
        if self.task_type and self.priority and self.due_option:
            self.continue_button.disabled = False
        await interaction.response.edit_message(view=self)
    
    async def continue_callback(self, interaction: discord.Interaction):
        """Continue to task name selection"""
        self.stop()
        await interaction.response.defer_update()




class AICompleteDropdown(commands.Cog):
    """AI commands with full dropdown support"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="ai", description="AI assistant with dropdown selections")
    async def ai_dropdown(self, interaction: discord.Interaction):
        """AI command with dropdown interface"""
        
        # Check configuration using workspace repository
        from repositories.clickup_workspaces import ClickUpWorkspaceRepository
        
        # Get default workspace and API
        default_workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
        if not default_workspace:
            clickup_api = None
        else:
            token = await ClickUpWorkspaceRepository.get_decrypted_token(default_workspace)
            clickup_api = ClickUpAPI(token) if token else None
        if not clickup_api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/clickup-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        config = await ClaudeConfigRepository.get_config(interaction.guild_id)
        if not config:
            embed = EmbedFactory.create_error_embed(
                "AI Not Configured",
                "Claude AI hasn't been set up yet. Use `/claude-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get Claude API
        api_key = await ClaudeConfigRepository.get_decrypted_api_key(config)
        claude_api = ClaudeAPI(api_key)
        
        # Show action selection
        embed = EmbedFactory.create_info_embed(
            "🤖 AI Assistant",
            "I'm here to help with your ClickUp tasks! Select an action below:"
        )
        
        view = AIActionView(clickup_api, claude_api)
        await interaction.response.send_message(embed=embed, view=view)
        
        # Wait for selection
        await view.wait()
        
        if not view.selected_action:
            return
        
        # Route to appropriate handler
        async with clickup_api:
            if view.selected_action == "create_task":
                await self._handle_create_task(interaction, clickup_api, claude_api)
            elif view.selected_action == "find_tasks":
                await self._handle_find_tasks(interaction, clickup_api, claude_api)
            elif view.selected_action == "update_tasks":
                await self._handle_update_tasks(interaction, clickup_api, claude_api)
            elif view.selected_action == "status_report":
                await self._handle_status_report(interaction, clickup_api, claude_api)
            elif view.selected_action == "due_dates":
                await self._handle_due_dates(interaction, clickup_api, claude_api)
            elif view.selected_action == "workload":
                await self._handle_workload(interaction, clickup_api, claude_api)
            elif view.selected_action == "priority_review":
                await self._handle_priority_review(interaction, clickup_api, claude_api)
            elif view.selected_action == "weekly_summary":
                await self._handle_weekly_summary(interaction, clickup_api, claude_api)
    
    async def _handle_create_task(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI
    ):
        """Handle AI task creation with dropdowns"""
        create_view = AICreateTaskView()
        await create_view.start(interaction)
        
        await create_view.wait()
        
        # Get the modal result
        if hasattr(create_view, 'continue_button') and create_view.continue_button.disabled == False:
            # User completed all selections
            # The modal will handle the task creation
            pass
    
    async def _handle_find_tasks(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI
    ):
        """Handle finding tasks with filters"""
        # Create filter view
        embed = EmbedFactory.create_info_embed(
            "🔍 Find Tasks",
            "Select filters to find specific tasks:"
        )
        
        class FilterView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
                self.filters = {}
                
                # Status filter
                status_options = [
                    discord.SelectOption(label="All Statuses", value="all"),
                    discord.SelectOption(label="To Do", value="to do"),
                    discord.SelectOption(label="In Progress", value="in progress"),
                    discord.SelectOption(label="Done", value="done"),
                    discord.SelectOption(label="Closed", value="closed")
                ]
                
                status_select = discord.ui.Select(
                    placeholder="Filter by status...",
                    options=status_options,
                    row=0
                )
                status_select.callback = self.status_callback
                self.add_item(status_select)
                
                # Priority filter
                priority_options = [
                    discord.SelectOption(label="All Priorities", value="all"),
                    discord.SelectOption(label="🔴 Urgent Only", value="urgent"),
                    discord.SelectOption(label="🟠 High & Above", value="high"),
                    discord.SelectOption(label="🟡 Normal & Above", value="normal")
                ]
                
                priority_select = discord.ui.Select(
                    placeholder="Filter by priority...",
                    options=priority_options,
                    row=1
                )
                priority_select.callback = self.priority_callback
                self.add_item(priority_select)
                
                # Search button
                search_btn = discord.ui.Button(
                    label="Search Tasks",
                    style=discord.ButtonStyle.success,
                    row=2
                )
                search_btn.callback = self.search_callback
                self.add_item(search_btn)
                
            async def status_callback(self, interaction: discord.Interaction):
                self.filters['status'] = interaction.data['values'][0]
                await interaction.response.defer()
                
            async def priority_callback(self, interaction: discord.Interaction):
                self.filters['priority'] = interaction.data['values'][0]
                await interaction.response.defer()
                
            async def search_callback(self, interaction: discord.Interaction):
                self.stop()
                await interaction.response.defer()
        
        filter_view = FilterView()
        await interaction.edit_original_response(embed=embed, view=filter_view)
        
        await filter_view.wait()
        
        # Execute search with filters
        await self._execute_task_search(
            interaction,
            clickup_api,
            claude_api,
            filter_view.filters
        )
    
    async def _handle_update_tasks(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI
    ):
        """Handle task updates with dropdowns"""
        # First select the list
        list_view = ListSelectView(clickup_api)
        await list_view.start(interaction)
        await list_view.wait()
        
        if not list_view.selected_list_id:
            return
        
        # Then select the task
        task_view = TaskSelectView(clickup_api, list_view.selected_list_id)
        await task_view.start(interaction)
        await task_view.wait()
        
        if not task_view.selected_task_id:
            return
        
        # Show update options
        embed = EmbedFactory.create_info_embed(
            "✏️ Update Task",
            f"Updating: **{task_view.selected_task_name}**\n\nWhat would you like to change?"
        )
        
        class UpdateView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
                
            @discord.ui.button(label="Change Status", style=discord.ButtonStyle.primary, row=0)
            async def change_status(self, interaction: discord.Interaction, button: discord.ui.Button):
                # Implementation would show status dropdown
                await interaction.response.send_message("Status update coming soon!", ephemeral=True)
                
            @discord.ui.button(label="Change Priority", style=discord.ButtonStyle.primary, row=0)
            async def change_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
                # Implementation would show priority dropdown
                await interaction.response.send_message("Priority update coming soon!", ephemeral=True)
                
            @discord.ui.button(label="Change Due Date", style=discord.ButtonStyle.primary, row=0)
            async def change_due_date(self, interaction: discord.Interaction, button: discord.ui.Button):
                # Implementation would show due date dropdown
                await interaction.response.send_message("Due date update coming soon!", ephemeral=True)
                
            @discord.ui.button(label="Assign User", style=discord.ButtonStyle.primary, row=1)
            async def assign_user(self, interaction: discord.Interaction, button: discord.ui.Button):
                # Implementation would show user dropdown
                await interaction.response.send_message("User assignment coming soon!", ephemeral=True)
        
        update_view = UpdateView()
        await interaction.edit_original_response(embed=embed, view=update_view)
    
    async def _handle_status_report(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI
    ):
        """Generate status report"""
        embed = EmbedFactory.create_info_embed(
            "📊 Generating Status Report",
            "Analyzing your tasks..."
        )
        await interaction.edit_original_response(embed=embed, view=None)
        
        # Get all tasks
        try:
            workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
            if not workspace:
                embed = EmbedFactory.create_error_embed(
                    "No Workspace",
                    "No default workspace found. Please configure a workspace first."
                )
                await interaction.edit_original_response(embed=embed)
                return
                
            all_tasks = []
            spaces = await clickup_api.get_spaces(workspace.workspace_id)
            for space in spaces[:2]:
                lists = await clickup_api.get_lists(space['id'])
                for lst in lists[:5]:
                    tasks = await clickup_api.get_tasks(lst['id'])
                    all_tasks.extend(tasks)
            
            # Generate report with AI
            prompt = f"""Generate a status report for these tasks:
{json.dumps([{
    'name': t['name'],
    'status': t.get('status', {}).get('status'),
    'priority': t.get('priority', {}).get('priority')
} for t in all_tasks[:30]], indent=2)}

Include:
1. Task count by status
2. Priority distribution
3. Key insights
4. Recommendations"""

            report = await claude_api.create_message(prompt, max_tokens=1000)
            
            embed = EmbedFactory.create_info_embed(
                "📊 Status Report",
                report[:2000] if report else "Unable to generate report"
            )
            
            await interaction.edit_original_response(embed=embed)
            
        except Exception as e:
            logger.error(f"Error generating status report: {e}")
            embed = EmbedFactory.create_error_embed(
                "Report Failed",
                f"Failed to generate status report: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed)
    
    async def _handle_due_dates(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI
    ):
        """Analyze due dates"""
        # Implementation similar to status report but focused on due dates
        embed = EmbedFactory.create_info_embed(
            "📅 Due Date Analysis",
            "This feature is coming soon!"
        )
        await interaction.edit_original_response(embed=embed, view=None)
    
    async def _handle_workload(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI
    ):
        """Analyze workload distribution"""
        embed = EmbedFactory.create_info_embed(
            "👥 Workload Analysis",
            "This feature is coming soon!"
        )
        await interaction.edit_original_response(embed=embed, view=None)
    
    async def _handle_priority_review(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI
    ):
        """Review and suggest priorities"""
        embed = EmbedFactory.create_info_embed(
            "🎯 Priority Review",
            "This feature is coming soon!"
        )
        await interaction.edit_original_response(embed=embed, view=None)
    
    async def _handle_weekly_summary(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI
    ):
        """Generate weekly summary"""
        embed = EmbedFactory.create_info_embed(
            "📈 Weekly Summary",
            "This feature is coming soon!"
        )
        await interaction.edit_original_response(embed=embed, view=None)
    
    async def _execute_task_search(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI,
        filters: dict
    ):
        """Execute task search with filters"""
        embed = EmbedFactory.create_info_embed(
            "🔍 Searching Tasks",
            f"Applying filters: {filters}"
        )
        await interaction.edit_original_response(embed=embed, view=None)
        
        # Implementation would search tasks with filters
        # For now, show placeholder
        embed = EmbedFactory.create_success_embed(
            "Search Complete",
            "Task search with filters is coming soon!"
        )
        await interaction.edit_original_response(embed=embed)

async def setup(bot):
    await bot.add_cog(AICompleteDropdown(bot))