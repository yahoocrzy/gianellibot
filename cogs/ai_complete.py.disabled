import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timedelta
from services.clickup_api import ClickUpAPI
from services.claude_api import ClaudeAPI
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from repositories.claude_config import ClaudeConfigRepository
from utils.embed_factory import EmbedFactory
from utils.helpers import parse_due_date
from loguru import logger

class AIComplete(commands.Cog):
    """Complete AI integration for natural language ClickUp management"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def get_apis(self, guild_id: int) -> tuple[Optional[ClickUpAPI], Optional[ClaudeAPI]]:
        """Get both ClickUp and Claude APIs"""
        # Get ClickUp API
        workspace = await ClickUpWorkspaceRepository.get_default_workspace(guild_id)
        clickup_api = None
        if workspace:
            token = await ClickUpWorkspaceRepository.get_decrypted_token(workspace)
            clickup_api = ClickUpAPI(token)
        
        # Get Claude API
        claude_api = None
        config = await ClaudeConfigRepository.get_config(guild_id)
        if config and config.is_enabled:
            api_key = await ClaudeConfigRepository.get_decrypted_api_key(config)
            claude_api = ClaudeAPI(
                api_key=api_key,
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
        
        return clickup_api, claude_api
    
    @app_commands.command(name="ai", description="Use AI to do anything with ClickUp")
    @app_commands.describe(
        request="What would you like me to do? (e.g., 'Show all high priority tasks', 'Create a bug report', 'Move John's tasks to next week')"
    )
    async def ai_command(self, interaction: discord.Interaction, request: str):
        """Universal AI command for any ClickUp operation"""
        
        # Get APIs
        clickup_api, claude_api = await self.get_apis(interaction.guild_id)
        
        if not clickup_api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/workspace-add` to configure workspaces."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not claude_api:
            embed = EmbedFactory.create_error_embed(
                "AI Not Configured",
                "Claude AI hasn't been set up yet. Use `/claude-setup` to enable AI features."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Defer response as this might take a while
        await interaction.response.defer()
        
        async with clickup_api:
            try:
                # First, analyze the request to understand intent
                analysis_prompt = f"""Analyze this ClickUp request and determine what actions to take:

Request: "{request}"

Identify:
1. Intent (create_task, update_task, delete_task, list_tasks, move_tasks, assign_tasks, query_status, create_report, etc.)
2. Entities (task names, people, dates, priorities, statuses, lists, etc.)
3. Filters or conditions
4. Required ClickUp API calls

Respond in JSON format:
{{
    "intent": "primary_action",
    "entities": {{
        "tasks": [],
        "people": [],
        "dates": [],
        "priorities": [],
        "statuses": [],
        "lists": [],
        "other": {{}}
    }},
    "filters": {{
        "assignee": null,
        "status": null,
        "priority": null,
        "due_date": null,
        "contains": null
    }},
    "actions": [
        {{
            "type": "api_call",
            "method": "method_name",
            "params": {{}}
        }}
    ],
    "response_format": "summary|detailed|list|report"
}}"""

                # Get AI analysis
                analysis_response = await claude_api.create_message(analysis_prompt, max_tokens=1000)
                
                # Parse the analysis
                try:
                    json_start = analysis_response.find('{')
                    json_end = analysis_response.rfind('}') + 1
                    analysis = json.loads(analysis_response[json_start:json_end])
                except:
                    # Fallback to basic parsing
                    analysis = {
                        "intent": "unknown",
                        "entities": {},
                        "filters": {},
                        "actions": [],
                        "response_format": "summary"
                    }
                
                # Execute based on intent
                result = await self._execute_intent(
                    interaction, 
                    clickup_api, 
                    claude_api,
                    request,
                    analysis
                )
                
            except Exception as e:
                logger.error(f"Error in AI command: {e}")
                embed = EmbedFactory.create_error_embed(
                    "AI Processing Failed",
                    f"I couldn't process your request: {str(e)}"
                )
                await interaction.followup.send(embed=embed)
    
    async def _execute_intent(
        self, 
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI,
        request: str,
        analysis: Dict[str, Any]
    ) -> None:
        """Execute the analyzed intent"""
        
        intent = analysis.get('intent', 'unknown')
        
        # Show processing message
        embed = EmbedFactory.create_info_embed(
            "🤖 AI Processing",
            f"Understanding your request: *{request}*\n\n"
            f"**Intent detected:** {intent.replace('_', ' ').title()}"
        )
        await interaction.followup.send(embed=embed)
        
        # Route to appropriate handler
        if intent == "create_task":
            await self._handle_create_task(interaction, clickup_api, claude_api, request, analysis)
        elif intent == "list_tasks" or intent == "query_status":
            await self._handle_list_tasks(interaction, clickup_api, claude_api, request, analysis)
        elif intent == "update_task" or intent == "move_tasks":
            await self._handle_update_tasks(interaction, clickup_api, claude_api, request, analysis)
        elif intent == "assign_tasks":
            await self._handle_assign_tasks(interaction, clickup_api, claude_api, request, analysis)
        elif intent == "delete_task":
            await self._handle_delete_tasks(interaction, clickup_api, claude_api, request, analysis)
        elif intent == "create_report":
            await self._handle_create_report(interaction, clickup_api, claude_api, request, analysis)
        else:
            # Try to handle it generically
            await self._handle_generic_request(interaction, clickup_api, claude_api, request, analysis)
    
    async def _handle_create_task(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI,
        request: str,
        analysis: Dict[str, Any]
    ):
        """Handle task creation requests"""
        # Get default workspace to find lists
        workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
        
        # Get all lists to find the best match
        all_lists = []
        spaces = await clickup_api.get_spaces(workspace.workspace_id)
        
        for space in spaces[:3]:  # Limit to avoid too many API calls
            lists = await clickup_api.get_lists(space['id'])
            all_lists.extend(lists)
        
        # Ask AI to parse the task details and pick the best list
        parse_prompt = f"""Given this task creation request: "{request}"
        
And these available lists:
{json.dumps([{"id": l['id'], "name": l['name']} for l in all_lists], indent=2)}

Extract:
1. Task name
2. Task description
3. Priority (urgent/high/normal/low)
4. Due date (if mentioned)
5. Assignee (if mentioned)
6. Best matching list ID based on the request context

Respond in JSON:
{{
    "name": "task name",
    "description": "description",
    "priority": "priority level",
    "due_date": "date string or null",
    "assignee": "name or null",
    "list_id": "best matching list id",
    "list_name": "list name"
}}"""

        task_details = await claude_api.create_message(parse_prompt, max_tokens=500)
        
        try:
            json_start = task_details.find('{')
            json_end = task_details.rfind('}') + 1
            task_data = json.loads(task_details[json_start:json_end])
        except:
            # Fallback
            task_data = {
                "name": request[:100],
                "description": "",
                "priority": "normal",
                "list_id": all_lists[0]['id'] if all_lists else None,
                "list_name": all_lists[0]['name'] if all_lists else "Unknown"
            }
        
        if not task_data.get('list_id'):
            embed = EmbedFactory.create_error_embed(
                "No Lists Found",
                "I couldn't find any lists to create the task in. Please create a list in ClickUp first."
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Create the task
        create_params = {
            "name": task_data['name'],
            "description": task_data.get('description', ''),
        }
        
        if task_data.get('priority'):
            create_params['priority'] = {"priority": task_data['priority']}
        
        if task_data.get('due_date'):
            due_date = parse_due_date(task_data['due_date'])
            if due_date:
                create_params['due_date'] = int(due_date.timestamp() * 1000)
        
        result = await clickup_api.create_task(task_data['list_id'], **create_params)
        
        # Success message
        embed = EmbedFactory.create_success_embed(
            "✅ Task Created",
            f"Created: **{task_data['name']}**"
        )
        embed.add_field(name="List", value=task_data['list_name'], inline=True)
        if task_data.get('priority'):
            embed.add_field(name="Priority", value=task_data['priority'].title(), inline=True)
        if task_data.get('due_date'):
            embed.add_field(name="Due Date", value=task_data['due_date'], inline=True)
        if result.get('url'):
            embed.add_field(name="Link", value=f"[View in ClickUp]({result['url']})", inline=False)
        
        await interaction.followup.send(embed=embed)
    
    async def _handle_list_tasks(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI,
        request: str,
        analysis: Dict[str, Any]
    ):
        """Handle task listing/query requests"""
        # Get all tasks from workspace
        workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
        
        all_tasks = []
        spaces = await clickup_api.get_spaces(workspace.workspace_id)
        
        # Collect tasks from all lists
        for space in spaces[:2]:  # Limit to avoid too many API calls
            lists = await clickup_api.get_lists(space['id'])
            for list_obj in lists[:5]:  # Limit lists too
                tasks = await clickup_api.get_tasks(list_obj['id'])
                for task in tasks:
                    task['list_name'] = list_obj['name']
                all_tasks.extend(tasks)
        
        if not all_tasks:
            embed = EmbedFactory.create_info_embed(
                "No Tasks Found",
                "You don't have any tasks in your ClickUp workspace yet."
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Ask AI to filter and format based on request
        filter_prompt = f"""Given this request: "{request}"

And these tasks:
{json.dumps([{
    "id": t['id'],
    "name": t['name'],
    "status": t.get('status', {}).get('status'),
    "priority": t.get('priority', {}).get('priority'),
    "due_date": t.get('due_date'),
    "assignees": [a.get('username') for a in t.get('assignees', [])],
    "list": t.get('list_name')
} for t in all_tasks[:50]], indent=2)}

Filter the tasks based on the request and provide:
1. A summary of what was found
2. The filtered task IDs that match the request
3. How to display them (detailed list, summary, grouped by status, etc.)

Respond in JSON:
{{
    "summary": "Found X tasks matching your criteria",
    "matching_task_ids": ["id1", "id2", ...],
    "display_format": "list|grouped|summary",
    "grouping_key": "status|priority|assignee|list|none"
}}"""

        filter_response = await claude_api.create_message(filter_prompt, max_tokens=800)
        
        try:
            json_start = filter_response.find('{')
            json_end = filter_response.rfind('}') + 1
            filter_data = json.loads(filter_response[json_start:json_end])
        except:
            # Show all tasks as fallback
            filter_data = {
                "summary": f"Showing all {len(all_tasks)} tasks",
                "matching_task_ids": [t['id'] for t in all_tasks],
                "display_format": "list",
                "grouping_key": "none"
            }
        
        # Filter tasks
        matching_tasks = [t for t in all_tasks if t['id'] in filter_data.get('matching_task_ids', [])]
        
        if not matching_tasks:
            matching_tasks = all_tasks[:20]  # Show first 20 as fallback
        
        # Create response embed
        embed = EmbedFactory.create_info_embed(
            "📋 Task Query Results",
            filter_data.get('summary', f"Found {len(matching_tasks)} tasks")
        )
        
        # Group tasks if needed
        if filter_data.get('grouping_key') != 'none':
            groups = {}
            for task in matching_tasks:
                key = task.get(filter_data['grouping_key'], 'Other')
                if filter_data['grouping_key'] == 'status':
                    key = task.get('status', {}).get('status', 'No Status')
                elif filter_data['grouping_key'] == 'priority':
                    key = task.get('priority', {}).get('priority', 'No Priority')
                elif filter_data['grouping_key'] == 'assignee':
                    assignees = task.get('assignees', [])
                    key = assignees[0]['username'] if assignees else 'Unassigned'
                elif filter_data['grouping_key'] == 'list':
                    key = task.get('list_name', 'Unknown List')
                
                if key not in groups:
                    groups[key] = []
                groups[key].append(task)
            
            # Add grouped fields
            for group_name, group_tasks in list(groups.items())[:5]:
                task_lines = []
                for task in group_tasks[:5]:
                    priority_emoji = {
                        'urgent': '🔴',
                        'high': '🟠',
                        'normal': '🟡',
                        'low': '🔵'
                    }.get(task.get('priority', {}).get('priority', ''), '⚪')
                    
                    task_lines.append(f"{priority_emoji} {task['name']}")
                
                if group_tasks:
                    value = "\n".join(task_lines)
                    if len(group_tasks) > 5:
                        value += f"\n*...and {len(group_tasks) - 5} more*"
                    
                    embed.add_field(
                        name=f"{group_name} ({len(group_tasks)})",
                        value=value,
                        inline=False
                    )
        else:
            # Simple list
            task_lines = []
            for task in matching_tasks[:10]:
                priority_emoji = {
                    'urgent': '🔴',
                    'high': '🟠',
                    'normal': '🟡',
                    'low': '🔵'
                }.get(task.get('priority', {}).get('priority', ''), '⚪')
                
                status = task.get('status', {}).get('status', 'no status')
                task_lines.append(f"{priority_emoji} **{task['name']}** - {status}")
            
            if task_lines:
                embed.add_field(
                    name="Tasks",
                    value="\n".join(task_lines),
                    inline=False
                )
        
        embed.set_footer(text=f"Showing {len(matching_tasks)} of {len(all_tasks)} total tasks")
        await interaction.followup.send(embed=embed)
    
    async def _handle_update_tasks(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI,
        request: str,
        analysis: Dict[str, Any]
    ):
        """Handle task update requests"""
        # Get all tasks
        workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
        all_tasks = []
        spaces = await clickup_api.get_spaces(workspace.workspace_id)
        
        for space in spaces[:2]:
            lists = await clickup_api.get_lists(space['id'])
            for list_obj in lists[:5]:
                tasks = await clickup_api.get_tasks(list_obj['id'])
                all_tasks.extend(tasks)
        
        # Ask AI to identify which tasks to update and how
        update_prompt = f"""Given this update request: "{request}"

And these tasks:
{json.dumps([{
    "id": t['id'],
    "name": t['name'],
    "status": t.get('status', {}).get('status'),
    "priority": t.get('priority', {}).get('priority'),
    "assignees": [a.get('username') for a in t.get('assignees', [])]
} for t in all_tasks[:30]], indent=2)}

Determine:
1. Which tasks to update (by ID)
2. What updates to make

Respond in JSON:
{{
    "tasks_to_update": ["id1", "id2"],
    "updates": {{
        "status": "new status or null",
        "priority": "new priority or null",
        "due_date": "new date or null",
        "name": "new name or null",
        "add_tag": "tag to add or null",
        "move_to_list": "list name or null"
    }},
    "summary": "What will be done"
}}"""

        update_response = await claude_api.create_message(update_prompt, max_tokens=600)
        
        try:
            json_start = update_response.find('{')
            json_end = update_response.rfind('}') + 1
            update_data = json.loads(update_response[json_start:json_end])
        except:
            embed = EmbedFactory.create_error_embed(
                "Update Failed",
                "I couldn't understand which tasks to update. Please be more specific."
            )
            await interaction.followup.send(embed=embed)
            return
        
        tasks_to_update = [t for t in all_tasks if t['id'] in update_data.get('tasks_to_update', [])]
        
        if not tasks_to_update:
            embed = EmbedFactory.create_error_embed(
                "No Tasks Found",
                "I couldn't find any tasks matching your update criteria."
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Perform updates
        updated_count = 0
        updates = update_data.get('updates', {})
        
        for task in tasks_to_update:
            try:
                update_params = {}
                
                if updates.get('status'):
                    update_params['status'] = updates['status']
                if updates.get('priority'):
                    update_params['priority'] = {"priority": updates['priority']}
                if updates.get('name'):
                    update_params['name'] = updates['name']
                if updates.get('due_date'):
                    due_date = parse_due_date(updates['due_date'])
                    if due_date:
                        update_params['due_date'] = int(due_date.timestamp() * 1000)
                
                if update_params:
                    await clickup_api.update_task(task['id'], **update_params)
                    updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update task {task['id']}: {e}")
        
        # Success message
        embed = EmbedFactory.create_success_embed(
            "✅ Tasks Updated",
            update_data.get('summary', f"Updated {updated_count} task(s)")
        )
        
        # Show what was updated
        task_names = [t['name'] for t in tasks_to_update[:5]]
        if task_names:
            embed.add_field(
                name="Updated Tasks",
                value="\n".join([f"• {name}" for name in task_names]),
                inline=False
            )
            if len(tasks_to_update) > 5:
                embed.add_field(
                    name="",
                    value=f"*...and {len(tasks_to_update) - 5} more*",
                    inline=False
                )
        
        await interaction.followup.send(embed=embed)
    
    async def _handle_assign_tasks(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI,
        request: str,
        analysis: Dict[str, Any]
    ):
        """Handle task assignment requests"""
        # This would need ClickUp team member mapping
        embed = EmbedFactory.create_info_embed(
            "Task Assignment",
            "Task assignment feature requires team member setup.\n\n"
            "For now, please use `/task-update` with the assignee dropdown."
        )
        await interaction.followup.send(embed=embed)
    
    async def _handle_delete_tasks(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI,
        request: str,
        analysis: Dict[str, Any]
    ):
        """Handle task deletion requests"""
        embed = EmbedFactory.create_warning_embed(
            "⚠️ Deletion Safety",
            "For safety, please use `/task-delete` command with confirmation.\n\n"
            "This prevents accidental deletions through AI misunderstanding."
        )
        await interaction.followup.send(embed=embed)
    
    async def _handle_create_report(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI,
        request: str,
        analysis: Dict[str, Any]
    ):
        """Handle report generation requests"""
        # Get all tasks for reporting
        workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
        all_tasks = []
        spaces = await clickup_api.get_spaces(workspace.workspace_id)
        
        for space in spaces[:3]:
            lists = await clickup_api.get_lists(space['id'])
            for list_obj in lists[:5]:
                tasks = await clickup_api.get_tasks(list_obj['id'])
                for task in tasks:
                    task['list_name'] = list_obj['name']
                all_tasks.extend(tasks)
        
        # Ask AI to generate the report
        report_prompt = f"""Generate a report based on this request: "{request}"

Using these tasks:
{json.dumps([{
    "name": t['name'],
    "status": t.get('status', {}).get('status'),
    "priority": t.get('priority', {}).get('priority'),
    "due_date": t.get('due_date'),
    "assignees": [a.get('username') for a in t.get('assignees', [])],
    "list": t.get('list_name'),
    "created": t.get('date_created'),
    "updated": t.get('date_updated')
} for t in all_tasks], indent=2)}

Create a comprehensive report with:
1. Executive summary
2. Key metrics
3. Task breakdown by status/priority/assignee
4. Insights and recommendations

Format nicely for Discord."""

        report = await claude_api.create_message(report_prompt, max_tokens=2000)
        
        # Create report embed
        embed = EmbedFactory.create_info_embed(
            "📊 ClickUp Report",
            f"Generated report for: *{request}*"
        )
        
        # Split report into sections
        sections = report.split('\n\n')
        for section in sections[:5]:  # Limit to 5 sections
            if ':' in section:
                title, content = section.split(':', 1)
                if len(content) > 1024:
                    content = content[:1021] + '...'
                embed.add_field(
                    name=title.strip(),
                    value=content.strip(),
                    inline=False
                )
        
        embed.set_footer(text=f"Report based on {len(all_tasks)} tasks")
        await interaction.followup.send(embed=embed)
    
    async def _handle_generic_request(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI,
        request: str,
        analysis: Dict[str, Any]
    ):
        """Handle any other request type"""
        # Get workspace context
        workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
        
        # Provide AI with context and let it figure out what to do
        context_prompt = f"""The user wants to: "{request}"

You have access to ClickUp with these capabilities:
- Create, update, list, delete tasks
- Manage priorities, statuses, due dates
- Create reports and analytics
- Query and filter tasks

Based on the request, provide a helpful response. If it requires specific actions, explain what would need to be done.

Be concise and helpful."""

        response = await claude_api.create_message(context_prompt, max_tokens=800)
        
        embed = EmbedFactory.create_info_embed(
            "🤖 AI Response",
            response[:2000]  # Limit response length
        )
        
        embed.add_field(
            name="💡 Tip",
            value="For specific actions, try commands like:\n"
                  "• 'Create a task...'\n"
                  "• 'Show me all...'\n"
                  "• 'Update ... tasks to...'\n"
                  "• 'Generate a report on...'",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AIComplete(bot))