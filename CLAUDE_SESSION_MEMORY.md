# Claude Session Memory - ClickBot Development

## Project Overview
ClickBot is a multi-purpose Discord bot featuring ClickUp project management integration, team mood/status system, moderation tools, and various utility features. Built using discord.py 2.4.0 with async SQLAlchemy for database operations.

## Current Development Context

### Recent Major Implementation (Current Session)
**Team Mood Status System** - Complete automated team availability/status system

#### Key Features Implemented:
1. **One-Command Setup** - `/team-mood-setup` automatically creates everything
2. **Automatic Role Creation** - Creates 4 status roles with proper colors:
   - ✅ Ready to Work (Green #00D166)
   - ⚠️ Phone Only (Yellow #FEE75C)
   - 🛑 Do not disturb! (Red #ED4245)
   - 💤 Need time (Bright Blue #5DADE2)
3. **Nickname Status Display** - Adds status emojis to usernames (e.g., "Username ✅")
4. **Smart Status Management** - Exclusive behavior (only one status at a time)
5. **Reaction Role System** - Click reactions to get/remove status roles

#### Commands Available:
- `/team-mood-setup [channel]` - Complete automated setup
- `/team-mood-status` - View current team availability statistics
- `/team-mood-remove [delete_roles]` - Remove system with optional role cleanup
- `/team-mood-refresh` - Recreate status message if deleted

#### Files Created/Modified:
- **NEW**: `database/models.py` - Added TeamMoodConfig and ReactionRole models
- **NEW**: `repositories/team_mood_repository.py` - Database operations
- **NEW**: `repositories/reaction_roles.py` - Reaction role management (recreated)
- **NEW**: `services/team_mood_service.py` - Core business logic
- **NEW**: `cogs/team_mood_commands.py` - Slash command interface
- **NEW**: `cogs/reaction_role_handler.py` - Event handlers for reactions
- **UPDATED**: `cogs/help_command.py` - Updated feature descriptions
- **UPDATED**: `cogs/help_pin.py` - Updated command documentation

#### Recent Commits:
1. `a3ee1d9` - Implement complete Team Mood Status System with automated setup
2. `b636599` - Enhance team mood roles with emojis and improved visibility
3. `d67617d` - Add nickname status display and improve role visibility

## Persistent Development Requirements

### User Preferences & Patterns:
1. **Commit Style**: Comprehensive commit messages with detailed feature descriptions
2. **Code Organization**: Clean architecture with repository/service/cog separation
3. **Error Handling**: Graceful degradation with proper permission checks
4. **User Experience**: Zero manual configuration required after setup commands
5. **Documentation**: Always update help systems when adding new features

### Technical Standards:
- Use async/await throughout
- SQLAlchemy with async sessions
- Proper logging with loguru
- Discord.py 2.4.0 patterns
- Type hints where appropriate
- Permission-based access control

### Bot Architecture Understanding:
- **Database Layer**: SQLAlchemy models in `database/models.py`
- **Repository Layer**: Data access in `repositories/`
- **Service Layer**: Business logic in `services/`
- **Presentation Layer**: Discord cogs in `cogs/`
- **Utilities**: Helper functions in `utils/`

### Auto-Loading System:
- Main.py automatically loads all `.py` files from `cogs/` directory
- No manual cog registration needed
- Files ending in `.old`, `.disabled`, `.future` are ignored

### Current Bot Status:
- **Deployment**: Hosted on Render platform
- **Database**: PostgreSQL in production, SQLite in development
- **Features**: ClickUp integration, team mood system, moderation, mood tracking
- **Missing**: Claude AI integration (infrastructure exists but not implemented)

## Development Commands to Remember:
- `python3 -m py_compile <file>` - Test compilation
- `git add <files> && git commit -m "message"` - Commit changes
- Main entry point: `main.py`
- Bot loads cogs automatically from `cogs/` directory

## Common Tasks:
1. **Adding New Commands**: Create cog in `cogs/`, update help system
2. **Database Changes**: Update models, create repository, add service logic
3. **Permission Requirements**: Use `@app_commands.default_permissions()`
4. **Error Handling**: Always include try/catch with proper logging

## Current State:
- Team mood system fully functional with nickname display
- All files compile successfully
- Ready for deployment and testing
- Next potential enhancements: ClickUp integration improvements, additional status customization

## Note for Future Sessions:
If continuing development, check git log for latest commits and review recent changes to understand current implementation state. The team mood system is the most recent major feature and should be fully functional.