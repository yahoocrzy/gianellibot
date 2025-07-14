import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Dict
from datetime import datetime, timedelta, date
import calendar
from services.clickup_api import ClickUpAPI
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from utils.embed_factory import EmbedFactory
from utils.enhanced_selections import ListSelectView
from loguru import logger

class CalendarView(discord.ui.View):
    """Interactive calendar navigation view"""
    
    def __init__(self, year: int, month: int, tasks_by_date: Dict[str, List], api: ClickUpAPI):
        super().__init__(timeout=300)
        self.year = year
        self.month = month
        self.tasks_by_date = tasks_by_date
        self.api = api
        
    def create_calendar_embed(self) -> discord.Embed:
        """Create calendar embed for the current month"""
        # Get month calendar
        cal = calendar.monthcalendar(self.year, self.month)
        month_name = calendar.month_name[self.month]
        
        # Create embed
        embed = EmbedFactory.create_info_embed(
            f"📅 {month_name} {self.year}",
            "Use the buttons below to navigate"
        )
        
        # Calendar header
        calendar_text = "```\n"
        calendar_text += "Mon Tue Wed Thu Fri Sat Sun\n"
        calendar_text += "─" * 28 + "\n"
        
        # Build calendar
        for week in cal:
            week_line = ""
            for day in week:
                if day == 0:
                    week_line += "    "
                else:
                    # Check if this day has tasks
                    date_str = f"{self.year}-{self.month:02d}-{day:02d}"
                    task_count = len(self.tasks_by_date.get(date_str, []))
                    
                    if task_count > 0:
                        # Highlight days with tasks
                        day_str = f"[{day:2d}]"
                    else:
                        day_str = f" {day:2d} "
                    
                    week_line += day_str + " "
            
            calendar_text += week_line.rstrip() + "\n"
        
        calendar_text += "```"
        
        embed.add_field(name="Calendar", value=calendar_text, inline=False)
        
        # Task summary
        total_tasks = sum(len(tasks) for tasks in self.tasks_by_date.values())
        if total_tasks > 0:
            summary_lines = []
            
            # Sort dates
            sorted_dates = sorted(self.tasks_by_date.keys())
            
            for date_str in sorted_dates[:5]:  # Show first 5 dates with tasks
                tasks = self.tasks_by_date[date_str]
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                day_name = date_obj.strftime("%b %d")
                
                # Count by priority
                priority_counts = {}
                for task in tasks:
                    priority = task.get('priority', {}).get('priority', 'none')
                    priority_counts[priority] = priority_counts.get(priority, 0) + 1
                
                priority_str = " ".join([
                    f"{count}{self.get_priority_emoji(p)}" 
                    for p, count in priority_counts.items()
                ])
                
                summary_lines.append(f"**{day_name}**: {len(tasks)} task(s) {priority_str}")
            
            if len(sorted_dates) > 5:
                summary_lines.append(f"*...and {len(sorted_dates) - 5} more days*")
            
            embed.add_field(
                name=f"📋 Tasks This Month ({total_tasks} total)",
                value="\n".join(summary_lines),
                inline=False
            )
        else:
            embed.add_field(
                name="📋 Tasks This Month",
                value="No tasks with due dates found",
                inline=False
            )
        
        # Legend
        embed.add_field(
            name="Legend",
            value="🔴 Urgent • 🟠 High • 🟡 Normal • 🔵 Low\n[##] = Day with tasks",
            inline=False
        )
        
        embed.set_footer(text="Click a date button to see tasks for that day")
        
        return embed
    
    def get_priority_emoji(self, priority: str) -> str:
        """Get emoji for priority level"""
        return {
            'urgent': '🔴',
            'high': '🟠',
            'normal': '🟡',
            'low': '🔵'
        }.get(priority, '⚪')
    
    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary, row=0)
    async def previous_month(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous month"""
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        
        await self.update_calendar(interaction)
    
    @discord.ui.button(label="Today", style=discord.ButtonStyle.success, row=0)
    async def go_to_today(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to current month"""
        today = datetime.now()
        self.year = today.year
        self.month = today.month
        
        await self.update_calendar(interaction)
    
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, row=0)
    async def next_month(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next month"""
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        
        await self.update_calendar(interaction)
    
    @discord.ui.select(
        placeholder="Select a day to view tasks...",
        min_values=1,
        max_values=1,
        row=1
    )
    async def select_day(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Show tasks for selected day"""
        selected_date = select.values[0]
        tasks = self.tasks_by_date.get(selected_date, [])
        
        if not tasks:
            await interaction.response.send_message(
                f"No tasks due on {selected_date}",
                ephemeral=True
            )
            return
        
        # Create tasks embed
        date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        embed = EmbedFactory.create_info_embed(
            f"Tasks for {date_obj.strftime('%B %d, %Y')}",
            f"Found {len(tasks)} task(s)"
        )
        
        # Group by status
        status_groups = {}
        for task in tasks:
            status = task.get('status', {}).get('status', 'No Status')
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(task)
        
        for status, group_tasks in status_groups.items():
            task_lines = []
            for task in group_tasks[:10]:  # Limit to 10 per status
                priority = task.get('priority', {})
                priority_emoji = self.get_priority_emoji(priority.get('priority', ''))
                
                assignees = task.get('assignees', [])
                assignee = f" ({assignees[0]['username']})" if assignees else ""
                
                task_lines.append(f"{priority_emoji} **{task['name']}**{assignee}")
            
            embed.add_field(
                name=f"{status.title()} ({len(group_tasks)})",
                value="\n".join(task_lines),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def update_calendar(self, interaction: discord.Interaction):
        """Update calendar display"""
        await interaction.response.defer()
        
        # Refetch tasks for new month
        start_date = date(self.year, self.month, 1)
        if self.month == 12:
            end_date = date(self.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(self.year, self.month + 1, 1) - timedelta(days=1)
        
        # This is a simplified version - in reality you'd refetch tasks
        # For now, we'll just update the display
        
        # Update day selector
        self.clear_items()
        
        # Re-add navigation buttons
        self.add_item(self.previous_month)
        self.add_item(self.go_to_today)
        self.add_item(self.next_month)
        
        # Update day selector
        days_with_tasks = []
        for date_str in self.tasks_by_date.keys():
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if date_obj.year == self.year and date_obj.month == self.month:
                    task_count = len(self.tasks_by_date[date_str])
                    days_with_tasks.append((date_obj.day, date_str, task_count))
            except:
                continue
        
        if days_with_tasks:
            days_with_tasks.sort(key=lambda x: x[0])
            
            options = []
            for day, date_str, count in days_with_tasks[:25]:  # Discord limit
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                options.append(
                    discord.SelectOption(
                        label=f"{date_obj.strftime('%B %d')} ({count} tasks)",
                        value=date_str,
                        description=f"{count} task(s) due"
                    )
                )
            
            select = discord.ui.Select(
                placeholder="Select a day to view tasks...",
                options=options,
                row=1
            )
            select.callback = self.select_day
            self.add_item(select)
        
        embed = self.create_calendar_embed()
        await interaction.edit_original_response(embed=embed, view=self)


class CalendarCommands(commands.Cog):
    """Calendar view and management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def get_api(self, guild_id: int) -> Optional[ClickUpAPI]:
        """Get ClickUp API instance"""
        workspace = await ClickUpWorkspaceRepository.get_default_workspace(guild_id)
        if workspace:
            token = await ClickUpWorkspaceRepository.get_decrypted_token(workspace)
            return ClickUpAPI(token)
        return None
    
    @app_commands.command(name="calendar", description="View tasks in a calendar format")
    async def calendar_view(self, interaction: discord.Interaction):
        """Show tasks in calendar view"""
        api = await self.get_api(interaction.guild_id)
        if not api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/workspace-add` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with api:
            # Show date selection first
            embed = EmbedFactory.create_info_embed(
                "📅 Calendar View",
                "Select the month and year to view:"
            )
            
            class DateSelectView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=180)
                    self.month = None
                    self.year = None
                    
                    # Month dropdown
                    months = [
                        "January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October", "November", "December"
                    ]
                    month_options = []
                    current_month = datetime.now().month
                    
                    for i, month_name in enumerate(months, 1):
                        month_options.append(
                            discord.SelectOption(
                                label=month_name,
                                value=str(i),
                                default=(i == current_month),
                                emoji="📅"
                            )
                        )
                    
                    month_select = discord.ui.Select(
                        placeholder="Select month...",
                        options=month_options,
                        row=0
                    )
                    month_select.callback = self.month_callback
                    self.add_item(month_select)
                    
                    # Year dropdown
                    current_year = datetime.now().year
                    year_options = []
                    
                    for year in range(current_year - 2, current_year + 3):
                        year_options.append(
                            discord.SelectOption(
                                label=str(year),
                                value=str(year),
                                default=(year == current_year),
                                emoji="📆"
                            )
                        )
                    
                    year_select = discord.ui.Select(
                        placeholder="Select year...",
                        options=year_options,
                        row=1
                    )
                    year_select.callback = self.year_callback
                    self.add_item(year_select)
                    
                    # Continue button
                    continue_btn = discord.ui.Button(
                        label="View Calendar",
                        style=discord.ButtonStyle.success,
                        row=2,
                        disabled=True
                    )
                    continue_btn.callback = self.continue_callback
                    self.add_item(continue_btn)
                    self.continue_button = continue_btn
                
                async def month_callback(self, interaction: discord.Interaction):
                    self.month = int(interaction.data['values'][0])
                    await self.check_complete(interaction)
                
                async def year_callback(self, interaction: discord.Interaction):
                    self.year = int(interaction.data['values'][0])
                    await self.check_complete(interaction)
                
                async def check_complete(self, interaction: discord.Interaction):
                    if self.month and self.year:
                        self.continue_button.disabled = False
                    await interaction.response.edit_message(view=self)
                
                async def continue_callback(self, interaction: discord.Interaction):
                    self.stop()
                    await interaction.response.defer()
            
            date_view = DateSelectView()
            await interaction.response.send_message(embed=embed, view=date_view)
            
            await date_view.wait()
            
            if not date_view.month or not date_view.year:
                return
                
            target_month = date_view.month
            target_year = date_view.year
            
            # Now select list
            list_view = ListSelectView(api)
            await list_view.start(interaction)
            
            await list_view.wait()
            
            if not list_view.selected_list_id:
                return
            
            # Fetch tasks
            embed = EmbedFactory.create_info_embed(
                "Loading Calendar",
                f"⏳ Loading tasks from **{list_view.selected_list_name}**..."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            try:
                # Get tasks with due dates
                tasks = await api.get_tasks(list_view.selected_list_id)
                
                # Organize tasks by date
                tasks_by_date = {}
                for task in tasks:
                    if task.get('due_date'):
                        # Convert timestamp to date
                        due_timestamp = int(task['due_date']) / 1000
                        due_date = datetime.fromtimestamp(due_timestamp)
                        date_str = due_date.strftime("%Y-%m-%d")
                        
                        if date_str not in tasks_by_date:
                            tasks_by_date[date_str] = []
                        tasks_by_date[date_str].append(task)
                
                # Create calendar view
                calendar_view = CalendarView(target_year, target_month, tasks_by_date, api)
                embed = calendar_view.create_calendar_embed()
                
                await interaction.edit_original_response(embed=embed, view=calendar_view)
                
            except Exception as e:
                logger.error(f"Error loading calendar: {e}")
                embed = EmbedFactory.create_error_embed(
                    "Error",
                    f"Failed to load calendar: {str(e)}"
                )
                await interaction.edit_original_response(embed=embed, view=None)
    
    @app_commands.command(name="upcoming", description="Show upcoming tasks for the next few days")
    async def upcoming_tasks(self, interaction: discord.Interaction):
        """Show upcoming tasks"""
        api = await self.get_api(interaction.guild_id)
        if not api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/workspace-add` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with api:
            # Show days selection first
            embed = EmbedFactory.create_info_embed(
                "📅 Upcoming Tasks",
                "How many days ahead would you like to see?"
            )
            
            class DaysSelectView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                    self.days = None
                    
                    options = [
                        discord.SelectOption(label="Today only", value="1", emoji="📅"),
                        discord.SelectOption(label="Next 3 days", value="3", emoji="📆"),
                        discord.SelectOption(label="Next week (7 days)", value="7", emoji="📍", default=True),
                        discord.SelectOption(label="Next 2 weeks", value="14", emoji="📎"),
                        discord.SelectOption(label="Next month (30 days)", value="30", emoji="🗓️")
                    ]
                    
                    select = discord.ui.Select(
                        placeholder="Select time range...",
                        options=options
                    )
                    select.callback = self.select_callback
                    self.add_item(select)
                
                async def select_callback(self, interaction: discord.Interaction):
                    self.days = int(interaction.data['values'][0])
                    self.stop()
                    await interaction.response.defer()
            
            days_view = DaysSelectView()
            await interaction.response.send_message(embed=embed, view=days_view)
            
            await days_view.wait()
            
            if not days_view.days:
                return
                
            days = days_view.days
            
            # Select list
            list_view = ListSelectView(api)
            await list_view.start(interaction)
            
            await list_view.wait()
            
            if not list_view.selected_list_id:
                return
            
            # Fetch tasks
            embed = EmbedFactory.create_info_embed(
                "Loading Upcoming Tasks",
                f"⏳ Loading tasks from **{list_view.selected_list_name}**..."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            try:
                tasks = await api.get_tasks(list_view.selected_list_id)
                
                # Filter for upcoming tasks
                now = datetime.now()
                end_date = now + timedelta(days=days)
                
                upcoming = []
                overdue = []
                
                for task in tasks:
                    if task.get('due_date'):
                        due_timestamp = int(task['due_date']) / 1000
                        due_date = datetime.fromtimestamp(due_timestamp)
                        
                        if due_date < now:
                            overdue.append((due_date, task))
                        elif due_date <= end_date:
                            upcoming.append((due_date, task))
                
                # Sort by date
                upcoming.sort(key=lambda x: x[0])
                overdue.sort(key=lambda x: x[0], reverse=True)
                
                # Create embed
                embed = EmbedFactory.create_info_embed(
                    f"📅 Upcoming Tasks - Next {days} Days",
                    f"From list: **{list_view.selected_list_name}**"
                )
                
                # Overdue tasks
                if overdue:
                    overdue_text = []
                    for due_date, task in overdue[:5]:
                        days_overdue = (now - due_date).days
                        priority = task.get('priority', {}).get('priority', '')
                        priority_emoji = {
                            'urgent': '🔴',
                            'high': '🟠',
                            'normal': '🟡',
                            'low': '🔵'
                        }.get(priority, '⚪')
                        
                        overdue_text.append(
                            f"{priority_emoji} **{task['name']}**\n"
                            f"   ⚠️ {days_overdue} day{'s' if days_overdue != 1 else ''} overdue"
                        )
                    
                    if len(overdue) > 5:
                        overdue_text.append(f"*...and {len(overdue) - 5} more*")
                    
                    embed.add_field(
                        name=f"🚨 Overdue ({len(overdue)})",
                        value="\n".join(overdue_text),
                        inline=False
                    )
                
                # Upcoming tasks by day
                if upcoming:
                    current_day = None
                    day_tasks = []
                    
                    for due_date, task in upcoming:
                        day_str = due_date.strftime("%A, %B %d")
                        
                        if day_str != current_day:
                            if current_day and day_tasks:
                                # Add previous day's tasks
                                embed.add_field(
                                    name=current_day,
                                    value="\n".join(day_tasks[:5]),
                                    inline=False
                                )
                            
                            current_day = day_str
                            day_tasks = []
                        
                        priority = task.get('priority', {}).get('priority', '')
                        priority_emoji = {
                            'urgent': '🔴',
                            'high': '🟠',
                            'normal': '🟡',
                            'low': '🔵'
                        }.get(priority, '⚪')
                        
                        assignees = task.get('assignees', [])
                        assignee = f" ({assignees[0]['username']})" if assignees else ""
                        
                        time_str = due_date.strftime("%I:%M %p")
                        day_tasks.append(f"{priority_emoji} **{task['name']}**{assignee} - {time_str}")
                    
                    # Add last day's tasks
                    if current_day and day_tasks:
                        embed.add_field(
                            name=current_day,
                            value="\n".join(day_tasks[:5]),
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="No Upcoming Tasks",
                        value=f"No tasks due in the next {days} days",
                        inline=False
                    )
                
                # Summary
                total_shown = len(overdue) + len(upcoming)
                embed.set_footer(text=f"Showing {total_shown} task(s) with due dates")
                
                await interaction.edit_original_response(embed=embed)
                
            except Exception as e:
                logger.error(f"Error loading upcoming tasks: {e}")
                embed = EmbedFactory.create_error_embed(
                    "Error",
                    f"Failed to load tasks: {str(e)}"
                )
                await interaction.edit_original_response(embed=embed)
    
    @app_commands.command(name="today", description="Show tasks due today")
    async def today_tasks(self, interaction: discord.Interaction):
        """Show tasks due today"""
        api = await self.get_api(interaction.guild_id)
        if not api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured", 
                "ClickUp hasn't been set up yet. Use `/workspace-add` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with api:
            # Get all workspaces
            workspaces = await ClickUpWorkspaceRepository.get_all_workspaces(interaction.guild_id)
            
            if not workspaces:
                embed = EmbedFactory.create_error_embed(
                    "No Workspaces",
                    "No workspaces configured. Use `/workspace-add` first."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.response.defer()
            
            # Collect tasks from all workspaces
            all_today_tasks = []
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            
            for workspace in workspaces:
                try:
                    # Get API for this workspace
                    ws_token = await ClickUpWorkspaceRepository.get_decrypted_token(workspace)
                    ws_api = ClickUpAPI(ws_token)
                    
                    async with ws_api:
                        # Get all spaces
                        spaces = await ws_api.get_spaces(workspace.workspace_id)
                        
                        for space in spaces:
                            # Get lists
                            lists = await ws_api.get_lists(space['id'])
                            
                            for lst in lists:
                                tasks = await ws_api.get_tasks(lst['id'])
                                
                                for task in tasks:
                                    if task.get('due_date'):
                                        due_timestamp = int(task['due_date']) / 1000
                                        due_date = datetime.fromtimestamp(due_timestamp)
                                        
                                        if today_start <= due_date < today_end:
                                            all_today_tasks.append({
                                                'task': task,
                                                'workspace': workspace.workspace_name,
                                                'list': lst['name']
                                            })
                
                except Exception as e:
                    logger.error(f"Error fetching tasks from workspace {workspace.workspace_name}: {e}")
                    continue
            
            # Create embed
            if all_today_tasks:
                embed = EmbedFactory.create_info_embed(
                    f"📅 Today's Tasks - {datetime.now().strftime('%B %d, %Y')}",
                    f"Found {len(all_today_tasks)} task(s) due today"
                )
                
                # Group by workspace
                by_workspace = {}
                for item in all_today_tasks:
                    ws_name = item['workspace']
                    if ws_name not in by_workspace:
                        by_workspace[ws_name] = []
                    by_workspace[ws_name].append(item)
                
                for ws_name, items in by_workspace.items():
                    task_lines = []
                    
                    for item in items[:10]:  # Limit per workspace
                        task = item['task']
                        priority = task.get('priority', {}).get('priority', '')
                        priority_emoji = {
                            'urgent': '🔴',
                            'high': '🟠', 
                            'normal': '🟡',
                            'low': '🔵'
                        }.get(priority, '⚪')
                        
                        status = task.get('status', {}).get('status', 'no status')
                        status_emoji = '✅' if status == 'complete' else '🔄'
                        
                        task_lines.append(
                            f"{priority_emoji} {status_emoji} **{task['name']}**\n"
                            f"   📋 {item['list']}"
                        )
                    
                    embed.add_field(
                        name=f"🏢 {ws_name} ({len(items)})",
                        value="\n".join(task_lines),
                        inline=False
                    )
            else:
                embed = EmbedFactory.create_info_embed(
                    "No Tasks Today",
                    "🎉 You have no tasks due today!"
                )
                
                embed.add_field(
                    name="Quick Actions",
                    value="• Use `/upcoming` to see future tasks\n"
                          "• Use `/calendar` to view the full month\n"
                          "• Use `/task-create` to add new tasks",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CalendarCommands(bot))