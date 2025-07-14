import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from services.clickup_api import ClickUpAPI
from services.claude_api import ClaudeAPI
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from repositories.claude_config import ClaudeConfigRepository
from utils.embed_factory import EmbedFactory
from utils.enhanced_selections import ListSelectView
from loguru import logger

class AICommandsEnhanced(commands.Cog):
    """Enhanced AI-powered ClickUp commands with multi-workspace support"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def get_clickup_api(self, guild_id: int) -> Optional[ClickUpAPI]:
        """Get ClickUp API instance using new workspace system"""
        workspace = await ClickUpWorkspaceRepository.get_default_workspace(guild_id)
        if workspace:
            token = await ClickUpWorkspaceRepository.get_decrypted_token(workspace)
            return ClickUpAPI(token)
        return None
    
    async def get_claude_api(self, guild_id: int) -> Optional[ClaudeAPI]:
        """Get Claude API instance"""
        config = await ClaudeConfigRepository.get_config(guild_id)
        if config and config.is_enabled:
            api_key = await ClaudeConfigRepository.get_decrypted_api_key(config)
            return ClaudeAPI(
                api_key=api_key,
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=config.temperature
            )
        return None
    
    @app_commands.command(name="ai-create-task", description="Create a task using natural language")
    @app_commands.describe(
        command="Natural language description of the task (e.g., 'Create urgent bug fix task due tomorrow')"
    )
    async def ai_create_task(
        self,
        interaction: discord.Interaction,
        command: str
    ):
        """Create a task using AI to parse natural language"""
        # Check ClickUp configuration
        clickup_api = await self.get_clickup_api(interaction.guild_id)
        if not clickup_api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/workspace-add` to configure workspaces."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check Claude configuration
        claude_api = await self.get_claude_api(interaction.guild_id)
        if not claude_api:
            embed = EmbedFactory.create_error_embed(
                "AI Not Configured",
                "Claude AI hasn't been set up yet. Use `/claude-setup` to enable AI features."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with clickup_api:
            # Select list first
            list_view = ListSelectView(clickup_api)
            await list_view.start(interaction)
            
            await list_view.wait()
            
            if not list_view.selected_list_id:
                return
            
            # Process with AI
            embed = EmbedFactory.create_info_embed(
                "Processing Task",
                f"🤖 AI is analyzing your request:\n```{command}```"
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            try:
                # Parse the command using Claude
                prompt = f"""Parse this task creation request and extract the following information:
                - Task name (required)
                - Description (if mentioned)
                - Priority (urgent/high/normal/low)
                - Due date (if mentioned, convert to a relative date like "tomorrow", "in 2 days", etc.)
                - Assignee (if mentioned)
                
                Request: "{command}"
                
                Respond in this JSON format:
                {{
                    "name": "task name",
                    "description": "description or null",
                    "priority": "priority level or null",
                    "due_date": "relative date or null",
                    "assignee": "assignee name or null"
                }}"""
                
                response = await claude_api.create_message(prompt, max_tokens=500)
                
                # Parse the response
                import json
                try:
                    # Extract JSON from Claude's response
                    json_start = response.find('{')
                    json_end = response.rfind('}') + 1
                    if json_start != -1 and json_end > json_start:
                        task_data = json.loads(response[json_start:json_end])
                    else:
                        raise ValueError("No JSON found in response")
                except:
                    # Fallback parsing
                    task_data = {
                        "name": command.split('\n')[0][:100],
                        "description": command if len(command) > 100 else None,
                        "priority": "normal",
                        "due_date": None,
                        "assignee": None
                    }
                
                # Create the task
                create_data = {
                    "name": task_data.get("name", command[:100]),
                    "description": task_data.get("description", ""),
                }
                
                # Add priority if specified
                if task_data.get("priority"):
                    create_data["priority"] = {"priority": task_data["priority"]}
                
                # Parse due date if specified
                if task_data.get("due_date"):
                    from utils.helpers import parse_due_date
                    due_date = parse_due_date(task_data["due_date"])
                    if due_date:
                        create_data["due_date"] = int(due_date.timestamp() * 1000)
                
                # Create the task
                result = await clickup_api.create_task(list_view.selected_list_id, **create_data)
                
                # Success embed
                embed = EmbedFactory.create_success_embed(
                    "Task Created with AI",
                    f"✅ Created: **{task_data.get('name', result['name'])}**"
                )
                
                embed.add_field(name="List", value=list_view.selected_list_name, inline=True)
                
                if task_data.get("priority"):
                    embed.add_field(name="Priority", value=task_data["priority"].title(), inline=True)
                
                if task_data.get("due_date"):
                    embed.add_field(name="Due Date", value=task_data["due_date"], inline=True)
                
                if result.get('url'):
                    embed.add_field(name="View Task", value=f"[Click here]({result['url']})", inline=False)
                
                embed.set_footer(text="🤖 Parsed by Claude AI")
                
                await interaction.edit_original_response(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in AI task creation: {e}")
                embed = EmbedFactory.create_error_embed(
                    "AI Processing Failed",
                    f"Failed to create task: {str(e)}"
                )
                await interaction.edit_original_response(embed=embed)
    
    @app_commands.command(name="ai-analyze-tasks", description="AI-powered task analysis")
    @app_commands.describe(
        analysis_type="Type of analysis to perform"
    )
    async def ai_analyze_tasks(
        self,
        interaction: discord.Interaction,
        analysis_type: app_commands.Choice[str]
    ):
        """Analyze tasks using AI"""
        # Check configuration
        clickup_api = await self.get_clickup_api(interaction.guild_id)
        if not clickup_api:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "ClickUp hasn't been set up yet. Use `/workspace-add` to configure workspaces."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        claude_api = await self.get_claude_api(interaction.guild_id)
        if not claude_api:
            embed = EmbedFactory.create_error_embed(
                "AI Not Configured",
                "Claude AI hasn't been set up yet. Use `/claude-setup` to enable AI features."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with clickup_api:
            # Select list
            list_view = ListSelectView(clickup_api)
            await list_view.start(interaction)
            
            await list_view.wait()
            
            if not list_view.selected_list_id:
                return
            
            # Fetch tasks
            embed = EmbedFactory.create_info_embed(
                "Analyzing Tasks",
                f"🤖 AI is analyzing tasks from **{list_view.selected_list_name}**..."
            )
            await interaction.edit_original_response(embed=embed, view=None)
            
            try:
                # Get tasks
                tasks = await clickup_api.get_tasks(list_view.selected_list_id)
                
                if not tasks:
                    embed = EmbedFactory.create_info_embed(
                        "No Tasks",
                        "No tasks found to analyze."
                    )
                    await interaction.edit_original_response(embed=embed)
                    return
                
                # Prepare task data for AI
                task_summary = []
                for task in tasks[:50]:  # Limit to 50 tasks
                    task_info = {
                        "name": task.get("name"),
                        "status": task.get("status", {}).get("status"),
                        "priority": task.get("priority", {}).get("priority"),
                        "due_date": task.get("due_date"),
                        "assignees": [a.get("username") for a in task.get("assignees", [])],
                        "description": task.get("description", "")[:200]  # Limit description length
                    }
                    task_summary.append(task_info)
                
                # Create analysis prompt based on type
                prompts = {
                    "priorities": "Analyze these tasks and suggest priority adjustments. Consider deadlines, task names, and current priorities.",
                    "dependencies": "Identify potential dependencies between these tasks and suggest an optimal order of completion.",
                    "workload": "Analyze the workload distribution among assignees and suggest rebalancing if needed.",
                    "overdue": "Identify overdue or at-risk tasks and suggest recovery actions.",
                    "optimization": "Provide general optimization suggestions for this task list."
                }
                
                prompt = f"{prompts.get(analysis_type.value, prompts['optimization'])}\n\nTasks:\n{json.dumps(task_summary, indent=2)}"
                
                # Get AI analysis
                analysis = await claude_api.create_message(prompt, max_tokens=1500)
                
                # Create result embed
                embed = EmbedFactory.create_info_embed(
                    f"🤖 AI Analysis: {analysis_type.name}",
                    f"Analysis of {len(tasks)} tasks from **{list_view.selected_list_name}**"
                )
                
                # Split analysis into chunks for embed fields
                chunks = [analysis[i:i+1024] for i in range(0, len(analysis), 1024)]
                for i, chunk in enumerate(chunks[:3]):  # Max 3 fields
                    field_name = "Analysis" if i == 0 else "Continued"
                    embed.add_field(name=field_name, value=chunk, inline=False)
                
                embed.set_footer(text="🤖 Analysis by Claude AI")
                
                await interaction.edit_original_response(embed=embed)
                
            except Exception as e:
                logger.error(f"Error in AI analysis: {e}")
                embed = EmbedFactory.create_error_embed(
                    "Analysis Failed",
                    f"Failed to analyze tasks: {str(e)}"
                )
                await interaction.edit_original_response(embed=embed)
    
    @ai_analyze_tasks.autocomplete('analysis_type')
    async def analysis_type_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        choices = [
            app_commands.Choice(name="Priority Suggestions", value="priorities"),
            app_commands.Choice(name="Task Dependencies", value="dependencies"),
            app_commands.Choice(name="Workload Distribution", value="workload"),
            app_commands.Choice(name="Overdue & At Risk", value="overdue"),
            app_commands.Choice(name="General Optimization", value="optimization")
        ]
        
        if current:
            return [c for c in choices if current.lower() in c.name.lower()]
        return choices

async def setup(bot):
    await bot.add_cog(AICommandsEnhanced(bot))