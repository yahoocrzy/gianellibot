#!/usr/bin/env python3
"""
Test script to verify all bot commands work properly
Run this after deployment to check functionality
"""

import asyncio
import discord
from discord.ext import commands
import os
from datetime import datetime
from loguru import logger

# Test configuration
TEST_RESULTS = []

def log_test(command: str, status: str, details: str = ""):
    """Log test result"""
    result = {
        "command": command,
        "status": status,
        "details": details,
        "timestamp": datetime.now()
    }
    TEST_RESULTS.append(result)
    
    emoji = "✅" if status == "PASS" else "❌"
    logger.info(f"{emoji} {command}: {status} {details}")

async def test_command_registration(bot):
    """Test that all commands are registered"""
    log_test("Command Registration", "START", "Checking registered commands...")
    
    commands = bot.tree.get_commands()
    expected_commands = [
        # Task Management
        "task-create", "task-update", "task-list", "task-delete",
        
        # Calendar
        "calendar", "upcoming", "today",
        
        # Workspaces
        "workspace-add", "workspace-list", "workspace-switch", "workspace-remove",
        
        # AI
        "ai", "ai-chat", "ai-analyze-tasks",
        
        # Claude Setup
        "claude-setup", "claude-settings", "claude-status",
        
        # Help
        "help", "about", "setup-help-pin", "update-help-pin",
        
        # Reaction Roles
        "reaction-roles-setup", "reaction-roles-list",
        
        # Moderation
        "purge", "purge-user", "purge-bots", "clear-channel",
        
        # Legacy
        "clickup-setup"
    ]
    
    registered = [cmd.name for cmd in commands]
    
    for expected in expected_commands:
        if expected in registered:
            log_test(f"Command /{expected}", "PASS", "Registered")
        else:
            log_test(f"Command /{expected}", "FAIL", "Not registered")
    
    # Check for unexpected commands
    for cmd in registered:
        if cmd not in expected_commands:
            log_test(f"Command /{cmd}", "INFO", "Extra command found")

async def test_cog_loading(bot):
    """Test that all cogs loaded properly"""
    log_test("Cog Loading", "START", "Checking loaded cogs...")
    
    expected_cogs = [
        "moderation",
        "calendar_commands", 
        "clickup_tasks_enhanced",
        "ai_commands_enhanced",
        "ai_complete_dropdown",
        "ai_conversation",
        "reaction_roles",
        "setup_wizard",
        "claude_setup",
        "workspace_management",
        "help_command",
        "help_pin"
    ]
    
    loaded_cogs = [name.lower() for name in bot.cogs.keys()]
    
    for expected in expected_cogs:
        cog_name = f"cogs.{expected}"
        if expected in [cog.lower() for cog in loaded_cogs]:
            log_test(f"Cog {expected}", "PASS", "Loaded")
        else:
            log_test(f"Cog {expected}", "FAIL", "Not loaded")

async def test_database_connection():
    """Test database connectivity"""
    log_test("Database", "START", "Testing database connection...")
    
    try:
        from database.models import init_db, async_session
        await init_db()
        
        # Test query
        async with async_session() as session:
            result = await session.execute("SELECT 1")
            
        log_test("Database Connection", "PASS", "Connected and queried successfully")
    except Exception as e:
        log_test("Database Connection", "FAIL", str(e))

async def test_api_connections():
    """Test external API connections"""
    log_test("APIs", "START", "Testing API connections...")
    
    # Test ClickUp API structure
    try:
        from services.clickup_api import ClickUpAPI
        log_test("ClickUp API Import", "PASS", "Module imported")
    except Exception as e:
        log_test("ClickUp API Import", "FAIL", str(e))
    
    # Test Claude API structure
    try:
        from services.claude_api import ClaudeAPI
        log_test("Claude API Import", "PASS", "Module imported")
    except Exception as e:
        log_test("Claude API Import", "FAIL", str(e))
    
    # Test Security Service
    try:
        from services.security import security_service, encrypt_token, decrypt_token
        
        # Test encryption/decryption
        test_token = "test_token_12345"
        encrypted = await encrypt_token(test_token)
        decrypted = await decrypt_token(encrypted)
        
        if decrypted == test_token:
            log_test("Security Service", "PASS", "Encryption/decryption working")
        else:
            log_test("Security Service", "FAIL", "Encryption/decryption mismatch")
    except Exception as e:
        log_test("Security Service", "FAIL", str(e))

async def test_view_components():
    """Test Discord UI components"""
    log_test("UI Components", "START", "Testing view components...")
    
    try:
        from utils.enhanced_selections import (
            ListSelectView, TaskSelectView, UserSelectView,
            PrioritySelectView, StatusSelectView
        )
        log_test("Selection Views", "PASS", "All view classes imported")
    except Exception as e:
        log_test("Selection Views", "FAIL", str(e))
    
    try:
        from utils.embed_factory import EmbedFactory
        
        # Test embed creation
        test_embed = EmbedFactory.create_success_embed("Test", "Test message")
        if isinstance(test_embed, discord.Embed):
            log_test("Embed Factory", "PASS", "Creates valid embeds")
        else:
            log_test("Embed Factory", "FAIL", "Invalid embed type")
    except Exception as e:
        log_test("Embed Factory", "FAIL", str(e))

def print_test_summary():
    """Print test results summary"""
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in TEST_RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in TEST_RESULTS if r["status"] == "FAIL")
    total = passed + failed
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed > 0:
        print("\nFailed Tests:")
        for result in TEST_RESULTS:
            if result["status"] == "FAIL":
                print(f"  - {result['command']}: {result['details']}")
    
    print("\n" + "="*60)

async def run_tests():
    """Run all tests"""
    print("Starting ClickBot Test Suite...")
    
    # Test imports and basic functionality
    await test_database_connection()
    await test_api_connections()
    await test_view_components()
    
    # Create a test bot instance to check commands
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    # Import and setup cogs
    from pathlib import Path
    
    cogs_dir = Path("cogs")
    for cog_file in cogs_dir.glob("*.py"):
        if cog_file.name != "__init__.py":
            cog_name = f"cogs.{cog_file.stem}"
            try:
                await bot.load_extension(cog_name)
            except Exception as e:
                log_test(f"Loading {cog_name}", "FAIL", str(e))
    
    # Run tests
    await test_cog_loading(bot)
    await test_command_registration(bot)
    
    # Print summary
    print_test_summary()

if __name__ == "__main__":
    asyncio.run(run_tests())