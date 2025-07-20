import discord
from typing import Optional, List, Dict, Any
from datetime import datetime

class EmbedFactory:
    """Factory for creating consistent embed styles"""
    
    # Color scheme
    COLORS = {
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "warning": discord.Color.yellow(),
        "info": discord.Color.blue(),
        "primary": discord.Color.blurple()
    }
    
    @staticmethod
    def create_base_embed(
        title: str,
        description: Optional[str] = None,
        color: Optional[discord.Color] = None
    ) -> discord.Embed:
        """Create base embed with consistent styling"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color or EmbedFactory.COLORS["primary"],
            timestamp=datetime.utcnow()
        )
        return embed
    
    @staticmethod
    def create_success_embed(title: str, description: str) -> discord.Embed:
        """Create success embed"""
        return EmbedFactory.create_base_embed(
            f"✅ {title}",
            description,
            EmbedFactory.COLORS["success"]
        )
    
    @staticmethod
    def create_error_embed(title: str, description: str) -> discord.Embed:
        """Create error embed"""
        return EmbedFactory.create_base_embed(
            f"❌ {title}",
            description,
            EmbedFactory.COLORS["error"]
        )
    
    @staticmethod
    def create_warning_embed(title: str, description: str) -> discord.Embed:
        """Create warning embed"""
        return EmbedFactory.create_base_embed(
            f"⚠️ {title}",
            description,
            EmbedFactory.COLORS["warning"]
        )
    
    @staticmethod
    def create_info_embed(title: str, description: str) -> discord.Embed:
        """Create info embed"""
        return EmbedFactory.create_base_embed(
            f"ℹ️ {title}",
            description,
            EmbedFactory.COLORS["info"]
        )
    
    
    @staticmethod
    def create_list_embed(
        title: str,
        items: List[str],
        description: Optional[str] = None,
        color: Optional[discord.Color] = None
    ) -> discord.Embed:
        """Create embed for displaying lists"""
        embed = EmbedFactory.create_base_embed(title, description, color)
        
        # Split items into chunks if needed (Discord field limit)
        for i in range(0, len(items), 10):
            chunk = items[i:i+10]
            field_value = "\n".join(chunk)
            embed.add_field(
                name=f"Items {i+1}-{min(i+10, len(items))}",
                value=field_value or "None",
                inline=False
            )
        
        return embed