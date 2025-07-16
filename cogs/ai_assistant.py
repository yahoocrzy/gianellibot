import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import json
from services.clickup_api import ClickUpAPI
from services.claude_api import ClaudeAPI
from repositories.claude_config import ClaudeConfigRepository
from utils.embed_factory import EmbedFactory
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from loguru import logger

class AIAssistant(commands.Cog):
    """AI-powered ClickUp assistant with dropdown-only interface"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def get_clickup_api(self, guild_id: int) -> Optional[ClickUpAPI]:
        """Get ClickUp API instance using workspace repository"""
        # Get default workspace
        default_workspace = await ClickUpWorkspaceRepository.get_default_workspace(guild_id)
        if not default_workspace:
            return None
            
        # Get decrypted token
        token = await ClickUpWorkspaceRepository.get_decrypted_token(default_workspace)
        if not token:
            return None
            
        return ClickUpAPI(token)
    
    async def get_claude_api(self, guild_id: int) -> Optional[ClaudeAPI]:
        """Get Claude API instance"""
        try:
            config = await ClaudeConfigRepository.get_config(guild_id)
            if config and config.is_enabled:
                api_key = await ClaudeConfigRepository.get_decrypted_api_key(config)
                return ClaudeAPI(api_key)
            return None
        except Exception as e:
            logger.error(f"Error getting Claude API: {e}")
            return None
    
    @app_commands.command(name="ai-assistant", description="AI assistant for ClickUp task management")
    async def ai_assistant(self, interaction: discord.Interaction):
        """AI assistant with dropdown selections"""
        # Check if both APIs are available
        clickup_api = await self.get_clickup_api(interaction.guild_id)
        claude_api = await self.get_claude_api(interaction.guild_id)
        
        if not clickup_api:
            embed = EmbedFactory.create_error_embed(
                "ClickUp Not Configured",
                "ClickUp hasn't been set up yet. Use `/clickup-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not claude_api:
            embed = EmbedFactory.create_error_embed(
                "Claude AI Not Configured",
                "Claude AI hasn't been set up yet. Use `/claude-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Show AI action selection
        embed = EmbedFactory.create_info_embed(
            "🤖 AI Assistant",
            "What would you like me to help you with?"
        )
        
        class AIActionView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
                self.selected_action = None
                
                options = [
                    discord.SelectOption(
                        label="Create Smart Task",
                        value="create_smart_task",
                        description="Create a task with AI-generated details",
                        emoji="➕"
                    ),
                    discord.SelectOption(
                        label="Task Status Report",
                        value="status_report",
                        description="Get AI analysis of task status",
                        emoji="📊"
                    ),
                    discord.SelectOption(
                        label="Find Tasks",
                        value="find_tasks",
                        description="Search tasks with natural language",
                        emoji="🔍"
                    ),
                    discord.SelectOption(
                        label="Suggest Improvements",
                        value="suggest_improvements",
                        description="Get AI suggestions for workflow",
                        emoji="💡"
                    )
                ]
                
                select = discord.ui.Select(
                    placeholder="Choose an AI action...",
                    options=options
                )
                select.callback = self.action_callback
                self.add_item(select)
            
            async def action_callback(self, select_interaction: discord.Interaction):
                self.selected_action = select_interaction.data['values'][0]
                self.stop()
                await select_interaction.response.defer_update()
        
        action_view = AIActionView()
        await interaction.response.send_message(embed=embed, view=action_view, ephemeral=True)
        
        await action_view.wait()
        
        if not action_view.selected_action:
            return
        
        # Handle the selected action
        async with clickup_api:
            if action_view.selected_action == "create_smart_task":
                await self.handle_create_smart_task(interaction, clickup_api, claude_api)
            elif action_view.selected_action == "status_report":
                await self.handle_status_report(interaction, clickup_api, claude_api)
            elif action_view.selected_action == "find_tasks":
                await self.handle_find_tasks(interaction, clickup_api, claude_api)
            elif action_view.selected_action == "suggest_improvements":
                await self.handle_suggest_improvements(interaction, clickup_api, claude_api)
    
    async def handle_create_smart_task(self, interaction: discord.Interaction, clickup_api: ClickUpAPI, claude_api: ClaudeAPI):
        """Handle smart task creation"""
        # Get task category first
        embed = EmbedFactory.create_info_embed(
            "🤖 Smart Task Creation",
            "What type of task would you like to create?"
        )
        
        class TaskCategoryView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                self.selected_category = None
                
                categories = [
                    {"name": "Bug Fix", "desc": "Fix a software bug or issue"},
                    {"name": "Feature Development", "desc": "Build new functionality"},
                    {"name": "Code Review", "desc": "Review and approve code"},
                    {"name": "Documentation", "desc": "Write or update documentation"},
                    {"name": "Testing", "desc": "Quality assurance and testing"},
                    {"name": "Research", "desc": "Investigate and research"},
                    {"name": "Meeting", "desc": "Plan or conduct meetings"},
                    {"name": "Deployment", "desc": "Deploy or release code"}
                ]
                
                options = []
                for cat in categories:
                    options.append(
                        discord.SelectOption(
                            label=cat["name"],
                            value=cat["name"],
                            description=cat["desc"]
                        )
                    )
                
                select = discord.ui.Select(
                    placeholder="Select task category...",
                    options=options
                )
                select.callback = self.category_callback
                self.add_item(select)
            
            async def category_callback(self, select_interaction: discord.Interaction):
                self.selected_category = select_interaction.data['values'][0]
                self.stop()
                await select_interaction.response.defer_update()
        
        category_view = TaskCategoryView()
        await interaction.edit_original_response(embed=embed, view=category_view)
        
        await category_view.wait()
        
        if not category_view.selected_category:
            return
        
        # Use AI to generate task details
        embed = EmbedFactory.create_info_embed(
            "🤖 Generating Task Details",
            "⏳ AI is creating optimized task details..."
        )
        await interaction.edit_original_response(embed=embed, view=None)
        
        try:
            # Generate smart task details using Claude
            prompt = f"""Generate a professional task for category: {category_view.selected_category}

Create a JSON response with:
- name: Specific, actionable task name (max 50 chars)
- description: Detailed description with acceptance criteria
- priority: one of: urgent, high, normal, low
- estimated_hours: realistic estimate (1-40)

Category: {category_view.selected_category}

Respond with only valid JSON."""

            response = await claude_api.create_message(prompt)
            
            try:
                task_data = json.loads(response)
            except:
                # Fallback if AI doesn't return valid JSON
                task_data = {
                    "name": f"{category_view.selected_category} Task",
                    "description": f"Auto-generated {category_view.selected_category.lower()} task",
                    "priority": "normal",
                    "estimated_hours": 4
                }
            
            # Now select list and create the task
            # Get the default workspace
            default_workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
            if not default_workspace:
                embed = EmbedFactory.create_error_embed("No Default Workspace", "No default workspace set. Run `/clickup-setup` first.")
                await interaction.edit_original_response(embed=embed)
                return
            
            workspace_id = default_workspace.workspace_id
            spaces = await clickup_api.get_spaces(workspace_id)
            
            all_lists = []
            for space in spaces[:2]:
                try:
                    lists = await clickup_api.get_lists(space['id'])
                    for lst in lists[:5]:
                        lst['space_name'] = space['name']
                        all_lists.append(lst)
                except Exception as e:
                    continue
            
            if not all_lists:
                embed = EmbedFactory.create_error_embed("No Lists", "No lists found.")
                await interaction.edit_original_response(embed=embed)
                return
            
            # Show list selection
            embed = EmbedFactory.create_info_embed(
                "Select Destination List",
                f"Creating: **{task_data['name']}**\\n\\nWhere should I create this task?"
            )
            
            class ListSelectView(discord.ui.View):
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
            
            list_view = ListSelectView()
            await interaction.edit_original_response(embed=embed, view=list_view)
            
            await list_view.wait()
            
            if not list_view.selected_list:
                return
            
            # Create the task
            embed = EmbedFactory.create_info_embed(
                "Creating Task",
                "⏳ Creating AI-generated task..."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            result = await clickup_api.create_task(
                list_view.selected_list['id'],
                name=task_data['name'],
                description=task_data['description'],
                priority={"priority": task_data['priority']}
            )
            
            # Success message
            embed = EmbedFactory.create_success_embed(
                "🤖 Smart Task Created!",
                f"✅ Created: **{task_data['name']}**"
            )
            
            embed.add_field(name="List", value=list_view.selected_list['name'], inline=True)
            embed.add_field(name="Priority", value=task_data['priority'].title(), inline=True)
            embed.add_field(name="AI Generated", value="Yes", inline=True)
            
            if result.get('url'):
                embed.add_field(name="View Task", value=f"[Click here]({result['url']})", inline=False)
            
            await interaction.edit_original_response(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in smart task creation: {e}")
            embed = EmbedFactory.create_error_embed(
                "Creation Failed",
                f"❌ Failed to create task: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed)
    
    async def handle_status_report(self, interaction: discord.Interaction, clickup_api: ClickUpAPI, claude_api: ClaudeAPI):
        """Generate AI status report"""
        embed = EmbedFactory.create_info_embed(
            "🤖 Generating Status Report",
            "⏳ AI is analyzing your tasks..."
        )
        await interaction.edit_original_response(embed=embed, view=None)
        
        try:
            # Get tasks from the default workspace only
            default_workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
            if not default_workspace:
                embed = EmbedFactory.create_error_embed("No Default Workspace", "No default workspace set. Run `/clickup-setup` first.")
                await interaction.edit_original_response(embed=embed)
                return
            
            all_tasks = []
            try:
                spaces = await clickup_api.get_spaces(default_workspace.workspace_id)
                for space in spaces[:2]:  # Limit spaces to prevent timeout
                    try:
                        lists = await clickup_api.get_lists(space['id'])
                        for lst in lists[:3]:  # Limit lists per space
                            try:
                                tasks = await clickup_api.get_tasks(lst['id'])
                                all_tasks.extend(tasks[:10])  # Limit tasks per list
                            except Exception as e:
                                logger.warning(f"Failed to get tasks from list {lst['name']}: {e}")
                                continue
                    except Exception as e:
                        logger.warning(f"Failed to get lists from space {space['name']}: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Failed to get spaces from workspace {default_workspace.workspace_id}: {e}")
            
            # Prepare task summary for AI
            task_summary = []
            for task in all_tasks[:20]:
                status = task.get('status', {}).get('status', 'unknown')
                priority = task.get('priority', {}).get('priority', 'none')
                task_summary.append(f"- {task['name']} (Status: {status}, Priority: {priority})")
            
            # Generate AI report
            prompt = f"""Analyze these ClickUp tasks and provide a brief status report:

{chr(10).join(task_summary)}

Provide:
1. Overall progress summary
2. Priority distribution
3. Key insights
4. Recommendations

Keep it concise and actionable. Max 300 words."""
            
            ai_response = await claude_api.create_message(prompt)
            
            embed = EmbedFactory.create_info_embed(
                "🤖 AI Status Report",
                ai_response[:1000] if len(ai_response) > 1000 else ai_response
            )
            
            embed.add_field(
                name="Tasks Analyzed",
                value=str(len(all_tasks)),
                inline=True
            )
            
            embed.add_field(
                name="Workspaces",
                value=str(len(workspaces)),
                inline=True
            )
            
            await interaction.edit_original_response(embed=embed)
            
        except Exception as e:
            logger.error(f"Error generating status report: {e}")
            embed = EmbedFactory.create_error_embed(
                "Report Failed",
                f"❌ Failed to generate report: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed)
    
    async def handle_find_tasks(self, interaction: discord.Interaction, clickup_api: ClickUpAPI, claude_api: ClaudeAPI):
        """Handle AI-powered task search"""
        embed = EmbedFactory.create_info_embed(
            "🔍 AI Task Search",
            "What type of tasks are you looking for?"
        )
        
        class SearchTypeView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                self.selected_search = None
                
                search_types = [
                    "High priority tasks",
                    "Overdue tasks",
                    "Tasks assigned to me",
                    "Bug fix tasks",
                    "Feature development tasks",
                    "Tasks due this week",
                    "Completed tasks",
                    "Tasks without assignees"
                ]
                
                options = []
                for search_type in search_types:
                    options.append(
                        discord.SelectOption(
                            label=search_type,
                            value=search_type
                        )
                    )
                
                select = discord.ui.Select(
                    placeholder="Select search type...",
                    options=options
                )
                select.callback = self.search_callback
                self.add_item(select)
            
            async def search_callback(self, select_interaction: discord.Interaction):
                self.selected_search = select_interaction.data['values'][0]
                self.stop()
                await select_interaction.response.defer_update()
        
        search_view = SearchTypeView()
        await interaction.edit_original_response(embed=embed, view=search_view)
        
        await search_view.wait()
        
        if not search_view.selected_search:
            return
        
        embed = EmbedFactory.create_info_embed(
            "🔍 Searching Tasks",
            f"⏳ Finding: {search_view.selected_search}..."
        )
        await interaction.edit_original_response(embed=embed, view=None)
        
        # Implementation would go here - simplified for now
        embed = EmbedFactory.create_info_embed(
            "🔍 Search Results",
            f"Search for '{search_view.selected_search}' completed.\\n\\nThis feature is being enhanced!"
        )
        await interaction.edit_original_response(embed=embed)
    
    async def handle_suggest_improvements(self, interaction: discord.Interaction, clickup_api: ClickUpAPI, claude_api: ClaudeAPI):
        """Generate AI workflow suggestions"""
        embed = EmbedFactory.create_info_embed(
            "💡 AI Workflow Analysis",
            "⏳ Analyzing your workflow for improvements..."
        )
        await interaction.edit_original_response(embed=embed, view=None)
        
        try:
            # Basic workflow analysis using default workspace
            default_workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
            workspace_info = f"workspace '{default_workspace.workspace_name}'" if default_workspace else "no configured workspace"
            
            prompt = f"""Provide 3-4 brief workflow improvement suggestions for a team using ClickUp with {workspace_info}.

Focus on:
- Task organization
- Priority management
- Team collaboration
- Productivity tips

Keep each suggestion to 1-2 sentences."""
            
            suggestions = await claude_api.create_message(prompt)
            
            embed = EmbedFactory.create_info_embed(
                "💡 AI Workflow Suggestions",
                suggestions[:1000] if len(suggestions) > 1000 else suggestions
            )
            
            await interaction.edit_original_response(embed=embed)
            
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            embed = EmbedFactory.create_error_embed(
                "Analysis Failed",
                f"❌ Failed to generate suggestions: {str(e)}"
            )
            await interaction.edit_original_response(embed=embed)

async def setup(bot):
    await bot.add_cog(AIAssistant(bot))