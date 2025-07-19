import discord
from discord.ext import commands
from discord import app_commands
from utils.embed_factory import EmbedFactory
from repositories.google_oauth_repository import GoogleOAuthRepository
from repositories.claude_config import ClaudeConfigRepository

class HelpCommand(commands.Cog):
    """Help and information commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="help", description="Get help with using the bot")
    async def help_command(self, interaction: discord.Interaction):
        """Show help information"""
        # Check configuration status
        credentials = await GoogleOAuthRepository.get_all_credentials(str(interaction.guild_id))
        claude_config = await ClaudeConfigRepository.get_config(interaction.guild_id)
        
        embed = EmbedFactory.create_info_embed(
            "🤖 CalendarBot Help",
            "Your Google Calendar integration for Discord!"
        )
        
        # Setup status
        setup_status = "❌ Not connected" if not credentials else f"✅ {len(credentials)} account(s)"
        ai_status = "❌ Not configured" if not claude_config else "✅ Enabled"
        
        embed.add_field(
            name="📊 Status",
            value=f"**Google Calendar:** {setup_status}\n**Claude AI:** {ai_status}",
            inline=False
        )
        
        # Getting started
        if not credentials:
            embed.add_field(
                name="🚀 Getting Started",
                value="1. Use `/calendar-setup` to connect Google Calendar\n"
                      "2. Grant calendar read permissions\n"
                      "3. Use `/calendar` to view your calendar\n"
                      "4. Use `/calendar-events` to list upcoming events",
                inline=False
            )
        
        # Core commands
        embed.add_field(
            name="📅 Calendar Commands",
            value="• `/calendar` - Monthly calendar view\n"
                  "• `/calendar-events` - List upcoming events\n"
                  "• `/calendar-today` - Today's events\n"
                  "• `/calendar-accounts` - Manage accounts",
            inline=True
        )
        
        embed.add_field(
            name="🔧 Setup Commands",
            value="• `/calendar-setup` - Connect Google Calendar\n"
                  "• `/claude-setup` - Enable AI features\n"
                  "• `/help` - Show this help",
            inline=True
        )
        
        # Other features
        embed.add_field(
            name="🎯 Other Features",
            value="• `/team-mood-setup` - Team status system\n"
                  "• `/reaction-roles` - Role assignment\n"
                  "• `/config-status` - Configuration health",
            inline=True
        )
        
        # AI commands (if configured)
        if claude_config:
            embed.add_field(
                name="🤖 AI Features",
                value="• AI conversation and assistance\n"
                      "• Claude-powered help and analysis\n"
                      "• `/claude-settings` - Configure AI",
                inline=True
            )
        else:
            embed.add_field(
                name="🤖 AI Features (Not Active)",
                value="Use `/claude-setup` to enable\nAI-powered assistance",
                inline=True
            )
        
        
        # Tips
        tips = [
            "💡 **Interactive calendar** - Navigate months with buttons",
            "🔄 **Multiple accounts** supported - connect different Google accounts",
            "📱 **Mobile friendly** - All features work on Discord mobile",
            "🔑 **Secure OAuth** - Uses Google's secure authentication"
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
            "About CalendarBot",
            "A powerful Discord bot for Google Calendar integration"
        )
        
        embed.add_field(
            name="Features",
            value="• Google Calendar integration\n"
                  "• Interactive calendar views\n"
                  "• Event listing and display\n"
                  "• AI-powered assistance\n"
                  "• Reaction roles\n"
                  "• Team mood tracking",
            inline=True
        )
        
        embed.add_field(
            name="Technology",
            value="• Built with discord.py\n"
                  "• Google Calendar API + OAuth2\n"
                  "• Claude AI integration\n"
                  "• PostgreSQL database\n"
                  "• Secure credential storage",
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
            title="🎉 CalendarBot Setup Guide",
            description="Follow these steps to get CalendarBot fully configured for your server.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📅 Step 1: Connect Google Calendar (Required)",
            value="1. Run `/calendar-setup`\n"
                  "2. Click **🔐 Login with Google**\n"
                  "3. Sign in and grant calendar permissions\n"
                  "4. You'll be redirected back here",
            inline=False
        )
        
        embed.add_field(
            name="🤖 Step 2: Enable AI Features (Optional)",
            value="For AI-powered assistance:\n"
                  "1. Get a Claude API key from [Anthropic](https://console.anthropic.com/)\n"
                  "2. Run `/claude-setup` and enter your key\n"
                  "3. AI features will be enabled!",
            inline=False
        )
        
        embed.add_field(
            inline=False
        )
        
        embed.add_field(
            name="✅ Quick Test",
            value="After setup, try these commands:\n"
                  "• `/calendar` - View your Google Calendar\n"
                  "• `/calendar-events` - List upcoming events\n"
                  "• `/help` - See all available commands",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Important Note",
            value="Make sure to grant calendar read permissions during OAuth setup. "
                  "Without proper permissions, the bot won't be able to display your calendar events.",
            inline=False
        )
        
        embed.set_footer(text="Need help? Use /help or check out our documentation!")
        
        # Create a view with helpful buttons
        class SetupGuideView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                
                # Add Google Calendar button
                self.add_item(discord.ui.Button(
                    label="Google Calendar",
                    url="https://calendar.google.com",
                    emoji="📅"
                ))
        
        await interaction.response.send_message(embed=embed, view=SetupGuideView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCommand(bot))