import discord
from utils.embed_factory import EmbedFactory

def create_setup_embeds():
    """Create setup and usage embeds for posting in Discord"""
    
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
    
    # Footer with call to action
    notes_embed.set_footer(text="🚀 Ready to start? Run /calendar-setup to begin!")
    
    return [setup_embed, commands_embed, status_embed, notes_embed]

# Usage example for posting:
# embeds = create_setup_embeds()
# for embed in embeds:
#     await channel.send(embed=embed)