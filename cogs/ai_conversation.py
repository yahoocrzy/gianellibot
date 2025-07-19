import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict, List
import json
import asyncio
from datetime import datetime, timedelta
# from services.clickup_api import ClickUpAPI  # Removed ClickUp dependency
from services.claude_api import ClaudeAPI
# from repositories.clickup_oauth_workspaces import ClickUpOAuthWorkspaceRepository  # Removed ClickUp dependency
from repositories.claude_config import ClaudeConfigRepository
from utils.embed_factory import EmbedFactory
from loguru import logger

class AIConversation(commands.Cog):
    """AI conversation mode with Claude functionality (ClickUp operations disabled)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_conversations = {}  # guild_id -> {user_id: conversation_data}
    
    @app_commands.command(name="ai-chat", description="Start an AI conversation with Claude (ClickUp operations disabled)")
    async def ai_chat(self, interaction: discord.Interaction):
        """Start a conversational AI session with Claude only"""
        
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
        
        self.active_conversations[interaction.guild_id][interaction.user.id] = {
            'started_at': datetime.now(),
            'context': [],
            'workspace_id': None  # No ClickUp workspace
        }
        
        embed = EmbedFactory.create_info_embed(
            "🤖 AI Chat Mode Active",
            "I'm ready to help you with general AI assistance! You can ask me to:\n\n"
            "• Answer questions and provide information\n"
            "• Help with writing and editing\n"
            "• Explain concepts and topics\n"
            "• Provide suggestions and advice\n"
            "• Generate creative content\n"
            "• And much more!\n\n"
            "**Note:** ClickUp task management features have been disabled.\n\n"
            "Type your requests naturally. Say 'exit' to end the conversation."
        )
        
        embed.add_field(
            name="Examples",
            value="• 'Help me write a professional email'\n"
                  "• 'Explain how machine learning works'\n"
                  "• 'Give me some creative writing prompts'\n"
                  "• 'What are best practices for project management?'",
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
        
        # Get Claude API only (ClickUp removed)
        api_key = await ClaudeConfigRepository.get_decrypted_api_key(
            await ClaudeConfigRepository.get_config(guild_id)
        )
        claude_api = ClaudeAPI(api_key)
        
        # Process with AI
        await interaction.response.defer()
        
        try:
            # Build conversation context
            context_str = "\n".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in conversation['context'][-5:]  # Last 5 messages
            ])
            
            prompt = f"""You are a helpful AI assistant.

Previous conversation:
{context_str}

Current request: {message}

Analyze what the user wants and provide:
1. Clear understanding of the request
2. Any clarifying questions needed
3. Helpful information or suggestions
4. Next steps if applicable

Note: ClickUp task management features are not available.

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
            
            # Note: ClickUp action execution has been disabled
            # await self._execute_conversation_actions(
            #     interaction, claude_api, message, response
            # )
            
        except Exception as e:
            logger.error(f"Error in AI conversation: {e}")
            embed = EmbedFactory.create_error_embed(
                "Error",
                f"Something went wrong: {str(e)}"
            )
            await interaction.followup.send(embed=embed)
    
    # async def _execute_conversation_actions(
    #     self,
    #     interaction: discord.Interaction,
    #     claude_api: ClaudeAPI,
    #     user_message: str,
    #     ai_response: str
    # ):
    #     """Execute any actions mentioned in the conversation - DISABLED"""
    #     # ClickUp action execution has been disabled due to dependency removal
    #     pass
    
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