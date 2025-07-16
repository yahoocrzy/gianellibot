import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict, List
import json
import asyncio
from datetime import datetime, timedelta
from services.clickup_api import ClickUpAPI
from services.claude_api import ClaudeAPI
from repositories.clickup_workspaces import ClickUpWorkspaceRepository
from repositories.claude_config import ClaudeConfigRepository
from utils.embed_factory import EmbedFactory
from loguru import logger

class AIConversation(commands.Cog):
    """AI conversation mode for complex ClickUp operations"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_conversations = {}  # guild_id -> {user_id: conversation_data}
    
    @app_commands.command(name="ai-chat", description="Start an AI conversation for complex ClickUp operations")
    async def ai_chat(self, interaction: discord.Interaction):
        """Start a conversational AI session"""
        
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
        
        # Initialize conversation
        if interaction.guild_id not in self.active_conversations:
            self.active_conversations[interaction.guild_id] = {}
        
        # Get workspace information
        try:
            workspace = await ClickUpWorkspaceRepository.get_default_workspace(interaction.guild_id)
            workspace_id = workspace.workspace_id if workspace else None
        except Exception as e:
            logger.error(f"Error getting workspace: {e}")
            workspace_id = None
        
        self.active_conversations[interaction.guild_id][interaction.user.id] = {
            'started_at': datetime.now(),
            'context': [],
            'workspace_id': workspace_id
        }
        
        embed = EmbedFactory.create_info_embed(
            "🤖 AI Chat Mode Active",
            "I'm ready to help with your ClickUp tasks! You can ask me to:\n\n"
            "• Create, update, or delete tasks\n"
            "• Find and filter tasks\n"
            "• Move tasks between lists\n"
            "• Generate reports\n"
            "• Plan and organize work\n"
            "• And much more!\n\n"
            "Type your requests naturally. Say 'exit' to end the conversation."
        )
        
        embed.add_field(
            name="Examples",
            value="• 'Create a new feature task for the login system'\n"
                  "• 'Show me all high priority bugs'\n"
                  "• 'Move all completed tasks to the archive list'\n"
                  "• 'What tasks are due this week?'",
            inline=False
        )
        
        view = ConversationView(self, interaction.user.id, interaction.guild_id)
        await interaction.response.send_message(embed=embed, view=view)
    
    async def process_message(
        self,
        user_id: int,
        guild_id: int,
        message: str,
        interaction: discord.Interaction
    ):
        """Process a message in the conversation"""
        
        if guild_id not in self.active_conversations or \
           user_id not in self.active_conversations[guild_id]:
            await interaction.response.send_message(
                "No active conversation. Use `/ai-chat` to start.",
                ephemeral=True
            )
            return
        
        # Check for exit
        if message.lower() in ['exit', 'quit', 'stop', 'bye']:
            await self.end_conversation(user_id, guild_id, interaction)
            return
        
        # Add to context
        conversation = self.active_conversations[guild_id][user_id]
        conversation['context'].append({
            'role': 'user',
            'content': message
        })
        
        # Get APIs using workspace repository
        from repositories.clickup_workspaces import ClickUpWorkspaceRepository
        
        default_workspace = await ClickUpWorkspaceRepository.get_default_workspace(guild_id)
        if not default_workspace:
            return "❌ ClickUp not configured properly."
            
        token = await ClickUpWorkspaceRepository.get_decrypted_token(default_workspace)
        if not token:
            return "❌ ClickUp not configured properly."
            
        clickup_api = ClickUpAPI(token)
        
        api_key = await ClaudeConfigRepository.get_decrypted_api_key(
            await ClaudeConfigRepository.get_config(guild_id)
        )
        claude_api = ClaudeAPI(api_key)
        
        # Process with AI
        await interaction.response.defer()
        
        async with clickup_api:
            try:
                # Build conversation context
                context_str = "\n".join([
                    f"{msg['role']}: {msg['content']}" 
                    for msg in conversation['context'][-5:]  # Last 5 messages
                ])
                
                prompt = f"""You are an AI assistant helping with ClickUp task management.

Previous conversation:
{context_str}

Current request: {message}

Analyze what the user wants and provide:
1. Clear understanding of the request
2. Any clarifying questions needed
3. Actions you'll take
4. Expected outcome

Respond conversationally and helpfully."""

                response = await claude_api.create_message(prompt, max_tokens=1000)
                
                # Add AI response to context
                conversation['context'].append({
                    'role': 'assistant',
                    'content': response
                })
                
                # Create response embed
                embed = EmbedFactory.create_info_embed(
                    "🤖 AI Assistant",
                    response[:2000]  # Discord limit
                )
                
                # Add continue button
                view = ConversationView(self, user_id, guild_id)
                await interaction.followup.send(embed=embed, view=view)
                
                # Execute any detected actions
                await self._execute_conversation_actions(
                    interaction, clickup_api, claude_api, message, response
                )
                
            except Exception as e:
                logger.error(f"Error in AI conversation: {e}")
                embed = EmbedFactory.create_error_embed(
                    "Error",
                    f"Something went wrong: {str(e)}"
                )
                await interaction.followup.send(embed=embed)
    
    async def _execute_conversation_actions(
        self,
        interaction: discord.Interaction,
        clickup_api: ClickUpAPI,
        claude_api: ClaudeAPI,
        user_message: str,
        ai_response: str
    ):
        """Execute any actions mentioned in the conversation"""
        
        # Analyze for actionable items
        action_prompt = f"""Based on this conversation:
User: {user_message}
Assistant: {ai_response}

Identify any specific actions to take with ClickUp. Return JSON:
{{
    "actions": [
        {{
            "type": "create_task|update_task|list_tasks|none",
            "details": {{}}
        }}
    ],
    "needs_confirmation": true/false
}}"""

        action_response = await claude_api.create_message(action_prompt, max_tokens=500)
        
        try:
            json_start = action_response.find('{')
            json_end = action_response.rfind('}') + 1
            actions = json.loads(action_response[json_start:json_end])
            
            # Execute actions
            for action in actions.get('actions', []):
                if action['type'] == 'create_task':
                    # Implementation would go here
                    pass
                elif action['type'] == 'list_tasks':
                    # Implementation would go here
                    pass
                # etc...
                
        except Exception as e:
            logger.debug(f"No actions to execute: {e}")
    
    async def end_conversation(
        self,
        user_id: int,
        guild_id: int,
        interaction: discord.Interaction
    ):
        """End the conversation"""
        
        if guild_id in self.active_conversations and \
           user_id in self.active_conversations[guild_id]:
            
            conversation = self.active_conversations[guild_id][user_id]
            duration = datetime.now() - conversation['started_at']
            
            # Generate summary
            embed = EmbedFactory.create_success_embed(
                "Conversation Ended",
                f"Thanks for chatting! Here's what we accomplished:\n\n"
                f"**Duration:** {duration.seconds // 60} minutes\n"
                f"**Messages:** {len(conversation['context'])}"
            )
            
            # Clean up
            del self.active_conversations[guild_id][user_id]
            
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message(
                "No active conversation to end.",
                ephemeral=True
            )


class ConversationView(discord.ui.View):
    """View for conversation interactions"""
    
    def __init__(self, cog: AIConversation, user_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
    
    @discord.ui.button(label="Type Message", style=discord.ButtonStyle.primary, emoji="💬")
    async def type_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal for typing message"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This conversation belongs to another user.",
                ephemeral=True
            )
            return
        
        modal = MessageModal(self.cog, self.user_id, self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="End Chat", style=discord.ButtonStyle.danger, emoji="🛑")
    async def end_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        """End the conversation"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This conversation belongs to another user.",
                ephemeral=True
            )
            return
        
        await self.cog.end_conversation(self.user_id, self.guild_id, interaction)


class MessageModal(discord.ui.Modal, title="Chat with AI"):
    """Modal for typing messages in conversation"""
    
    def __init__(self, cog: AIConversation, user_id: int, guild_id: int):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        self.message = discord.ui.TextInput(
            label="Your Message",
            placeholder="Type your request or question...",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=1000
        )
        self.add_item(self.message)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process the submitted message"""
        await self.cog.process_message(
            self.user_id,
            self.guild_id,
            self.message.value,
            interaction
        )


async def setup(bot):
    await bot.add_cog(AIConversation(bot))