import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

class SetupGuide(commands.Cog):
    """Commands for posting setup guides"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="post-setup-guide", description="Post the bot setup and usage guide")
    @app_commands.describe(
        channel="Channel to post the guide in (defaults to current channel)"
    )
    async def post_setup_guide(
        self, 
        interaction: discord.Interaction, 
        channel: Optional[discord.TextChannel] = None
    ):
        """Post setup and usage guide embeds"""
        
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need Administrator permissions to post setup guides.", 
                ephemeral=True
            )
            return
        
        target_channel = channel or interaction.channel
        await interaction.response.defer()
        
        try:
            # Main Setup Embed
            setup_embed = discord.Embed(
                title="🗓️ CalendarBot Setup & Usage Guide",
                description="Complete guide to set up and use all CalendarBot features",
                color=discord.Color.blue()
            )
            
            setup_embed.add_field(
                name="📋 Step 1: Connect Google Calendar",
                value="1. Run `/calendar-setup`\n"
                      "2. Click **🔐 Login with Google**\n"
                      "3. Sign in to your Google account\n"
                      "4. Authorize calendar access\n"
                      "5. Setup complete!",
                inline=False
            )
            
            setup_embed.add_field(
                name="🤖 Step 2: Enable AI Features (Optional)",
                value="1. Get Claude API key from [Anthropic](https://console.anthropic.com/)\n"
                      "2. Run `/claude-setup` and enter your key\n"
                      "3. AI commands unlocked!",
                inline=False
            )
            
            # Commands Embed
            commands_embed = discord.Embed(
                title="📋 Available Commands",
                color=discord.Color.green()
            )
            
            commands_embed.add_field(
                name="📅 Calendar Commands",
                value="`/calendar` - View monthly calendar\n"
                      "`/calendar-events` - List upcoming events\n"
                      "`/calendar-today` - See today's events\n"
                      "`/calendar-setup` - Connect Google Calendar",
                inline=True
            )
            
            commands_embed.add_field(
                name="🤖 AI Commands",
                value="`/ai-chat` - Start Claude conversation\n"
                      "`/ai-assistant` - AI task assistance\n"
                      "`/ai-create-task` - AI task parsing\n"
                      "`/claude-setup` - Configure AI",
                inline=True
            )
            
            commands_embed.add_field(
                name="🎭 Team Mood System",
                value="`/team-mood-setup` - Create status system\n"
                      "`/team-mood-status` - View team stats\n"
                      "`/team-mood-refresh` - Recreate message\n"
                      "`/team-mood-remove` - Remove system",
                inline=False
            )
            
            commands_embed.add_field(
                name="⚡ Reaction Roles",
                value="`/reaction-roles-setup` - Create system\n"
                      "`/reaction-roles-add` - Add emoji→role\n"
                      "`/reaction-roles-remove` - Remove mapping",
                inline=True
            )
            
            commands_embed.add_field(
                name="🔧 Admin Commands",
                value="`/clear-messages` - Bulk delete\n"
                      "`/purge-user` - Delete user messages\n"
                      "`/help` - Show all commands",
                inline=True
            )
            
            # Status Options Embed
            status_embed = discord.Embed(
                title="🎭 Team Mood Status Options",
                description="Click reactions to set your availability status",
                color=discord.Color.gold()
            )
            
            status_embed.add_field(
                name="Available Statuses",
                value="✅ **Ready to Work** - Available for tasks\n"
                      "⚠️ **Phone Only** - Available by phone/urgent only\n"
                      "🛑 **Do not disturb** - Focused work, no interruptions\n"
                      "💤 **Need time** - Taking a break or unavailable",
                inline=False
            )
            
            # Important Notes Embed
            notes_embed = discord.Embed(
                title="⚠️ Important Notes",
                color=discord.Color.orange()
            )
            
            notes_embed.add_field(
                name="🔑 Requirements",
                value="• Bot needs **Administrator** permissions\n"
                      "• Google Calendar requires **read permissions**\n"
                      "• Claude AI requires separate **API key**\n"
                      "• Team Mood works best in **dedicated channels**",
                inline=False
            )
            
            notes_embed.add_field(
                name="🆘 Troubleshooting",
                value="1. Check bot permissions in server settings\n"
                      "2. Reconnect Google Calendar with `/calendar-setup`\n"
                      "3. Ensure Google Calendar API is enabled\n"
                      "4. Contact server administrators for help",
                inline=False
            )
            
            notes_embed.set_footer(text="🚀 Ready to start? Run /calendar-setup to begin!")
            
            # Post all embeds
            embeds = [setup_embed, commands_embed, status_embed, notes_embed]
            
            for embed in embeds:
                await target_channel.send(embed=embed)
            
            await interaction.followup.send(
                f"✅ Setup guide posted successfully in {target_channel.mention}!", 
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to post setup guide: {str(e)}", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(SetupGuide(bot))