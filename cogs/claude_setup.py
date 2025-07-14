import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.embed_factory import EmbedFactory
from repositories.claude_config import ClaudeConfigRepository
from services.claude_api import ClaudeAPI
from loguru import logger

class ClaudeAPIModal(discord.ui.Modal, title="Claude AI Setup"):
    def __init__(self):
        super().__init__()
        
        self.api_key = discord.ui.TextInput(
            label="Claude API Key",
            placeholder="Enter your Anthropic API key (sk-ant-...)",
            style=discord.TextStyle.short,
            required=True,
            min_length=10,
            max_length=200
        )
        
        self.add_item(self.api_key)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Test the API key
            test_api = ClaudeAPI(self.api_key.value)
            is_valid = await test_api.test_connection()
            
            if not is_valid:
                raise Exception("Invalid API key or Claude API is unreachable")
            
            # Save the configuration
            config = await ClaudeConfigRepository.create_or_update_config(
                guild_id=interaction.guild_id,
                api_key=self.api_key.value,
                added_by_user_id=interaction.user.id
            )
            
            embed = EmbedFactory.create_success_embed(
                "Claude AI Setup Complete",
                "✅ Successfully configured Claude AI for this server!"
            )
            
            embed.add_field(
                name="Configuration",
                value=f"• Model: `{config.model}`\n"
                      f"• Max Tokens: `{config.max_tokens}`\n"
                      f"• Temperature: `{config.temperature}`",
                inline=False
            )
            
            embed.add_field(
                name="Available Commands",
                value="• `/ai-create-task` - Create tasks from natural language\n"
                      "• `/ai-analyze-tasks` - AI-powered task analysis\n"
                      "• `/ai-task-suggestions` - Get AI suggestions for tasks\n"
                      "• `/claude-settings` - Adjust AI model settings",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            logger.info(f"Claude AI configured for guild {interaction.guild_id}")
            
        except Exception as e:
            logger.error(f"Error setting up Claude: {e}")
            
            embed = EmbedFactory.create_error_embed(
                "Setup Failed",
                f"❌ Failed to configure Claude AI: {str(e)}\n\n"
                "Please check that your API key is valid."
            )
            
            embed.add_field(
                name="Getting an API Key",
                value="1. Go to [console.anthropic.com](https://console.anthropic.com)\n"
                      "2. Navigate to API Keys section\n"
                      "3. Create a new API key\n"
                      "4. Copy the key (starts with `sk-ant-`)",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)


class ClaudeSetup(commands.Cog):
    """Commands for setting up and managing Claude AI integration"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="claude-setup", description="Configure Claude AI for enhanced task management")
    @app_commands.default_permissions(administrator=True)
    async def claude_setup(self, interaction: discord.Interaction):
        """Set up Claude AI integration"""
        
        # Check if already configured
        existing_config = await ClaudeConfigRepository.get_config(interaction.guild_id)
        
        if existing_config:
            embed = EmbedFactory.create_info_embed(
                "Claude AI Already Configured",
                "Claude AI is already set up for this server."
            )
            
            embed.add_field(
                name="Current Configuration",
                value=f"• Model: `{existing_config.model}`\n"
                      f"• Status: {'🟢 Enabled' if existing_config.is_enabled else '🔴 Disabled'}\n"
                      f"• Configured by: <@{existing_config.added_by_user_id}>",
                inline=False
            )
            
            # Update options
            class UpdateOptions(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                
                @discord.ui.button(label="Update API Key", style=discord.ButtonStyle.primary)
                async def update_key(self, interaction: discord.Interaction, button: discord.ui.Button):
                    modal = ClaudeAPIModal()
                    await interaction.response.send_modal(modal)
                
                @discord.ui.button(label="Disable Claude AI", style=discord.ButtonStyle.danger)
                async def disable_claude(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await ClaudeConfigRepository.disable_claude(interaction.guild_id)
                    
                    embed = EmbedFactory.create_success_embed(
                        "Claude AI Disabled",
                        "🔴 Claude AI has been disabled for this server."
                    )
                    await interaction.response.edit_message(embed=embed, view=None)
            
            await interaction.response.send_message(embed=embed, view=UpdateOptions(), ephemeral=True)
        else:
            # New setup
            embed = EmbedFactory.create_info_embed(
                "Claude AI Setup",
                "Let's set up Claude AI for enhanced task management!"
            )
            
            embed.add_field(
                name="What is Claude AI?",
                value="Claude AI powers intelligent features like:\n"
                      "• Natural language task creation\n"
                      "• Smart task analysis and prioritization\n"
                      "• AI-powered suggestions and insights",
                inline=False
            )
            
            embed.add_field(
                name="Requirements",
                value="You'll need an Anthropic API key to use Claude AI.\n"
                      "Visit [console.anthropic.com](https://console.anthropic.com) to get one.",
                inline=False
            )
            
            class SetupStart(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=60)
                
                @discord.ui.button(label="Start Setup", style=discord.ButtonStyle.success)
                async def start_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
                    modal = ClaudeAPIModal()
                    await interaction.response.send_modal(modal)
                
                @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                    embed = EmbedFactory.create_info_embed(
                        "Setup Cancelled",
                        "Claude AI setup has been cancelled."
                    )
                    await interaction.response.edit_message(embed=embed, view=None)
            
            await interaction.response.send_message(embed=embed, view=SetupStart(), ephemeral=True)
    
    @app_commands.command(name="claude-settings", description="Adjust Claude AI model settings")
    @app_commands.describe(
        model="Claude model to use",
        max_tokens="Maximum response length (default: 4096)",
        temperature="Creativity level 0.0-1.0 (default: 0.7)"
    )
    @app_commands.default_permissions(administrator=True)
    async def claude_settings(
        self,
        interaction: discord.Interaction,
        model: Optional[str] = None,
        max_tokens: Optional[app_commands.Range[int, 100, 8192]] = None,
        temperature: Optional[app_commands.Range[float, 0.0, 1.0]] = None
    ):
        """Adjust Claude AI settings"""
        
        config = await ClaudeConfigRepository.get_config(interaction.guild_id)
        if not config:
            embed = EmbedFactory.create_error_embed(
                "Not Configured",
                "Claude AI hasn't been set up yet. Use `/claude-setup` first."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not any([model, max_tokens, temperature]):
            # Show current settings
            embed = EmbedFactory.create_info_embed(
                "Claude AI Settings",
                "Current configuration:"
            )
            
            embed.add_field(name="Model", value=f"`{config.model}`", inline=True)
            embed.add_field(name="Max Tokens", value=f"`{config.max_tokens}`", inline=True)
            embed.add_field(name="Temperature", value=f"`{config.temperature}`", inline=True)
            
            embed.add_field(
                name="About Settings",
                value="• **Model**: The Claude model version to use\n"
                      "• **Max Tokens**: Maximum response length\n"
                      "• **Temperature**: Creativity (0=focused, 1=creative)",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Update settings
        success = await ClaudeConfigRepository.update_model_settings(
            interaction.guild_id,
            model=model if model else None,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        if success:
            embed = EmbedFactory.create_success_embed(
                "Settings Updated",
                "✅ Claude AI settings have been updated!"
            )
            
            updates = []
            if model:
                updates.append(f"• Model: `{model}`")
            if max_tokens is not None:
                updates.append(f"• Max Tokens: `{max_tokens}`")
            if temperature is not None:
                updates.append(f"• Temperature: `{temperature}`")
            
            if updates:
                embed.add_field(name="Changes", value="\n".join(updates), inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = EmbedFactory.create_error_embed(
                "Update Failed",
                "Failed to update Claude AI settings."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @claude_settings.autocomplete('model')
    async def model_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        models = [
            app_commands.Choice(name="Claude 3 Opus (Most Capable)", value="claude-3-opus-20240229"),
            app_commands.Choice(name="Claude 3 Sonnet (Balanced)", value="claude-3-sonnet-20240229"),
            app_commands.Choice(name="Claude 3 Haiku (Fast)", value="claude-3-haiku-20240307"),
            app_commands.Choice(name="Claude 2.1 (Legacy)", value="claude-2.1"),
        ]
        
        if current:
            return [m for m in models if current.lower() in m.name.lower()]
        return models
    
    @app_commands.command(name="claude-status", description="Check Claude AI status and usage")
    async def claude_status(self, interaction: discord.Interaction):
        """Check Claude AI status"""
        
        config = await ClaudeConfigRepository.get_config(interaction.guild_id)
        
        if not config:
            embed = EmbedFactory.create_info_embed(
                "Claude AI Not Configured",
                "Claude AI hasn't been set up for this server.\n"
                "Use `/claude-setup` to get started!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = EmbedFactory.create_info_embed(
            "Claude AI Status",
            f"{'🟢 Active' if config.is_enabled else '🔴 Disabled'}"
        )
        
        embed.add_field(
            name="Configuration",
            value=f"• Model: `{config.model}`\n"
                  f"• Max Tokens: `{config.max_tokens}`\n"
                  f"• Temperature: `{config.temperature}`",
            inline=True
        )
        
        embed.add_field(
            name="Setup Info",
            value=f"• Configured by: <@{config.added_by_user_id}>\n"
                  f"• Setup date: <t:{int(config.created_at.timestamp())}:R>",
            inline=True
        )
        
        # Test the connection
        try:
            api_key = await ClaudeConfigRepository.get_decrypted_api_key(config)
            api = ClaudeAPI(api_key)
            
            # Quick test
            is_working = await api.test_connection()
            
            if is_working:
                embed.add_field(
                    name="API Status",
                    value="✅ API connection is working",
                    inline=False
                )
            else:
                embed.add_field(
                    name="API Status",
                    value="⚠️ API connection failed",
                    inline=False
                )
                
        except Exception as e:
            embed.add_field(
                name="API Status",
                value=f"❌ API error: {str(e)}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ClaudeSetup(bot))