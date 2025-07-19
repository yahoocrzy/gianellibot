import discord
from discord.ext import commands
from discord import app_commands
from utils.embed_factory import EmbedFactory
from repositories.clickup_oauth_workspaces import ClickUpOAuthWorkspaceRepository
from repositories.claude_config import ClaudeConfigRepository

class HelpCommand(commands.Cog):
    """Help and information commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="help", description="Get help with using the bot")
    async def help_command(self, interaction: discord.Interaction):
        """Show help information"""
        # Check configuration status
        workspaces = await ClickUpOAuthWorkspaceRepository.get_all_workspaces(interaction.guild_id)
        claude_config = await ClaudeConfigRepository.get_config(interaction.guild_id)
        
        embed = EmbedFactory.create_info_embed(
            "🤖 ClickBot Help",
            "Your all-in-one ClickUp integration for Discord!"
        )
        
        # Setup status
        setup_status = "❌ Not configured" if not workspaces else f"✅ {len(workspaces)} workspace(s)"
        ai_status = "❌ Not configured" if not claude_config else "✅ Enabled"
        
        embed.add_field(
            name="📊 Status",
            value=f"**ClickUp:** {setup_status}\n**Claude AI:** {ai_status}",
            inline=False
        )
        
        # Getting started
        if not workspaces:
            embed.add_field(
                name="🚀 Getting Started",
                value="1. Use `/clickup-setup` to login with ClickUp\n"
                      "2. Use `/workspace-add-token` for full access\n"
                      "3. Use `/task-create` to create your first task\n"
                      "4. Use `/calendar` to view tasks in a calendar",
                inline=False
            )
        
        # Core commands
        embed.add_field(
            name="📋 Task Management",
            value="• `/task-create` - Create tasks with dropdowns\n"
                  "• `/task-update` - Update existing tasks\n"
                  "• `/task-list` - View tasks from a list\n"
                  "• `/task-delete` - Delete tasks safely",
            inline=True
        )
        
        embed.add_field(
            name="📅 Calendar & Views",
            value="• `/calendar` - Monthly calendar view\n"
                  "• `/upcoming` - Tasks for next N days\n"
                  "• `/today` - All tasks due today",
            inline=True
        )
        
        # Workspace commands
        embed.add_field(
            name="🏢 Workspace Management",
            value="• `/clickup-setup` - OAuth2 ClickUp setup\n"
                  "• `/workspace-add` - Add workspaces\n"
                  "• `/workspace-add-token` - Add personal token\n"
                  "• `/workspace-list` - View workspaces\n"
                  "• `/workspace-switch` - Change default",
            inline=True
        )
        
        # AI commands (if configured)
        if claude_config:
            embed.add_field(
                name="🤖 AI Features",
                value="• `/ai-create-task` - Natural language tasks\n"
                      "• `/ai-analyze-tasks` - AI task analysis\n"
                      "• `/claude-settings` - Configure AI",
                inline=True
            )
        else:
            embed.add_field(
                name="🤖 AI Features (Not Active)",
                value="Use `/claude-setup` to enable\nAI-powered task management",
                inline=True
            )
        
        # Other features
        embed.add_field(
            name="🎯 Other Features",
            value="• `/team-mood-setup` - Team status/availability system\n"
                  "• `/purge` - Advanced message cleanup\n"
                  "• `/config-status` - Check configuration health",
            inline=False
        )
        
        # Tips
        tips = [
            "💡 **No more typing IDs!** All commands use interactive dropdowns",
            "🔄 **Multiple workspaces** supported - switch between them easily",
            "📱 **Mobile friendly** - All features work on Discord mobile",
            "🔑 **Full access** - Add personal API token for space/task operations"
        ]
        
        embed.add_field(
            name="💡 Tips",
            value="\n".join(tips),
            inline=False
        )
        
        # Support
        embed.add_field(
            name="❓ Need Help?",
            value="• Check the [documentation](https://github.com/yourusername/clickbot)\n"
                  "• Report issues on GitHub\n"
                  "• Join our support server",
            inline=False
        )
        
        embed.set_footer(text="Use /help to see this message again")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="about", description="Information about the bot")
    async def about_command(self, interaction: discord.Interaction):
        """Show bot information"""
        embed = EmbedFactory.create_info_embed(
            "About ClickBot",
            "A powerful Discord bot for ClickUp integration"
        )
        
        embed.add_field(
            name="Features",
            value="• Multi-workspace support\n"
                  "• Full dropdown selections\n"
                  "• Calendar views\n"
                  "• AI-powered task management\n"
                  "• Reaction roles\n"
                  "• Advanced moderation",
            inline=True
        )
        
        embed.add_field(
            name="Technology",
            value="• Built with discord.py\n"
                  "• ClickUp API v2 + OAuth2\n"
                  "• Claude AI integration\n"
                  "• PostgreSQL database\n"
                  "• Hybrid token system",
            inline=True
        )
        
        embed.add_field(
            name="Statistics",
            value=f"• Servers: {len(self.bot.guilds)}\n"
                  f"• Commands: {len(self.bot.tree.get_commands())}\n"
                  f"• Uptime: <t:{int(self.bot.start_time.timestamp())}:R>",
            inline=False
        )
        
        embed.set_footer(text="Made with ❤️ for productivity")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setup-guide", description="Show the complete setup guide")
    async def setup_guide(self, interaction: discord.Interaction):
        """Show the complete setup guide"""
        embed = discord.Embed(
            title="🎉 ClickBot Setup Guide",
            description="Follow these steps to get ClickBot fully configured for your server.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Step 1: Connect ClickUp (Required)",
            value="1. Run `/clickup-setup`\n"
                  "2. Click **🔐 Login with ClickUp**\n"
                  "3. Sign in and select your workspaces\n"
                  "4. You'll be redirected back here",
            inline=False
        )
        
        embed.add_field(
            name="🔑 Step 2: Add Personal API Token (Required for Full Access)",
            value="Due to ClickUp's OAuth limitations, you need a personal token for task operations:\n"
                  "1. Go to [ClickUp Settings > Apps](https://app.clickup.com/settings/apps)\n"
                  "2. Find **Personal API Token** and click **Generate**\n"
                  "3. Copy the token (starts with `pk_`)\n"
                  "4. Run `/workspace-add-token` and paste it",
            inline=False
        )
        
        embed.add_field(
            name="🤖 Step 3: Enable AI Features (Optional)",
            value="For AI-powered task management:\n"
                  "1. Get a Claude API key from [Anthropic](https://console.anthropic.com/)\n"
                  "2. Run `/claude-setup` and enter your key\n"
                  "3. AI commands will be unlocked!",
            inline=False
        )
        
        embed.add_field(
            name="✅ Quick Test",
            value="After setup, try these commands:\n"
                  "• `/task-create` - Create your first task\n"
                  "• `/calendar` - View tasks in calendar\n"
                  "• `/help` - See all available commands",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Important Note",
            value="Without a personal API token, you'll see **'Team(s) not authorized'** errors. "
                  "This is a ClickUp limitation - the personal token provides full access to your spaces and tasks.",
            inline=False
        )
        
        embed.set_footer(text="Need help? Use /help or check out our documentation!")
        
        # Create a view with helpful buttons
        class SetupGuideView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                
                # Add ClickUp setup button
                self.add_item(discord.ui.Button(
                    label="ClickUp Settings",
                    url="https://app.clickup.com/settings/apps",
                    emoji="🔗"
                ))
        
        await interaction.response.send_message(embed=embed, view=SetupGuideView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCommand(bot))