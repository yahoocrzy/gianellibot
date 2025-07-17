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
            value="• `/reaction-roles-setup` - Auto role assignment\n"
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

async def setup(bot):
    await bot.add_cog(HelpCommand(bot))