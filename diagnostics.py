#!/usr/bin/env python3
"""
Standalone diagnostics script to check bot configuration and environment
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import json
from datetime import datetime

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

class BotDiagnostics:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.successes = []
        
    def add_issue(self, message):
        self.issues.append(f"❌ {message}")
        
    def add_warning(self, message):
        self.warnings.append(f"⚠️  {message}")
        
    def add_success(self, message):
        self.successes.append(f"✅ {message}")
        
    def check_environment(self):
        """Check environment variables"""
        print("\n🔍 Checking Environment Variables...")
        
        required_vars = {
            "DISCORD_TOKEN": "Discord bot token",
            "ENCRYPTION_KEY": "Encryption key for sensitive data",
            "CLAUDE_API_URL": "Claude API URL"
        }
        
        optional_vars = {
            "CLAUDE_API_KEY": "Claude API key",
            "DATABASE_URL": "Database connection string",
            "REDIS_URL": "Redis connection string",
            "PORT": "Web server port",
            "LOG_LEVEL": "Logging level",
            "DEBUG": "Debug mode flag"
        }
        
        # Check required variables
        for var, description in required_vars.items():
            value = os.getenv(var)
            if not value:
                self.add_issue(f"{var} is missing - {description}")
            else:
                if var == "ENCRYPTION_KEY" and len(value) < 32:
                    self.add_warning(f"{var} is too short (must be at least 32 characters)")
                else:
                    self.add_success(f"{var} is set")
                    
        # Check optional variables
        for var, description in optional_vars.items():
            value = os.getenv(var)
            if value:
                self.add_success(f"{var} is set (optional)")
            else:
                self.add_warning(f"{var} is not set - {description}")
                
    def check_files(self):
        """Check important files exist"""
        print("\n📁 Checking Files...")
        
        important_files = [
            "main.py",
            "config.py",
            "requirements.txt"
        ]
        
        for file in important_files:
            if Path(file).exists():
                self.add_success(f"{file} exists")
            else:
                self.add_issue(f"{file} is missing")
                
        # Check for .env file
        if Path(".env").exists():
            self.add_success(".env file exists")
        else:
            self.add_warning(".env file not found - using system environment variables")
            
    def check_directories(self):
        """Check required directories"""
        print("\n📂 Checking Directories...")
        
        required_dirs = ["cogs", "services", "utils", "database", "repositories"]
        
        for dir_name in required_dirs:
            if Path(dir_name).exists() and Path(dir_name).is_dir():
                # Count Python files
                py_files = list(Path(dir_name).glob("*.py"))
                self.add_success(f"{dir_name}/ exists ({len(py_files)} Python files)")
            else:
                self.add_issue(f"{dir_name}/ directory is missing")
                
    async def check_database(self):
        """Check database connectivity"""
        print("\n🗄️  Checking Database...")
        
        try:
            from database.models import engine, Base
            from sqlalchemy import text
            
            # Test connection
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                self.add_success("Database connection successful")
                
                # Check tables
                async with engine.begin() as conn:
                    tables = await conn.run_sync(
                        lambda sync_conn: sync_conn.dialect.get_table_names(sync_conn)
                    )
                    if tables:
                        self.add_success(f"Found {len(tables)} database tables")
                    else:
                        self.add_warning("No database tables found - run migrations")
                        
        except ImportError as e:
            self.add_issue(f"Failed to import database modules: {e}")
        except Exception as e:
            self.add_issue(f"Database connection failed: {e}")
            
    def check_dependencies(self):
        """Check Python dependencies"""
        print("\n📦 Checking Dependencies...")
        
        try:
            import discord
            self.add_success(f"discord.py version: {discord.__version__}")
        except ImportError:
            self.add_issue("discord.py is not installed")
            
        try:
            import aiohttp
            self.add_success("aiohttp is installed")
        except ImportError:
            self.add_issue("aiohttp is not installed")
            
        try:
            import sqlalchemy
            self.add_success(f"SQLAlchemy version: {sqlalchemy.__version__}")
        except ImportError:
            self.add_issue("SQLAlchemy is not installed")
            
    def check_cogs(self):
        """Check cog files for issues"""
        print("\n⚙️  Checking Cogs...")
        
        cogs_dir = Path("cogs")
        if not cogs_dir.exists():
            self.add_issue("Cogs directory not found")
            return
            
        cog_files = list(cogs_dir.glob("*.py"))
        active_cogs = [f for f in cog_files if not f.name.endswith(('.old', '.disabled', '.future'))]
        disabled_cogs = [f for f in cog_files if f.name.endswith(('.old', '.disabled', '.future'))]
        
        self.add_success(f"Found {len(active_cogs)} active cogs")
        if disabled_cogs:
            self.add_warning(f"Found {len(disabled_cogs)} disabled cogs")
            
        # Check each active cog for basic syntax
        for cog_file in active_cogs:
            try:
                with open(cog_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'async def setup(bot)' not in content:
                        self.add_warning(f"{cog_file.name} missing setup function")
                    else:
                        self.add_success(f"{cog_file.name} has setup function")
            except Exception as e:
                self.add_issue(f"Error reading {cog_file.name}: {e}")
                
    def print_report(self):
        """Print diagnostic report"""
        print("\n" + "="*60)
        print("📊 DIAGNOSTIC REPORT")
        print("="*60)
        print(f"Generated: {datetime.utcnow().isoformat()}")
        
        if self.successes:
            print(f"\n✅ Successes ({len(self.successes)}):")
            for msg in self.successes:
                print(f"  {msg}")
                
        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for msg in self.warnings:
                print(f"  {msg}")
                
        if self.issues:
            print(f"\n❌ Issues ({len(self.issues)}):")
            for msg in self.issues:
                print(f"  {msg}")
                
        print("\n" + "="*60)
        
        if self.issues:
            print("❗ CRITICAL ISSUES FOUND - Bot may not function properly")
        elif self.warnings:
            print("⚠️  Some warnings found - Bot should work but check warnings")
        else:
            print("✅ All checks passed - Bot should be ready to run")
            
        print("="*60)
        
async def main():
    print("🤖 ClickUp Discord Bot Diagnostics")
    print("="*60)
    
    diag = BotDiagnostics()
    
    # Run checks
    diag.check_environment()
    diag.check_files()
    diag.check_directories()
    diag.check_dependencies()
    diag.check_cogs()
    await diag.check_database()
    
    # Print report
    diag.print_report()
    
    # Save report to file
    report_file = f"diagnostics_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w') as f:
        f.write(f"ClickUp Discord Bot Diagnostics Report\n")
        f.write(f"Generated: {datetime.utcnow().isoformat()}\n\n")
        
        if diag.successes:
            f.write(f"Successes ({len(diag.successes)}):\n")
            for msg in diag.successes:
                f.write(f"  {msg}\n")
            f.write("\n")
            
        if diag.warnings:
            f.write(f"Warnings ({len(diag.warnings)}):\n")
            for msg in diag.warnings:
                f.write(f"  {msg}\n")
            f.write("\n")
            
        if diag.issues:
            f.write(f"Issues ({len(diag.issues)}):\n")
            for msg in diag.issues:
                f.write(f"  {msg}\n")
                
    print(f"\n📝 Report saved to: {report_file}")

if __name__ == "__main__":
    asyncio.run(main())