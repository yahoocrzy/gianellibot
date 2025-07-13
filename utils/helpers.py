from datetime import datetime, timedelta
import re
from typing import Optional, Union
import discord
from discord.ext import commands
from repositories.server_config import ServerConfigRepository

async def get_prefix(bot: commands.Bot, message: discord.Message) -> str:
    """Get the prefix for a guild"""
    if not message.guild:
        return "!"
    
    repo = ServerConfigRepository()
    config = await repo.get_config(message.guild.id)
    
    if config and config.get('prefix'):
        return config['prefix']
    
    return "!"

def parse_due_date(date_string: str) -> Optional[datetime]:
    """Parse various date formats into datetime"""
    date_string = date_string.lower().strip()
    now = datetime.utcnow()
    
    # Relative dates
    if date_string == "today":
        return now.replace(hour=23, minute=59, second=59)
    elif date_string == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)
    elif date_string == "next week":
        return (now + timedelta(weeks=1)).replace(hour=23, minute=59, second=59)
    
    # Try to parse ISO format
    try:
        return datetime.fromisoformat(date_string)
    except:
        pass
    
    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except:
            continue
    
    return None

def format_task_status(status: str) -> str:
    """Convert task status to emoji"""
    status_emojis = {
        "to do": "⬜",
        "in progress": "🔵",
        "review": "🟡",
        "complete": "✅",
        "closed": "❌",
        "blocked": "🚫"
    }
    return status_emojis.get(status.lower(), "❓")

def truncate_text(text: str, max_length: int = 1024) -> str:
    """Truncate text to fit Discord embed limits"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def format_user_mention(user_id: Union[str, int]) -> str:
    """Format user ID as Discord mention"""
    return f"<@{user_id}>"

def parse_mentions(text: str) -> list[int]:
    """Extract user IDs from mentions in text"""
    mention_pattern = r'<@!?(\d+)>'
    matches = re.findall(mention_pattern, text)
    return [int(user_id) for user_id in matches]

def humanize_timedelta(td: timedelta) -> str:
    """Convert timedelta to human-readable string"""
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds and not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    return " ".join(parts) if parts else "0 seconds"