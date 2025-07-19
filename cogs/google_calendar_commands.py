import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import calendar
from typing import List, Optional
from loguru import logger

from services.google_calendar_api import GoogleCalendarAPI
from repositories.google_oauth_repository import GoogleOAuthRepository
from utils.embed_factory import EmbedFactory
import os

class GoogleCalendarCommands(commands.Cog):
    """Commands for Google Calendar integration"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def get_calendar_api(self, guild_id: str, user_id: str = None) -> Optional[GoogleCalendarAPI]:
        """Get Google Calendar API instance for a guild/user"""
        cred = await GoogleOAuthRepository.get_credentials(guild_id, user_id)
        if not cred:
            return None
        
        decrypted_creds = GoogleOAuthRepository.decrypt_credentials(cred.credentials_encrypted)
        if not decrypted_creds:
            return None
        
        return GoogleCalendarAPI(decrypted_creds)
    
    @app_commands.command(name="calendar-setup", description="Connect your Google Calendar to Discord")
    async def calendar_setup(self, interaction: discord.Interaction):
        """Setup Google Calendar OAuth2 connection"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create OAuth state
            state, auth_url = await GoogleOAuthRepository.create_oauth_state(
                str(interaction.guild_id),
                str(interaction.user.id)
            )
            
            # Create setup embed
            embed = EmbedFactory.create_info_embed(
                title="🔐 Google Calendar Setup",
                description="Click the button below to connect your Google Calendar"
            )
            
            embed.add_field(
                name="What happens next?",
                value="1. You'll be redirected to Google\n"
                      "2. Sign in and grant calendar access\n"
                      "3. You'll be redirected back here\n"
                      "4. Your calendar will be connected!",
                inline=False
            )
            
            embed.add_field(
                name="Required Permissions",
                value="• Read access to your calendars\n"
                      "• View calendar events",
                inline=False
            )
            
            # Create button
            class SetupView(discord.ui.View):
                def __init__(self, auth_url: str):
                    super().__init__(timeout=180)
                    self.add_item(discord.ui.Button(
                        label="🔗 Connect Google Calendar",
                        url=auth_url,
                        style=discord.ButtonStyle.link
                    ))
            
            await interaction.followup.send(embed=embed, view=SetupView(auth_url), ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in calendar setup: {e}")
            embed = EmbedFactory.create_error_embed(
                title="Setup Error",
                description=f"Failed to create setup link: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="calendar", description="View your Google Calendar")
    async def calendar_view(
        self,
        interaction: discord.Interaction,
        month: Optional[int] = None,
        year: Optional[int] = None
    ):
        """Display calendar view with events"""
        await interaction.response.defer()
        
        # Get calendar API
        api = await self.get_calendar_api(str(interaction.guild_id))
        if not api:
            embed = EmbedFactory.create_error_embed(
                title="Not Connected",
                description="No Google Calendar connected. Use `/calendar-setup` to connect."
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Default to current month/year
        now = datetime.now()
        if not month:
            month = now.month
        if not year:
            year = now.year
        
        try:
            # Get month start and end
            month_start = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            else:
                month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            
            # Get events for the month
            events = await api.list_events(
                time_min=month_start,
                time_max=month_end,
                max_results=100
            )
            
            # Create calendar embed
            embed = discord.Embed(
                title=f"📅 {calendar.month_name[month]} {year}",
                color=discord.Color.blue()
            )
            
            # Create calendar grid
            cal = calendar.monthcalendar(year, month)
            cal_text = "```\n"
            cal_text += "Su Mo Tu We Th Fr Sa\n"
            
            # Process events by day
            events_by_day = {}
            for event in events:
                start_time, _ = GoogleCalendarAPI.parse_event_time(event)
                if start_time.month == month and start_time.year == year:
                    day = start_time.day
                    if day not in events_by_day:
                        events_by_day[day] = 0
                    events_by_day[day] += 1
            
            # Build calendar
            for week in cal:
                for day in week:
                    if day == 0:
                        cal_text += "   "
                    else:
                        if day in events_by_day:
                            # Day with events - add indicator
                            cal_text += f"{day:2}*"
                        else:
                            cal_text += f"{day:2} "
                cal_text += "\n"
            
            cal_text += "```"
            embed.description = cal_text
            
            # Add legend
            if events_by_day:
                embed.add_field(
                    name="Legend",
                    value="* = Has events",
                    inline=False
                )
                
                # List today's events if viewing current month
                if month == now.month and year == now.year:
                    today_events = [e for e in events if GoogleCalendarAPI.parse_event_time(e)[0].day == now.day]
                    if today_events:
                        today_text = ""
                        for event in today_events[:5]:  # Limit to 5 events
                            start_time, _ = GoogleCalendarAPI.parse_event_time(event)
                            time_str = start_time.strftime("%I:%M %p")
                            title = event.get('summary', 'No Title')
                            today_text += f"• {time_str}: {title}\n"
                        
                        if len(today_events) > 5:
                            today_text += f"... and {len(today_events) - 5} more"
                        
                        embed.add_field(
                            name=f"Today's Events ({now.strftime('%B %d')})",
                            value=today_text,
                            inline=False
                        )
            
            # Navigation buttons
            class CalendarView(discord.ui.View):
                def __init__(self, current_month: int, current_year: int):
                    super().__init__(timeout=300)
                    self.month = current_month
                    self.year = current_year
                
                @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.primary)
                async def previous_month(self, interaction: discord.Interaction, button: discord.ui.Button):
                    # Calculate previous month
                    if self.month == 1:
                        new_month = 12
                        new_year = self.year - 1
                    else:
                        new_month = self.month - 1
                        new_year = self.year
                    
                    # Rerun command with new month/year
                    await interaction.response.defer()
                    cog = interaction.client.get_cog('GoogleCalendarCommands')
                    await cog.calendar_view.callback(cog, interaction, new_month, new_year)
                
                @discord.ui.button(label="Today", style=discord.ButtonStyle.success)
                async def today(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer()
                    cog = interaction.client.get_cog('GoogleCalendarCommands')
                    now = datetime.now()
                    await cog.calendar_view.callback(cog, interaction, now.month, now.year)
                
                @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary)
                async def next_month(self, interaction: discord.Interaction, button: discord.ui.Button):
                    # Calculate next month
                    if self.month == 12:
                        new_month = 1
                        new_year = self.year + 1
                    else:
                        new_month = self.month + 1
                        new_year = self.year
                    
                    # Rerun command with new month/year
                    await interaction.response.defer()
                    cog = interaction.client.get_cog('GoogleCalendarCommands')
                    await cog.calendar_view.callback(cog, interaction, new_month, new_year)
            
            await interaction.followup.send(embed=embed, view=CalendarView(month, year))
            
        except Exception as e:
            logger.error(f"Error displaying calendar: {e}")
            embed = EmbedFactory.create_error_embed(
                title="Calendar Error",
                description=f"Failed to display calendar: {str(e)}"
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="calendar-events", description="List upcoming Google Calendar events")
    async def calendar_events(
        self,
        interaction: discord.Interaction,
        days: Optional[int] = 7
    ):
        """List upcoming events from Google Calendar"""
        await interaction.response.defer()
        
        # Get calendar API
        api = await self.get_calendar_api(str(interaction.guild_id))
        if not api:
            embed = EmbedFactory.create_error_embed(
                title="Not Connected",
                description="No Google Calendar connected. Use `/calendar-setup` to connect."
            )
            await interaction.followup.send(embed=embed)
            return
        
        try:
            # Get events for next N days
            now = datetime.now(timezone.utc)
            end_date = now + timedelta(days=days)
            
            events = await api.list_events(
                time_min=now,
                time_max=end_date,
                max_results=25
            )
            
            if not events:
                embed = EmbedFactory.create_info_embed(
                    title="No Upcoming Events",
                    description=f"No events found in the next {days} days."
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Create events embed
            embed = discord.Embed(
                title=f"📅 Upcoming Events (Next {days} Days)",
                color=discord.Color.blue(),
                timestamp=now
            )
            
            # Group events by date
            events_by_date = {}
            for event in events:
                start_time, _ = GoogleCalendarAPI.parse_event_time(event)
                date_key = start_time.strftime("%A, %B %d")
                
                if date_key not in events_by_date:
                    events_by_date[date_key] = []
                
                events_by_date[date_key].append(event)
            
            # Add events to embed
            for date_str, date_events in events_by_date.items():
                field_value = ""
                for event in date_events[:5]:  # Limit to 5 events per day
                    start_time, end_time = GoogleCalendarAPI.parse_event_time(event)
                    
                    # Format time
                    if 'date' in event.get('start', {}):
                        # All-day event
                        time_str = "All Day"
                    else:
                        time_str = f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"
                    
                    title = event.get('summary', 'No Title')
                    location = event.get('location', '')
                    
                    field_value += f"**{time_str}**\n{title}"
                    if location:
                        field_value += f" 📍 {location}"
                    field_value += "\n\n"
                
                if len(date_events) > 5:
                    field_value += f"... and {len(date_events) - 5} more events"
                
                embed.add_field(
                    name=date_str,
                    value=field_value.strip(),
                    inline=False
                )
            
            embed.set_footer(text=f"Total: {len(events)} events")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing events: {e}")
            embed = EmbedFactory.create_error_embed(
                title="Events Error",
                description=f"Failed to list events: {str(e)}"
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="calendar-today", description="Show today's Google Calendar events")
    async def calendar_today(self, interaction: discord.Interaction):
        """Show today's events"""
        await interaction.response.defer()
        
        # Get calendar API
        api = await self.get_calendar_api(str(interaction.guild_id))
        if not api:
            embed = EmbedFactory.create_error_embed(
                title="Not Connected",
                description="No Google Calendar connected. Use `/calendar-setup` to connect."
            )
            await interaction.followup.send(embed=embed)
            return
        
        try:
            # Get today's events
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            
            events = await api.list_events(
                time_min=today_start,
                time_max=today_end,
                max_results=50
            )
            
            # Create embed
            embed = discord.Embed(
                title=f"📅 Today's Events - {now.strftime('%A, %B %d, %Y')}",
                color=discord.Color.blue()
            )
            
            if not events:
                embed.description = "No events scheduled for today."
            else:
                # Sort events by start time
                sorted_events = sorted(events, key=lambda e: GoogleCalendarAPI.parse_event_time(e)[0])
                
                for event in sorted_events:
                    start_time, end_time = GoogleCalendarAPI.parse_event_time(event)
                    
                    # Format time
                    if 'date' in event.get('start', {}):
                        time_str = "All Day"
                    else:
                        time_str = f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"
                    
                    title = event.get('summary', 'No Title')
                    description = event.get('description', '')
                    location = event.get('location', '')
                    
                    field_value = f"⏰ {time_str}"
                    if location:
                        field_value += f"\n📍 {location}"
                    if description:
                        # Truncate description if too long
                        desc_preview = description[:100] + "..." if len(description) > 100 else description
                        field_value += f"\n📝 {desc_preview}"
                    
                    embed.add_field(
                        name=title,
                        value=field_value,
                        inline=False
                    )
            
            embed.set_footer(text=f"Total: {len(events)} events today")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing today's events: {e}")
            embed = EmbedFactory.create_error_embed(
                title="Today's Events Error",
                description=f"Failed to show today's events: {str(e)}"
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="calendar-accounts", description="Manage connected Google Calendar accounts")
    async def calendar_accounts(self, interaction: discord.Interaction):
        """List and manage connected Google accounts"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get all credentials for the guild
            credentials = await GoogleOAuthRepository.get_all_credentials(str(interaction.guild_id))
            
            if not credentials:
                embed = EmbedFactory.create_info_embed(
                    title="No Accounts Connected",
                    description="No Google Calendar accounts are connected. Use `/calendar-setup` to connect."
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Create accounts embed
            embed = discord.Embed(
                title="🔗 Connected Google Calendar Accounts",
                color=discord.Color.blue()
            )
            
            for cred in credentials:
                user = self.bot.get_user(int(cred.user_id))
                user_name = user.name if user else f"User {cred.user_id}"
                
                field_value = f"📧 {cred.email}\n"
                field_value += f"👤 Added by: {user_name}\n"
                field_value += f"📅 Connected: {cred.created_at.strftime('%Y-%m-%d')}"
                
                if cred.is_default:
                    field_value += "\n⭐ **Default Account**"
                
                embed.add_field(
                    name=f"Account {credentials.index(cred) + 1}",
                    value=field_value,
                    inline=False
                )
            
            # Management buttons
            class AccountsView(discord.ui.View):
                def __init__(self, accounts: List, user_id: int):
                    super().__init__(timeout=180)
                    self.accounts = accounts
                    self.user_id = user_id
                
                @discord.ui.button(label="Set Default", style=discord.ButtonStyle.primary)
                async def set_default(self, interaction: discord.Interaction, button: discord.ui.Button):
                    # Check if user has an account
                    user_account = next((a for a in self.accounts if a.user_id == str(interaction.user.id)), None)
                    if not user_account:
                        await interaction.response.send_message(
                            "You don't have a connected account. Use `/calendar-setup` first.",
                            ephemeral=True
                        )
                        return
                    
                    # Set as default
                    success = await GoogleOAuthRepository.set_default_credentials(
                        str(interaction.guild_id),
                        str(interaction.user.id)
                    )
                    
                    if success:
                        await interaction.response.send_message(
                            "✅ Your account has been set as the default.",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            "❌ Failed to set default account.",
                            ephemeral=True
                        )
                
                @discord.ui.button(label="Remove My Account", style=discord.ButtonStyle.danger)
                async def remove_account(self, interaction: discord.Interaction, button: discord.ui.Button):
                    success = await GoogleOAuthRepository.remove_credentials(
                        str(interaction.guild_id),
                        str(interaction.user.id)
                    )
                    
                    if success:
                        await interaction.response.send_message(
                            "✅ Your Google Calendar account has been disconnected.",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message(
                            "❌ No account found to remove.",
                            ephemeral=True
                        )
            
            await interaction.followup.send(
                embed=embed,
                view=AccountsView(credentials, interaction.user.id),
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error managing accounts: {e}")
            embed = EmbedFactory.create_error_embed(
                title="Accounts Error",
                description=f"Failed to manage accounts: {str(e)}"
            )
            await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(GoogleCalendarCommands(bot))