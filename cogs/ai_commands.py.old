import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import json
from services.claude_api import ClaudeAPI
from services.clickup_api import ClickUpAPI
from services.security import security_service
from repositories.server_config import ServerConfigRepository
from utils.embed_factory import EmbedFactory
from utils.selection_views import WorkspaceSelectView, SpaceSelectView, ListSelectView
from loguru import logger

class AICommands(commands.Cog):
    """AI-powered task management commands using Claude"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def _get_clickup_api(self, guild_id: int) -> Optional[ClickUpAPI]:
        """Get ClickUp API instance for guild"""
        repo = ServerConfigRepository()
        config = await repo.get_config(guild_id)
        
        if not config or not config.get('clickup_token_encrypted'):
            return None
            
        token = security_service.decrypt(config['clickup_token_encrypted'])
        return ClickUpAPI(token)
    
    async def _get_claude_api(self, guild_id: int) -> Optional[ClaudeAPI]:
        """Get Claude API instance for guild"""
        repo = ServerConfigRepository()
        config = await repo.get_config(guild_id)
        
        # For now, use a simple implementation - this should be configured per server
        if not config or not config.get('claude_api_url'):
            return None
        
        api_key = None
        if config.get('claude_api_key_encrypted'):
            api_key = security_service.decrypt(config['claude_api_key_encrypted'])
        
        return ClaudeAPI(config['claude_api_url'], api_key)
    
    @app_commands.command(name="ai-create-task", description="Create a task using natural language with AI")
    @app_commands.describe(
        command="Natural language description of the task to create",
        list_id="List ID to create task in (optional, will prompt if not provided)"
    )
    async def ai_create_task(
        self,
        interaction: discord.Interaction,
        command: str,
        list_id: Optional[str] = None
    ):
        """Create a task using natural language processing"""
        clickup_api = await self._get_clickup_api(interaction.guild.id)
        if not clickup_api:
            await interaction.response.send_message(
                "❌ ClickUp is not configured. Run `/clickup-setup` first.", 
                ephemeral=True
            )
            return
        
        claude_api = await self._get_claude_api(interaction.guild.id)
        if not claude_api:
            # Fallback to basic parsing if Claude is not configured
            await self._create_task_fallback(interaction, command, list_id)
            return
        
        await interaction.response.defer()
        
        try:
            # Parse the command using Claude
            task_data = await claude_api.parse_task_command(command)
            
            if not list_id:
                await interaction.followup.send(
                    "❌ Please provide a list ID.\n\n"
                    "💡 **Tip:** Use `/select-list` to browse and find list IDs using interactive dropdowns!",
                    ephemeral=True
                )
                return
            
            # Create the task using parsed data
            async with clickup_api:
                clickup_task_data = {
                    "name": task_data.get("name", command),
                    "priority": task_data.get("priority", 3)
                }
                
                if task_data.get("description"):
                    clickup_task_data["description"] = task_data["description"]
                
                if task_data.get("due_date"):
                    try:
                        from datetime import datetime
                        due_date = datetime.fromisoformat(task_data["due_date"])
                        clickup_task_data["due_date"] = int(due_date.timestamp() * 1000)
                    except:
                        pass  # Invalid date format, skip
                
                task = await clickup_api.create_task(list_id, **clickup_task_data)
            
            # Create success embed
            embed = EmbedFactory.create_success_embed(
                "🤖 AI Task Created",
                f"Successfully created task using AI parsing!"
            )
            embed.add_field(name="Task Name", value=task['name'], inline=False)
            embed.add_field(name="ID", value=task['id'], inline=True)
            embed.add_field(name="Status", value=task['status']['status'], inline=True)
            
            if task_data.get("description"):
                embed.add_field(name="Description", value=task_data["description"][:1000], inline=False)
            
            if task.get('url'):
                embed.add_field(name="Link", value=f"[Open in ClickUp]({task['url']})", inline=False)
            
            # Show AI parsing details
            parsing_details = f"**Original Command:** {command}\n"
            parsing_details += f"**Parsed Priority:** {task_data.get('priority', 3)}/4\n"
            if task_data.get("tags"):
                parsing_details += f"**Tags:** {', '.join(task_data['tags'])}\n"
            
            embed.add_field(name="AI Parsing Details", value=parsing_details, inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to create AI task: {e}")
            await interaction.followup.send(
                f"❌ Failed to create task using AI: {str(e)}\n\n"
                "💡 **Tip:** Try using `/task-create` for manual task creation.",
                ephemeral=True
            )
    
    async def _create_task_fallback(self, interaction: discord.Interaction, command: str, list_id: Optional[str]):
        """Fallback task creation without AI parsing"""
        if not list_id:
            await interaction.response.send_message(
                "❌ Please provide a list ID.\n\n"
                "💡 **Tip:** Use `/select-list` to browse and find list IDs using interactive dropdowns!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        clickup_api = await self._get_clickup_api(interaction.guild.id)
        async with clickup_api:
            try:
                task = await clickup_api.create_task(list_id, name=command)
                
                embed = EmbedFactory.create_success_embed(
                    "✅ Task Created (Basic Mode)",
                    "Created task without AI parsing (Claude not configured)"
                )
                embed.add_field(name="Task Name", value=task['name'], inline=False)
                embed.add_field(name="ID", value=task['id'], inline=True)
                embed.add_field(name="Status", value=task['status']['status'], inline=True)
                
                if task.get('url'):
                    embed.add_field(name="Link", value=f"[Open in ClickUp]({task['url']})", inline=False)
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                logger.error(f"Failed to create fallback task: {e}")
                await interaction.followup.send(f"❌ Failed to create task: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="ai-analyze-tasks", description="Get AI analysis and suggestions for your tasks")
    @app_commands.describe(
        list_id="List ID to analyze tasks from",
        analysis_type="Type of analysis to perform"
    )
    @app_commands.choices(analysis_type=[
        app_commands.Choice(name="Priority Suggestions", value="priority"),
        app_commands.Choice(name="Task Dependencies", value="dependencies"),
        app_commands.Choice(name="Time Estimates", value="estimates"),
        app_commands.Choice(name="Task Organization", value="organization")
    ])
    async def ai_analyze_tasks(
        self,
        interaction: discord.Interaction,
        list_id: str,
        analysis_type: str = "priority"
    ):
        """Analyze tasks using AI and provide suggestions"""
        clickup_api = await self._get_clickup_api(interaction.guild.id)
        if not clickup_api:
            await interaction.response.send_message(
                "❌ ClickUp is not configured. Run `/clickup-setup` first.", 
                ephemeral=True
            )
            return
        
        claude_api = await self._get_claude_api(interaction.guild.id)
        if not claude_api:
            await interaction.response.send_message(
                "❌ Claude AI is not configured for this server.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Get tasks from the list
            async with clickup_api:
                tasks = await clickup_api.get_tasks(list_id)
            
            if not tasks:
                await interaction.followup.send("No tasks found in this list.", ephemeral=True)
                return
            
            # Prepare task data for AI analysis
            task_summary = []
            for task in tasks[:20]:  # Limit to first 20 tasks
                task_info = {
                    "name": task["name"],
                    "status": task["status"]["status"],
                    "priority": task.get("priority", {}).get("priority", "None"),
                    "description": task.get("description", "")[:200]  # Limit description length
                }
                task_summary.append(task_info)
            
            # Create analysis prompt based on type
            analysis_prompts = {
                "priority": "Analyze these tasks and suggest priority adjustments. Consider urgency, impact, and dependencies.",
                "dependencies": "Identify potential dependencies between these tasks and suggest optimal ordering.",
                "estimates": "Provide time estimates for each task and suggest realistic deadlines.",
                "organization": "Suggest how to better organize and categorize these tasks for improved workflow."
            }
            
            prompt = f"""{analysis_prompts[analysis_type]}
            
            Tasks:
            {json.dumps(task_summary, indent=2)}
            
            Provide actionable insights and specific recommendations. Format your response in a clear, organized manner."""
            
            # Get AI analysis
            analysis = await claude_api.complete(prompt)
            
            if not analysis:
                await interaction.followup.send(
                    "❌ Failed to get AI analysis. Please try again later.",
                    ephemeral=True
                )
                return
            
            # Create analysis embed
            embed = discord.Embed(
                title=f"🤖 AI Task Analysis: {analysis_type.title()}",
                description=analysis[:2000],  # Discord embed description limit
                color=discord.Color.blue()
            )
            embed.add_field(name="Analyzed Tasks", value=f"{len(tasks)} tasks", inline=True)
            embed.add_field(name="List ID", value=list_id, inline=True)
            embed.set_footer(text="AI analysis provided by Claude")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to analyze tasks: {e}")
            await interaction.followup.send(
                f"❌ Failed to analyze tasks: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="ai-task-suggestions", description="Get AI suggestions for improving a specific task")
    @app_commands.describe(task_id="Task ID to analyze and improve")
    async def ai_task_suggestions(self, interaction: discord.Interaction, task_id: str):
        """Get AI suggestions for improving a specific task"""
        clickup_api = await self._get_clickup_api(interaction.guild.id)
        if not clickup_api:
            await interaction.response.send_message(
                "❌ ClickUp is not configured. Run `/clickup-setup` first.", 
                ephemeral=True
            )
            return
        
        claude_api = await self._get_claude_api(interaction.guild.id)
        if not claude_api:
            await interaction.response.send_message(
                "❌ Claude AI is not configured for this server.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Get task details
            async with clickup_api:
                task = await clickup_api.get_task(task_id)
            
            # Prepare task data for analysis
            task_data = {
                "name": task["name"],
                "description": task.get("description", ""),
                "status": task["status"]["status"],
                "priority": task.get("priority", {}).get("priority", "None"),
                "due_date": task.get("due_date"),
                "assignees": [assignee.get("username", "Unknown") for assignee in task.get("assignees", [])]
            }
            
            prompt = f"""Analyze this task and provide specific suggestions for improvement:

            Task Details:
            {json.dumps(task_data, indent=2)}
            
            Please provide suggestions for:
            1. Better task naming and clarity
            2. Improved description and acceptance criteria
            3. Priority and timeline optimization
            4. Potential subtasks or breaking down the work
            5. Risk mitigation and dependencies
            
            Be specific and actionable in your recommendations."""
            
            # Get AI suggestions
            suggestions = await claude_api.complete(prompt)
            
            if not suggestions:
                await interaction.followup.send(
                    "❌ Failed to get AI suggestions. Please try again later.",
                    ephemeral=True
                )
                return
            
            # Create suggestions embed
            embed = discord.Embed(
                title=f"🤖 AI Suggestions for Task",
                color=discord.Color.green()
            )
            embed.add_field(name="Task", value=f"{task['name']} ({task_id})", inline=False)
            embed.add_field(name="Current Status", value=task["status"]["status"], inline=True)
            embed.add_field(name="Priority", value=task.get("priority", {}).get("priority", "None"), inline=True)
            
            # Split suggestions if too long
            if len(suggestions) > 1024:
                embed.add_field(name="AI Suggestions (Part 1)", value=suggestions[:1024], inline=False)
                if len(suggestions) > 1024:
                    embed.add_field(name="AI Suggestions (Part 2)", value=suggestions[1024:2048], inline=False)
            else:
                embed.add_field(name="AI Suggestions", value=suggestions, inline=False)
            
            embed.set_footer(text="AI suggestions provided by Claude")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to get task suggestions: {e}")
            await interaction.followup.send(
                f"❌ Failed to get task suggestions: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AICommands(bot))