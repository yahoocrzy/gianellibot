"""
Enhanced debug logging system for the bot
"""
import os
import sys
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger
import discord
from discord.ext import commands

class DebugLogger:
    """Enhanced debug logger with structured logging"""
    
    def __init__(self):
        self.setup_logger()
        self.startup_time = datetime.utcnow()
        self.events = []
        self.errors = []
        
    def setup_logger(self):
        """Configure enhanced logging"""
        # Remove default logger
        logger.remove()
        
        # Console logging with detailed format
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="DEBUG" if os.getenv("DEBUG", "false").lower() == "true" else "INFO"
        )
        
        # File logging with rotation
        logger.add(
            "logs/debug_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="14 days",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        )
        
        # Error file logging
        logger.add(
            "logs/errors_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="30 days",
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{extra}"
        )
        
    def log_event(self, event_type: str, data: Dict[str, Any], level: str = "INFO"):
        """Log structured event"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "data": data
        }
        self.events.append(event)
        
        # Keep only last 1000 events in memory
        if len(self.events) > 1000:
            self.events = self.events[-1000:]
            
        logger.log(level, f"[{event_type}] {json.dumps(data, default=str)}")
        
    def log_error(self, error: Exception, context: Dict[str, Any]):
        """Log error with full context"""
        error_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context
        }
        self.errors.append(error_data)
        
        # Keep only last 100 errors in memory
        if len(self.errors) > 100:
            self.errors = self.errors[-100:]
            
        logger.error(f"[{error_data['error_type']}] {error_data['error_message']}")
        logger.debug(f"Context: {json.dumps(context, default=str)}")
        logger.debug(f"Traceback:\n{error_data['traceback']}")
        
    def log_cog_load(self, cog_name: str, success: bool, error: Optional[Exception] = None):
        """Log cog loading status"""
        data = {
            "cog": cog_name,
            "success": success
        }
        if error:
            data["error"] = str(error)
            self.log_error(error, {"cog": cog_name, "action": "load"})
        
        self.log_event("cog_load", data, "INFO" if success else "ERROR")
        
    def log_command(self, ctx: commands.Context, error: Optional[Exception] = None):
        """Log command execution"""
        data = {
            "command": ctx.command.name if ctx.command else "unknown",
            "user": str(ctx.author),
            "guild": str(ctx.guild) if ctx.guild else "DM",
            "channel": str(ctx.channel),
            "args": str(ctx.args),
            "kwargs": str(ctx.kwargs)
        }
        
        if error:
            data["error"] = str(error)
            self.log_error(error, data)
        else:
            self.log_event("command", data)
            
    def log_api_call(self, service: str, endpoint: str, success: bool, 
                     response_code: Optional[int] = None, error: Optional[Exception] = None):
        """Log API calls"""
        data = {
            "service": service,
            "endpoint": endpoint,
            "success": success,
            "response_code": response_code
        }
        
        if error:
            data["error"] = str(error)
            
        self.log_event("api_call", data, "INFO" if success else "WARNING")
        
    def get_debug_stats(self) -> Dict[str, Any]:
        """Get debug statistics"""
        return {
            "uptime": str(datetime.utcnow() - self.startup_time),
            "total_events": len(self.events),
            "total_errors": len(self.errors),
            "recent_errors": self.errors[-5:],
            "event_types": self._count_event_types()
        }
        
    def _count_event_types(self) -> Dict[str, int]:
        """Count events by type"""
        counts = {}
        for event in self.events:
            event_type = event.get("type", "unknown")
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts
        
    def create_debug_embed(self) -> discord.Embed:
        """Create debug information embed"""
        stats = self.get_debug_stats()
        
        embed = discord.Embed(
            title="🔍 Debug Information",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="System Status",
            value=f"**Uptime:** {stats['uptime']}\n"
                  f"**Total Events:** {stats['total_events']}\n"
                  f"**Total Errors:** {stats['total_errors']}",
            inline=False
        )
        
        if stats['event_types']:
            event_summary = "\n".join([f"**{k}:** {v}" for k, v in stats['event_types'].items()])
            embed.add_field(
                name="Event Summary",
                value=event_summary[:1024],
                inline=False
            )
            
        if stats['recent_errors']:
            recent_errors = []
            for error in stats['recent_errors'][-3:]:
                recent_errors.append(
                    f"**{error['error_type']}** - {error['error_message'][:50]}..."
                )
            embed.add_field(
                name="Recent Errors",
                value="\n".join(recent_errors),
                inline=False
            )
            
        return embed

# Global debug logger instance
debug_logger = DebugLogger()