#!/usr/bin/env python3
"""
Test script to verify bot connections and configurations
"""
import asyncio
import os
import sys
from dotenv import load_dotenv
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

async def test_discord_token():
    """Test Discord token validity"""
    print("\n🔌 Testing Discord Connection...")
    
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not found in environment")
        return False
        
    try:
        import discord
        import aiohttp
        
        # Test token with Discord API
        headers = {"Authorization": f"Bot {token}"}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://discord.com/api/v10/users/@me", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ Discord token valid - Bot: {data['username']}#{data['discriminator']}")
                    return True
                elif resp.status == 401:
                    print("❌ Discord token invalid or expired")
                    return False
                else:
                    print(f"❌ Discord API error: {resp.status}")
                    return False
    except Exception as e:
        print(f"❌ Error testing Discord token: {e}")
        return False

async def test_database():
    """Test database connection"""
    print("\n🗄️  Testing Database Connection...")
    
    try:
        from database.models import engine, ServerConfig
        from sqlalchemy import text
        
        async with engine.begin() as conn:
            # Test basic connection
            result = await conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
            
            # Check if tables exist
            tables = await conn.run_sync(
                lambda sync_conn: sync_conn.dialect.get_table_names(sync_conn)
            )
            
            expected_tables = [
                'server_configs', 'reaction_roles', 'user_preferences',
                'clickup_workspaces', 'claude_configs', 'cache'
            ]
            
            for table in expected_tables:
                if table in tables:
                    print(f"  ✅ Table '{table}' exists")
                else:
                    print(f"  ❌ Table '{table}' missing")
                    
            return True
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

async def test_encryption():
    """Test encryption functionality"""
    print("\n🔐 Testing Encryption...")
    
    try:
        from services.security import security_service
        
        # Test encryption/decryption
        test_string = "test_token_12345"
        encrypted = security_service.encrypt(test_string)
        decrypted = security_service.decrypt(encrypted)
        
        if decrypted == test_string:
            print("✅ Encryption/decryption working correctly")
            return True
        else:
            print("❌ Encryption/decryption mismatch")
            return False
            
    except Exception as e:
        print(f"❌ Encryption error: {e}")
        return False

async def test_clickup_api():
    """Test ClickUp API if configured"""
    print("\n🔗 Testing ClickUp API...")
    
    try:
        from database.models import async_session, ClickUpWorkspace
        from services.clickup_api import ClickUpAPI
        from repositories.clickup_workspaces import ClickUpWorkspaceRepository
        
        # Get any configured workspace
        async with async_session() as session:
            result = await session.execute(
                session.query(ClickUpWorkspace).filter_by(is_active=True).limit(1)
            )
            workspace = result.scalar_one_or_none()
            
        if not workspace:
            print("⚠️  No ClickUp workspaces configured yet")
            return None
            
        # Test API
        token = await ClickUpWorkspaceRepository.get_decrypted_token(workspace)
        api = ClickUpAPI(token)
        
        async with api:
            workspaces = await api.get_workspaces()
            if workspaces:
                print(f"✅ ClickUp API working - Found {len(workspaces)} workspace(s)")
                for ws in workspaces[:2]:
                    print(f"  - {ws['name']}")
                return True
            else:
                print("❌ ClickUp API returned no workspaces")
                return False
                
    except Exception as e:
        print(f"❌ ClickUp API error: {e}")
        return False

async def test_claude_api():
    """Test Claude API if configured"""
    print("\n🤖 Testing Claude API...")
    
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        print("⚠️  CLAUDE_API_KEY not set - Claude features won't work")
        return None
        
    try:
        from services.claude_api import ClaudeAPI
        
        claude = ClaudeAPI(api_key)
        response = await claude.test_connection()
        
        if response:
            print("✅ Claude API connection successful")
            return True
        else:
            print("❌ Claude API test failed")
            return False
            
    except Exception as e:
        print(f"❌ Claude API error: {e}")
        return False

async def test_web_server():
    """Test if web server can start"""
    print("\n🌐 Testing Web Server...")
    
    try:
        import uvicorn
        from fastapi import FastAPI
        
        app = FastAPI()
        print("✅ FastAPI and Uvicorn available")
        
        port = int(os.getenv("PORT", 10000))
        print(f"  - Configured port: {port}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Web server dependencies missing: {e}")
        return False

async def main():
    """Run all tests"""
    print("=" * 60)
    print("🤖 ClickUp Discord Bot Connection Tests")
    print("=" * 60)
    print(f"Started: {datetime.utcnow().isoformat()}")
    
    results = {
        "Discord": await test_discord_token(),
        "Database": await test_database(),
        "Encryption": await test_encryption(),
        "Web Server": await test_web_server(),
        "ClickUp API": await test_clickup_api(),
        "Claude API": await test_claude_api(),
    }
    
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test, result in results.items():
        if result is True:
            print(f"✅ {test}: PASSED")
            passed += 1
        elif result is False:
            print(f"❌ {test}: FAILED")
            failed += 1
        else:
            print(f"⚠️  {test}: SKIPPED")
            skipped += 1
            
    print("\n" + "-" * 60)
    print(f"Total: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0:
        print("\n✅ All required tests passed! Bot should be ready to run.")
    else:
        print(f"\n❌ {failed} test(s) failed. Please check the errors above.")
        
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())