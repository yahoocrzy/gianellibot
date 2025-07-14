# ClickBot - Discord ClickUp Integration Bot Documentation

This document provides a comprehensive overview of the ClickBot Discord bot architecture, functionality, and codebase for AI analysis and understanding.

## Overview

ClickBot is a Discord bot that integrates ClickUp project management with Discord servers, featuring AI-powered task management, reaction roles, and interactive setup wizards. The bot is built with discord.py and uses modern Discord slash commands with interactive UI components.

## Architecture

### Core Components

1. **Main Bot (`main.py`)**
   - Entry point for the bot
   - Handles bot initialization, database setup, and cog loading
   - Includes web server for deployment platforms like Render
   - Graceful shutdown handling with signal handlers

2. **Database Layer (`database/`)**
   - SQLAlchemy-based models for data persistence
   - Models: ServerConfig, ReactionRole
   - Async database operations with aiosqlite/asyncpg support
   - Migration support via Alembic

3. **Services Layer (`services/`)**
   - `clickup_api.py`: Complete ClickUp API v2 wrapper with retry logic
   - `claude_api.py`: AI integration for natural language processing
   - `security.py`: Encryption/decryption for sensitive data storage

4. **Repository Pattern (`repositories/`)**
   - Data access layer abstracting database operations
   - `server_config.py`: Server configuration management
   - `reaction_roles.py`: Reaction role mappings storage

5. **Cogs (Commands) (`cogs/`)**
   - Modular command organization
   - `clickup_tasks.py`: Core ClickUp task management
   - `ai_commands.py`: AI-powered task operations
   - `reaction_roles.py`: Automated role assignment system
   - `setup_wizard.py`: Interactive bot configuration
   - `moderation.py`: Advanced moderation tools with purge functionality

6. **Utilities (`utils/`)**
   - `embed_factory.py`: Standardized Discord embed creation
   - `selection_views.py`: Interactive dropdown components
   - `helpers.py`: Common utility functions

## Key Features

### 1. ClickUp Integration

**Task Management Commands:**
- `/task-create` - Create tasks with priority, due dates, descriptions
- `/task-list` - List tasks from ClickUp lists with filtering
- `/task-update` - Modify existing tasks
- `/task-delete` - Delete tasks with confirmation
- `/task-comment` - Add comments to tasks
- `/task-assign` - Assign team members to tasks

**Interactive Navigation:**
- `/select-list` - Browse ClickUp hierarchy (Workspace → Space → List)
- Dropdown menus for workspace, space, and list selection
- Real-time loading of ClickUp data with proper error handling

### 2. AI-Powered Features

**Natural Language Processing:**
- `/ai-create-task` - Create tasks from plain English descriptions
- Automatic parsing of priorities, due dates, assignees from text
- Example: "Create urgent bug fix task due tomorrow"

**AI Analysis:**
- `/ai-analyze-tasks` - Multiple analysis types:
  - Priority suggestions based on task content
  - Dependency identification and ordering
  - Time estimates and deadline recommendations
  - Task organization and workflow optimization

**Task Optimization:**
- `/ai-task-suggestions` - Specific task improvement recommendations
- Analyzes task naming, descriptions, priorities, timelines
- Provides actionable suggestions for task breakdown

### 3. Reaction Role System

**Automated Role Management:**
- `/reaction-roles-setup` - Interactive setup with channel selection
- Users react to messages to get/remove roles automatically
- Database persistence for reaction → role mappings
- Support for multiple roles per message

**Administrative Tools:**
- `/reaction-roles-list` - View all reaction role messages
- Custom message titles and descriptions
- Emoji validation and role conflict detection

### 4. Setup and Configuration

**Interactive Setup Wizard:**
- `/clickup-setup` - Guided bot configuration
- API token validation with ClickUp workspace detection
- Optional notification channel selection
- Secure token encryption and storage

**Security Features:**
- All API tokens encrypted before database storage
- Per-server configuration isolation
- Administrator-only setup commands

### 5. Moderation System

**Advanced Message Management:**
- `/purge <amount> [user] [contains] [channel]` - Advanced message deletion with filters
- `/purge-user <user> [amount] [channel]` - Delete messages from specific users
- `/purge-bots [amount] [channel]` - Remove all bot messages
- `/clear-channel [channel] <confirm_text>` - Complete channel clearing (admin-only)

**Safety Features:**
- Confirmation dialogs for large purges (≥10 messages)
- Permission validation for both bot and users
- Pinned message protection
- Discord's 14-day message limit handling
- Comprehensive audit logging

**Security Controls:**
- Manage Messages permission required
- Administrator permission for destructive actions
- Confirmation text required for channel clearing
- Ephemeral responses to prevent command spam

## Technical Implementation

### Session Management (Critical Fix)

**Problem Solved:**
The bot previously experienced `RetryError[RuntimeError]` issues due to aiohttp session lifecycle problems during Discord interactions.

**Solution Implemented:**
```python
# In ClickUpAPI._request method
if not self._session or self._session.closed:
    logger.warning("Session is closed or None, creating new session")
    if self._session:
        await self._session.close()
    self._session = aiohttp.ClientSession(headers=self.headers)
```

**Key Improvements:**
- Session validation before each request
- Automatic session recreation when needed
- Proper cleanup in context managers
- Error handling for network issues

### Discord Interaction Patterns

**Deferred Responses:**
All time-consuming operations use `await interaction.response.defer()` to prevent Discord timeouts.

**View Classes:**
Interactive components inherit from `discord.ui.View` with proper timeout handling and user validation.

**Modal Forms:**
Text input handled via `discord.ui.Modal` for secure data collection (API tokens, configuration).

### Database Schema

**ServerConfig Table:**
- `guild_id`: Discord server ID (primary key)
- `clickup_token_encrypted`: Encrypted ClickUp API token
- `workspace_id`: Selected ClickUp workspace
- `notification_channel_id`: Optional channel for notifications
- `setup_complete`: Configuration status flag

**ReactionRole Table:**
- `id`: Primary key
- `guild_id`: Discord server ID
- `message_id`: Discord message ID
- `channel_id`: Discord channel ID
- `emoji`: Reaction emoji (unicode or custom)
- `role_id`: Discord role ID to assign
- `exclusive`: Whether role is mutually exclusive

### Error Handling Strategy

**Graceful Degradation:**
- AI features fall back to basic functionality if Claude API unavailable
- Network errors provide user-friendly messages with retry suggestions
- Invalid configurations prompt users to run setup again

**Logging:**
- Structured logging with Loguru
- Different log levels for development vs production
- Automatic log rotation and retention

## Command Reference

### Setup Commands
- `/clickup-setup` - Interactive ClickUp configuration
- `/reaction-roles-setup` - Interactive reaction role setup

### ClickUp Task Management
- `/select-list` - Browse ClickUp hierarchy
- `/task-create <name> [description] [list_id] [priority] [due_date]`
- `/task-list <list_id> [status] [assignee]`
- `/task-update <task_id> [name] [description] [status] [priority]`
- `/task-delete <task_id>`
- `/task-comment <task_id> <comment>`
- `/task-assign <task_id> <user>` (placeholder for future Discord→ClickUp mapping)

### AI-Powered Commands
- `/ai-create-task <command> [list_id]` - Natural language task creation
- `/ai-analyze-tasks <list_id> [analysis_type]` - AI task analysis
- `/ai-task-suggestions <task_id>` - AI improvement suggestions

### Reaction Role Management
- `/reaction-roles-setup` - Create reaction role messages
- `/reaction-roles-list` - List existing reaction role messages

### Moderation Commands
- `/purge <amount> [user] [contains] [channel]` - Advanced message purging
- `/purge-user <user> [amount] [channel]` - User-specific message deletion
- `/purge-bots [amount] [channel]` - Bot message cleanup
- `/clear-channel [channel] <confirm_text>` - Complete channel clearing

## Configuration Requirements

### Environment Variables
- `DISCORD_TOKEN` - Discord bot token
- `CLICKUP_API_KEY` - ClickUp API key (optional, configured per server)
- `DATABASE_URL` - Database connection string
- `LOG_LEVEL` - Logging level (INFO, DEBUG, ERROR)
- `WEB_SERVER_ENABLED` - Enable web server for deployment platforms
- `PORT` - Web server port (default: 10000)

### Discord Bot Permissions
Required permissions for full functionality:
- Send Messages
- Use Slash Commands
- View Channels
- Read Message History
- Embed Links
- Attach Files
- Manage Roles (for reaction roles)
- Add Reactions
- Manage Messages (for moderation/purge commands)
- Use External Emojis (optional, for custom reactions)

### ClickUp API Requirements
- Personal API token with workspace access
- Permissions to create, read, update, delete tasks
- Access to workspaces, spaces, lists, and folders

## Deployment Considerations

### Platform Support
- Designed for deployment on Render.com
- Includes web server for health checks
- Graceful shutdown handling for container environments

### Database Support
- SQLite for development
- PostgreSQL for production
- Automatic migration handling

### Security
- All sensitive data encrypted at rest
- No API tokens stored in plain text
- Per-server configuration isolation

## Recent Improvements

### Session Management Fix
Resolved critical `RetryError[RuntimeError]` issues that occurred when Discord interactions tried to use closed aiohttp sessions.

### AI Integration Enhancement
Added comprehensive AI-powered task management with natural language processing and intelligent analysis.

### User Experience Improvements
- Interactive setup wizards with channel selection dropdowns
- Better error messages with actionable suggestions
- Comprehensive command help and documentation

### Moderation System Addition
Implemented advanced moderation tools with multiple purge options, safety confirmations, and comprehensive permission handling.

### UI/UX Enhancements
- Replaced text inputs with user-friendly dropdown menus
- Added confirmation dialogs for destructive actions
- Implemented proper error handling and fallback mechanisms

## Development Patterns

### Async/Await Usage
All Discord and ClickUp operations use proper async/await patterns with context managers for resource management.

### Error Boundaries
Each command includes try/catch blocks with specific error handling for different failure modes.

### Modular Design
Cogs provide clear separation of concerns, making the bot easily extensible for new features.

This documentation should provide a complete understanding of the bot's architecture, functionality, and implementation details for AI analysis and further development.